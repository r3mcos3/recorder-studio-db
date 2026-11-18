"""Read-only statistics for PostgreSQL and MariaDB (modern recorder schema: states + states_meta).

Pure Python: takes a DB-API connection (psycopg2 / pymysql), so it is unit-testable against real servers in CI.
Only SELECT/SET statements are issued.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable

RECENT_SECONDS = 86400
ATTR_TIME_LIMIT = 20  # seconds

COUNT_SQL = "SELECT m.entity_id, COUNT(*) FROM states s JOIN states_meta m ON m.metadata_id = s.metadata_id GROUP BY m.entity_id ORDER BY 2 DESC"
RECENT_SQL = (
    "SELECT m.entity_id, COUNT(*) FROM states s JOIN states_meta m ON m.metadata_id = s.metadata_id "
    "WHERE s.last_updated_ts >= %s GROUP BY m.entity_id ORDER BY 2 DESC"
)
ATTR_SQL = (
    "SELECT m.entity_id, SUM(LENGTH(a.shared_attrs)) FROM "
    "(SELECT DISTINCT metadata_id, attributes_id FROM states WHERE attributes_id IS NOT NULL) d "
    "JOIN state_attributes a ON a.attributes_id = d.attributes_id "
    "JOIN states_meta m ON m.metadata_id = d.metadata_id GROUP BY m.entity_id"
)

TABLES_SQL = {
    "postgresql": (
        "SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relkind = 'r' AND n.nspname = current_schema()"
    ),
    "mariadb": "SELECT table_name, data_length + index_length FROM information_schema.tables WHERE table_schema = DATABASE()",
}
DBSIZE_SQL = {
    "postgresql": "SELECT pg_database_size(current_database())",
    "mariadb": "SELECT COALESCE(SUM(data_length + index_length), 0) FROM information_schema.tables WHERE table_schema = DATABASE()",
}
FREE_SQL = {
    "postgresql": None,  # dead tuples are reclaimed by autovacuum; there is no file-level "unused space" figure to show
    "mariadb": "SELECT COALESCE(SUM(data_free), 0) FROM information_schema.tables WHERE table_schema = DATABASE()",
}
VERSION_SQL = {"postgresql": "SHOW server_version", "mariadb": "SELECT VERSION()"}
TIMEOUT_SQL = {
    "postgresql": "SET statement_timeout = %d" % (ATTR_TIME_LIMIT * 1000),
    "mariadb": "SET SESSION max_statement_time = %d" % ATTR_TIME_LIMIT,
}


def _rows(conn, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return list(cur.fetchall())
    finally:
        cur.close()


def _scalar(conn, sql: str):
    rows = _rows(conn, sql)
    return rows[0][0] if rows else None


def version(conn, dialect: str) -> str:
    return str(_scalar(conn, VERSION_SQL[dialect]))


def db_size(conn, dialect: str) -> int:
    return int(_scalar(conn, DBSIZE_SQL[dialect]) or 0)


def table_sizes(conn, dialect: str) -> list[dict[str, Any]]:
    out = [{"name": n, "bytes": int(b or 0)} for n, b in _rows(conn, TABLES_SQL[dialect])]
    return sorted((t for t in out if t["bytes"]), key=lambda t: -t["bytes"])


ROW_TABLES = ("states", "events", "state_attributes", "event_data", "statistics", "statistics_short_term")
ROWS_SQL = {  # estimates from the catalog: an exact COUNT(*) of millions of rows is not worth it every few minutes
    "postgresql": (
        "SELECT c.relname, GREATEST(c.reltuples, 0)::bigint FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relkind = 'r' AND n.nspname = current_schema()"
    ),
    "mariadb": "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE()",
}
DEAD_SQL = "SELECT COALESCE(SUM(n_dead_tup), 0), COALESCE(SUM(n_live_tup), 0) FROM pg_stat_user_tables WHERE schemaname = current_schema()"


def extras(conn, dialect: str) -> dict[str, Any]:
    """Estimated rows per table, age of the history and (PostgreSQL) the share of dead tuples. Each part may fail alone."""
    out: dict[str, Any] = {"table_rows": {}, "oldest_ts": None, "dead_ratio": None, "rows_estimated": True}
    try:
        out["table_rows"] = {str(n): int(r or 0) for n, r in _rows(conn, ROWS_SQL[dialect]) if str(n) in ROW_TABLES}
    except Exception:  # noqa: BLE001
        _rollback(conn)
    try:
        v = _scalar(conn, "SELECT MIN(last_updated_ts) FROM states")
        out["oldest_ts"] = float(v) if v is not None else None
    except Exception:  # noqa: BLE001
        _rollback(conn)
    if dialect == "postgresql":
        try:
            dead, live = _rows(conn, DEAD_SQL)[0]
            total = float(dead or 0) + float(live or 0)
            out["dead_ratio"] = float(dead or 0) / total if total else 0.0
        except Exception:  # noqa: BLE001
            _rollback(conn)
    return out


def latest_ts(conn) -> float | None:
    """Newest states.last_updated_ts: tells whether Home Assistant is currently writing into this database."""
    try:
        v = _scalar(conn, "SELECT MAX(last_updated_ts) FROM states")
    except Exception:  # noqa: BLE001 - table not there yet (fresh database)
        _rollback(conn)
        return None
    return float(v) if v is not None else None


def _rollback(conn) -> None:
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001
        pass


def analyze(connect: Callable[[], Any], dialect: str, label: str, full: bool = True, attrs: bool = False, now_ts: float | None = None) -> dict[str, Any]:
    """Same result shape as db_stats.analyze() (SQLite): counts, recent counts, table sizes, optional attribute sizes."""
    conn = connect()
    try:
        counts = {e: int(c) for e, c in _rows(conn, COUNT_SQL) if e}
        since = (now_ts if now_ts is not None else time.time()) - RECENT_SECONDS
        recent = {e: int(c) for e, c in _rows(conn, RECENT_SQL, (since,)) if e}
        tables = table_sizes(conn, dialect) if full else None
        extra = extras(conn, dialect) if full else None
        free = None
        if full:
            free = int(_scalar(conn, FREE_SQL[dialect]) or 0) if FREE_SQL[dialect] else 0
        attr = None
        if full and attrs:
            try:
                cur = conn.cursor()
                cur.execute(TIMEOUT_SQL[dialect])
                cur.close()
                attr = {e: int(b or 0) for e, b in _rows(conn, ATTR_SQL) if e}
            except Exception:  # noqa: BLE001 - timed out or no attribute table: keep the previous result
                _rollback(conn)
                attr = None
        size = db_size(conn, dialect)
        ver = version(conn, dialect) if full else None
    finally:
        conn.close()
    return {
        "entity_counts": counts,
        "total_records": sum(counts.values()),
        "db_path": label,
        "db_size_bytes": size,
        "files": {"db": size, "wal": 0, "shm": 0, "total": size},
        "tables": tables,
        "free_bytes": free,
        "extra": extra,
        "version": ver,
        "recent_counts": recent,
        "recent_total": sum(recent.values()),
        "attr_bytes": attr,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }
