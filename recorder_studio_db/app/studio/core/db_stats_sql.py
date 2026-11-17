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
        "recent_counts": recent,
        "recent_total": sum(recent.values()),
        "attr_bytes": attr,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }
