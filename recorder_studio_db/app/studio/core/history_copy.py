"""Copy the recorder history of a SQLite file into a database Home Assistant already created its tables in.

Design (so Home Assistant may keep writing while we copy):
* The source is opened read-only and is never changed: it stays as the backup.
* Rows whose ids are only referenced inside the copied data get the old id + an offset that is larger than anything
  the target holds, so they can never collide with rows Home Assistant is writing at the same time.
* Small lookup tables (states_meta, event_types, statistics_meta) are merged by name instead.
* Only real columns are copied; the legacy text columns of old schemas are skipped.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Callable

MARGIN = 1_000_000  # head-room above the highest id in the target
BATCH = 5000

# table -> (primary key, columns to copy)
STAT_COLS = ["created_ts", "metadata_id", "start_ts", "mean", "mean_weight", "min", "max", "last_reset_ts", "state", "sum"]
TABLES: dict[str, tuple[str, list[str]]] = {
    "states_meta": ("metadata_id", ["entity_id"]),
    "event_types": ("event_type_id", ["event_type"]),
    "state_attributes": ("attributes_id", ["hash", "shared_attrs"]),
    "event_data": ("data_id", ["hash", "shared_data"]),
    "states": ("state_id", ["state", "last_changed_ts", "last_reported_ts", "last_updated_ts", "old_state_id", "attributes_id", "origin_idx", "context_id_bin", "context_user_id_bin", "context_parent_id_bin", "metadata_id"]),
    "events": ("event_id", ["event_type_id", "data_id", "origin_idx", "time_fired_ts", "context_id_bin", "context_user_id_bin", "context_parent_id_bin"]),
    "statistics_meta": ("id", ["statistic_id", "source", "unit_of_measurement", "unit_class", "has_mean", "has_sum", "name", "mean_type"]),
    "statistics": ("id", STAT_COLS),
    "statistics_short_term": ("id", STAT_COLS),
}
BOOL_COLS = {"has_mean", "has_sum"}
REQUIRED = ("states", "states_meta", "state_attributes")


class CopyError(Exception):
    """Something prevents the copy; the message is meant for the user."""


class Progress:
    def __init__(self) -> None:
        self.state = "idle"  # idle | running | done | error
        self.step = ""
        self.done = 0
        self.total = 0
        self.started: float | None = None
        self.finished: float | None = None
        self.copied: dict[str, int] = {}
        self.error: str | None = None
        self.source = ""
        self.engine = ""

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in ("state", "step", "done", "total", "started", "finished", "copied", "error", "source", "engine")}


def _table_columns(cur, dialect: str, table: str) -> set[str]:
    if dialect == "sqlite":
        cur.execute(f"PRAGMA table_info({table})")
        return {r[1] for r in cur.fetchall()}
    if dialect == "postgresql":
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s", (table,))
    else:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s", (table,))
    return {r[0].lower() if isinstance(r[0], str) else r[0] for r in cur.fetchall()}


def _placeholder(dialect: str) -> str:
    return "?" if dialect == "sqlite" else "%s"


def _insert_rows(cur, dialect: str, table: str, cols: list[str], rows: list[tuple], ignore: bool = False) -> None:
    if not rows:
        return
    names = ", ".join(cols)
    if dialect == "postgresql":
        from psycopg2.extras import execute_values

        sql = f"INSERT INTO {table} ({names}) VALUES %s" + (" ON CONFLICT DO NOTHING" if ignore else "")
        execute_values(cur, sql, rows, page_size=BATCH)
        return
    verb = {"sqlite": "INSERT OR IGNORE", "mariadb": "INSERT IGNORE"}.get(dialect, "INSERT") if ignore else "INSERT"
    ph = ", ".join([_placeholder(dialect)] * len(cols))
    cur.executemany(f"{verb} INTO {table} ({names}) VALUES ({ph})", rows)


def _max_id(cur, table: str, pk: str) -> int:
    cur.execute(f"SELECT COALESCE(MAX({pk}), 0) FROM {table}")
    return int(cur.fetchone()[0])


def _merge_lookup(src: sqlite3.Connection, cur, dialect: str, table: str, pk: str, key: str, extra: list[str]) -> dict[int, int]:
    """Copy a small lookup table by its natural key; returns old id -> id in the target."""
    ph = _placeholder(dialect)
    cur.execute(f"SELECT {pk}, {key} FROM {table}")
    existing = {row[1]: int(row[0]) for row in cur.fetchall()}
    mapping: dict[int, int] = {}
    cols = [key] + extra
    for row in src.execute(f"SELECT {pk}, {', '.join(cols)} FROM {table}"):
        old_id, natural = int(row[0]), row[1]
        if natural in existing:
            mapping[old_id] = existing[natural]
            continue
        values = [bool(v) if (c in BOOL_COLS and v is not None and dialect == "postgresql") else v for c, v in zip(cols, row[1:])]
        if dialect == "postgresql":
            cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join([ph] * len(cols))}) RETURNING {pk}", values)
            new_id = int(cur.fetchone()[0])
        else:
            cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join([ph] * len(cols))})", values)
            new_id = int(cur.lastrowid)
        existing[natural] = new_id
        mapping[old_id] = new_id
    return mapping


def copy_history(source_path: str, connect: Callable[[], Any], dialect: str, progress: Progress | None = None, batch: int = BATCH) -> dict[str, int]:
    """Copy history from the SQLite file at source_path. `connect` returns a writable DB-API connection to the target."""
    progress = progress or Progress()
    src = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    conn = connect()
    copied: dict[str, int] = {}
    try:
        cur = conn.cursor()
        have = {t for t in TABLES if _table_columns(cur, dialect, t)}
        missing = [t for t in REQUIRED if t not in have]
        if missing:
            raise CopyError("The target database has no Home Assistant tables yet. Activate this database for the recorder, restart Home Assistant and try again.")
        src_tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "states" not in src_tables:
            raise CopyError("The SQLite file does not look like a Home Assistant database (no states table).")
        todo = [t for t in TABLES if t in have and t in src_tables]
        progress.total = sum(int(src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in todo)
        progress.done = 0
        cols_of: dict[str, list[str]] = {}
        for t in todo:
            target_cols = _table_columns(cur, dialect, t)
            src_cols = {r[1] for r in src.execute(f"PRAGMA table_info({t})")}
            cols_of[t] = [c for c in TABLES[t][1] if c in target_cols and c in src_cols]
        offsets = {t: _max_id(cur, t, TABLES[t][0]) + MARGIN for t in todo}

        def tick(table: str, n: int) -> None:
            progress.done += n
            copied[table] = copied.get(table, 0) + n
            progress.copied = dict(copied)

        def bulk(table: str, query: str, transform: Callable[[tuple], tuple], cols: list[str], ignore: bool = False) -> None:
            progress.step = table
            pending: list[tuple] = []
            for row in src.execute(query):
                pending.append(transform(row))
                if len(pending) >= batch:
                    _insert_rows(cur, dialect, table, cols, pending, ignore)
                    conn.commit()
                    tick(table, len(pending))
                    pending = []
            if pending:
                _insert_rows(cur, dialect, table, cols, pending, ignore)
                conn.commit()
                tick(table, len(pending))

        meta_map: dict[int, int] = {}
        if "states_meta" in todo:
            progress.step = "states_meta"
            meta_map = _merge_lookup(src, cur, dialect, "states_meta", "metadata_id", "entity_id", [])
            conn.commit()
            tick("states_meta", len(meta_map))
        type_map: dict[int, int] = {}
        if "event_types" in todo:
            progress.step = "event_types"
            type_map = _merge_lookup(src, cur, dialect, "event_types", "event_type_id", "event_type", [])
            conn.commit()
            tick("event_types", len(type_map))
        stat_map: dict[int, int] = {}
        if "statistics_meta" in todo:
            progress.step = "statistics_meta"
            stat_map = _merge_lookup(src, cur, dialect, "statistics_meta", "id", "statistic_id", [c for c in cols_of["statistics_meta"] if c != "statistic_id"])
            conn.commit()
            tick("statistics_meta", len(stat_map))

        for table, pk in (("state_attributes", "attributes_id"), ("event_data", "data_id")):
            if table in todo:
                off = offsets[table]
                cols = cols_of[table]
                bulk(table, f"SELECT {pk}, {', '.join(cols)} FROM {table} ORDER BY {pk}", lambda r, off=off: (r[0] + off,) + tuple(r[1:]), [pk] + cols)

        if "states" in todo:
            cols = cols_of["states"]
            sel = []
            for c in cols:
                if c == "old_state_id":
                    sel.append("CASE WHEN o.state_id IS NULL THEN NULL ELSE s.old_state_id END")
                elif c == "attributes_id":
                    sel.append("CASE WHEN a.attributes_id IS NULL THEN NULL ELSE s.attributes_id END")
                else:
                    sel.append(f"s.{c}")
            query = ("SELECT s.state_id, " + ", ".join(sel) + " FROM states s LEFT JOIN states o ON o.state_id = s.old_state_id "
                     "LEFT JOIN state_attributes a ON a.attributes_id = s.attributes_id ORDER BY s.state_id")
            idx = {c: i + 1 for i, c in enumerate(cols)}
            so, ao = offsets["states"], offsets.get("state_attributes", 0)

            def fix_state(r: tuple) -> tuple:
                v = list(r)
                v[0] += so
                if "old_state_id" in idx and v[idx["old_state_id"]] is not None:
                    v[idx["old_state_id"]] += so
                if "attributes_id" in idx and v[idx["attributes_id"]] is not None:
                    v[idx["attributes_id"]] += ao
                if "metadata_id" in idx:
                    v[idx["metadata_id"]] = meta_map.get(v[idx["metadata_id"]])
                return tuple(v)

            bulk("states", query, fix_state, ["state_id"] + cols)

        if "events" in todo:
            cols = cols_of["events"]
            idx = {c: i + 1 for i, c in enumerate(cols)}
            eo, do = offsets["events"], offsets.get("event_data", 0)

            def fix_event(r: tuple) -> tuple:
                v = list(r)
                v[0] += eo
                if "data_id" in idx and v[idx["data_id"]] is not None:
                    v[idx["data_id"]] += do
                if "event_type_id" in idx:
                    v[idx["event_type_id"]] = type_map.get(v[idx["event_type_id"]])
                return tuple(v)

            bulk("events", f"SELECT event_id, {', '.join(cols)} FROM events ORDER BY event_id", fix_event, ["event_id"] + cols)

        for table in ("statistics", "statistics_short_term"):
            if table in todo:
                cols = cols_of[table]
                mi = cols.index("metadata_id")

                def fix_stat(r: tuple, mi=mi) -> tuple:
                    v = list(r)
                    v[mi] = stat_map.get(v[mi])
                    return tuple(v)

                # the unique (metadata_id, start_ts) index makes rows Home Assistant already holds a harmless duplicate
                bulk(table, f"SELECT {', '.join(cols)} FROM {table} WHERE metadata_id IS NOT NULL ORDER BY id", fix_stat, cols, ignore=True)

        if dialect == "postgresql":
            progress.step = "sequences"
            for t in todo:
                pk = TABLES[t][0]
                cur.execute(f"SELECT setval(pg_get_serial_sequence('{t}', '{pk}'), (SELECT COALESCE(MAX({pk}), 1) FROM {t}))")
            conn.commit()
        return copied
    finally:
        src.close()
        conn.close()


def run(source_path: str, connect: Callable[[], Any], dialect: str, progress: Progress) -> None:
    """Thread entry point: never raises, reports through progress."""
    progress.state, progress.started, progress.finished, progress.error, progress.copied = "running", time.time(), None, None, {}
    try:
        copy_history(source_path, connect, dialect, progress)
        progress.state, progress.step = "done", "done"
    except CopyError as err:
        progress.state, progress.error = "error", str(err)
    except Exception as err:  # noqa: BLE001 - shown to the user
        progress.state, progress.error = "error", f"{type(err).__name__}: {err}"
    finally:
        progress.finished = time.time()
