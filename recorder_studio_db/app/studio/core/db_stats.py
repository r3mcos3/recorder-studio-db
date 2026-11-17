"""Read-only SQLite analysis of the recorder database."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time
from typing import Any

DEFAULT_DB = "home-assistant_v2.db"
RECENT_SECONDS = 86400  # window for the "records in the last 24 hours" growth numbers
ATTR_TIME_LIMIT = 20.0  # seconds; the attribute size query is aborted when it takes longer


def resolve_db_path(config_dir: str, db_url: str | None) -> Path:
    """Map a SQLAlchemy sqlite URL to a file path (relative URLs resolve against config_dir)."""
    base = Path(config_dir)
    if db_url and db_url.lower().startswith("sqlite://"):
        raw = db_url.partition("://")[2].partition("?")[0]
        if raw.strip("/"):
            if db_url.startswith("sqlite:////"):
                return Path("/" + raw.lstrip("/"))
            return base / raw.lstrip("/")
    return base / DEFAULT_DB


def total_size_bytes(db_path: Path) -> int:
    """Sum of the .db file and its -wal / -shm sidecars."""
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += (db_path.with_name(db_path.name + suffix)).stat().st_size
        except OSError:
            pass
    return total


def file_sizes(db_path: Path) -> dict[str, int]:
    """Sizes of the database file and its WAL/SHM sidecars (cheap: stat only, no SQL)."""
    out = {}
    for key, suffix in (("db", ""), ("wal", "-wal"), ("shm", "-shm")):
        try:
            out[key] = db_path.with_name(db_path.name + suffix).stat().st_size
        except OSError:
            out[key] = 0
    out["total"] = out["db"] + out["wal"] + out["shm"]
    return out


def table_sizes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Bytes per table (indexes included) using the dbstat virtual table; [] when unavailable."""
    try:
        owner = {n: t for n, t in conn.execute("SELECT name, tbl_name FROM sqlite_master")}
        sizes: dict[str, int] = {}
        for name, size in conn.execute("SELECT name, SUM(pgsize) FROM dbstat GROUP BY name"):
            table = owner.get(name, name)
            sizes[table] = sizes.get(table, 0) + int(size or 0)
    except sqlite3.Error:
        return []
    return [{"name": n, "bytes": b} for n, b in sorted(sizes.items(), key=lambda kv: -kv[1]) if b]


def free_bytes(conn: sqlite3.Connection) -> int:
    """Space inside the file that is unused and would be returned to the OS by a repack."""
    try:
        pages = conn.execute("PRAGMA freelist_count").fetchone()[0]
        size = conn.execute("PRAGMA page_size").fetchone()[0]
        return int(pages) * int(size)
    except sqlite3.Error:
        return 0


def recent_counts(conn: sqlite3.Connection, now_ts: float | None = None, seconds: int = RECENT_SECONDS) -> dict[str, int]:
    """Records written per entity during the last `seconds` (the real ingest rate, unaffected by purges).

    Needs the modern schema (states_meta + states.last_updated_ts, indexed); returns {} on anything else.
    """
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(states)")}
        if "last_updated_ts" not in cols or "metadata_id" not in cols:
            return {}
        since = (now_ts if now_ts is not None else time.time()) - seconds
        rows = conn.execute(
            "SELECT m.entity_id, COUNT(*) FROM states s JOIN states_meta m ON m.metadata_id = s.metadata_id "
            "WHERE s.last_updated_ts >= ? GROUP BY m.entity_id ORDER BY 2 DESC",
            (since,),
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {e: int(c) for e, c in rows if e}


def attribute_bytes(conn: sqlite3.Connection, time_limit: float = ATTR_TIME_LIMIT, progress_ops: int = 10000) -> dict[str, int] | None:
    """Raw size of the distinct attribute blobs each entity points to (attributes are shared between states).

    Returns None when the schema has no attribute table or the query ran past `time_limit` (it is aborted, so a
    huge database on slow storage never blocks the panel).
    """
    deadline = time.monotonic() + time_limit
    try:
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, progress_ops)
        rows = conn.execute(
            "SELECT m.entity_id, SUM(LENGTH(a.shared_attrs)) FROM "
            "(SELECT DISTINCT metadata_id, attributes_id FROM states WHERE attributes_id IS NOT NULL) d "
            "JOIN state_attributes a ON a.attributes_id = d.attributes_id "
            "JOIN states_meta m ON m.metadata_id = d.metadata_id GROUP BY m.entity_id"
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.set_progress_handler(None, 0)
    return {e: int(b or 0) for e, b in rows if e}


def estimate_entity_bytes(stats: dict[str, Any]) -> dict[str, int]:
    """Approximate bytes per entity: its share of the states table plus its (scaled) attribute blobs.

    An estimate, not an exact figure: shared attribute rows and index overhead are spread out proportionally.
    """
    counts: dict[str, int] = stats.get("entity_counts") or {}
    total = int(stats.get("total_records") or 0)
    if not counts or not total:
        return {}
    tables = {t["name"]: int(t["bytes"]) for t in (stats.get("tables") or [])}
    states_bytes = tables.get("states") or int((stats.get("db_size_bytes") or 0) * 0.5)
    per_record = states_bytes / total
    attrs: dict[str, int] = stats.get("attr_bytes") or {}
    raw = sum(attrs.values())
    attr_table = tables.get("state_attributes")
    scale = (attr_table / raw) if attr_table and raw else 1.0
    return {e: int(c * per_record + attrs.get(e, 0) * scale) for e, c in counts.items()}


def estimate_daily_bytes(stats: dict[str, Any], sizes: dict[str, int]) -> int:
    """Approximate bytes the database takes in per day at the current ingest rate (records of the last 24 h)."""
    counts: dict[str, int] = stats.get("entity_counts") or {}
    total = 0.0
    for eid, n in (stats.get("recent_counts") or {}).items():
        have = counts.get(eid)
        if have:
            total += sizes.get(eid, 0) / have * n
    return int(total)


def analyze(db_path: Path, full: bool = True, attrs: bool = False) -> dict[str, Any]:
    """Per-entity state counts. Opens the database strictly read-only.

    `full=False` skips the per-table sizes and free space (they read every page of the file), so it is cheap enough
    to run repeatedly; the caller keeps the previous values for those. `attrs=True` also measures the attribute
    size per entity (slow on big databases, time-limited, so only asked for now and then).
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "states_meta" in tables:
            sql = (
                "SELECT m.entity_id, COUNT(*) FROM states s "
                "JOIN states_meta m ON m.metadata_id = s.metadata_id "
                "GROUP BY m.entity_id ORDER BY 2 DESC"
            )
        else:
            sql = "SELECT entity_id, COUNT(*) FROM states GROUP BY entity_id ORDER BY 2 DESC"
        counts = {e: c for e, c in conn.execute(sql) if e}
        recent = recent_counts(conn)
        tables = table_sizes(conn) if full else None
        free = free_bytes(conn) if full else None
        attr = attribute_bytes(conn) if (full and attrs) else None
    finally:
        conn.close()
    return {
        "entity_counts": counts,
        "total_records": sum(counts.values()),
        "db_path": str(db_path),
        "db_size_bytes": total_size_bytes(db_path),
        "files": file_sizes(db_path),
        "tables": tables,
        "free_bytes": free,
        "recent_counts": recent,
        "recent_total": sum(recent.values()),
        "attr_bytes": attr,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }


def summarize(stats: dict[str, Any], excluded: list[str], known_entities: set[str]) -> dict[str, Any]:
    """Derive the dashboard numbers from raw counts.

    obsolete = records that still sit in the database for entities that are now excluded
    orphans  = excluded entity ids that no longer exist anywhere in Home Assistant
    """
    counts: dict[str, int] = stats.get("entity_counts", {})
    total = int(stats.get("total_records", 0))
    obsolete = sum(counts.get(e, 0) for e in excluded)
    matched = [e for e in excluded if e in counts]
    orphans = sorted(e for e in excluded if e not in known_entities and e not in counts)
    return {
        "total_records": total,
        "current_records": total - obsolete,
        "obsolete_records": obsolete,
        "excluded_with_records": len(matched),
        "orphan_exclusions": orphans,
        "entity_count": len(counts),
        "db_size_bytes": stats.get("db_size_bytes", 0),
        "tables": stats.get("tables", []),
        "free_bytes": stats.get("free_bytes", 0),
        "db_path": stats.get("db_path"),
        "generated_at": stats.get("generated_at"),
        "error": stats.get("error"),
        "top_entities": [[e, c, round(c * 100 / total, 2) if total else 0.0] for e, c in list(counts.items())[:15]],
        "top_sizes": _top_sizes(stats),
        "recent_total": int(stats.get("recent_total") or 0),
        "top_recent": [[e, c] for e, c in list((stats.get("recent_counts") or {}).items())[:10]],
        "has_attr_sizes": stats.get("attr_bytes") is not None,
    }


def _top_sizes(stats: dict[str, Any], n: int = 15) -> list[list[Any]]:
    sizes = estimate_entity_bytes(stats)
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])[:n]
    return [[e, b, round(b * 100 / total, 2)] for e, b in ranked]


def estimate_impact(stats: dict[str, Any], entity_ids: list[str]) -> dict[str, Any]:
    """Rough impact of purging the given entities, for confirmation dialogs."""
    counts = stats.get("entity_counts", {})
    records = sum(counts.get(e, 0) for e in entity_ids)
    total = max(int(stats.get("total_records", 0)), 1)
    return {
        "entities": len(entity_ids),
        "records": records,
        "approx_bytes": int(stats.get("db_size_bytes", 0) * records / total),
    }
