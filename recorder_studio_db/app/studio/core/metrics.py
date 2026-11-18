"""Turns the database statistics into the figures shown in the panel and exposed as Home Assistant sensors.

Pure Python. Every value is optional: when an engine cannot tell (e.g. the dead-tuple share on SQLite) it is None and the
sensor shows as unavailable instead of a made-up number.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

STATISTICS_TABLES = ("statistics", "statistics_short_term", "statistics_meta", "statistics_runs")
EVENT_TABLES = ("events", "event_data", "event_types")
ATTRIBUTE_TABLES = ("state_attributes",)


def _sum(tables: dict[str, int], names: tuple[str, ...]) -> int | None:
    found = [tables[n] for n in names if n in tables]
    return sum(found) if found else None


def fragmentation(stats: dict[str, Any]) -> tuple[float | None, int | None]:
    """(percent, reclaimable bytes). SQLite/MariaDB: free space inside the files; PostgreSQL: share of dead tuples."""
    extra = stats.get("extra") or {}
    size = int(stats.get("db_size_bytes") or 0)
    if extra.get("dead_ratio") is not None:
        ratio = float(extra["dead_ratio"])
        return round(ratio * 100, 1), int(size * ratio) if size else None
    free = stats.get("free_bytes")
    if free is None or not size:
        return None, None
    return round(int(free) * 100 / size, 1), int(free)


def build(stats: dict[str, Any], growth: dict[str, Any], engine: str, version: str | None = None) -> dict[str, Any]:
    """{"sensors": flat values for Home Assistant, "tables": rows for the panel, "engine": ..., "generated_at": ...}."""
    stats = stats or {}
    growth = growth or {}
    extra = stats.get("extra") or {}
    sizes = {t["name"]: int(t["bytes"]) for t in (stats.get("tables") or [])}
    rows = {k: int(v) for k, v in (extra.get("table_rows") or {}).items()}
    percent, reclaimable = fragmentation(stats)
    oldest = extra.get("oldest_ts")
    per_day = growth.get("growth_per_day")
    if per_day is None:
        per_day = growth.get("bytes_per_day") or None
    total = int(stats.get("db_size_bytes") or 0)
    sensors = {
        "engine": f"{engine} {version}".strip() if version else engine,
        "database_size": total or None,
        "states_size": sizes.get("states"),
        "attributes_size": _sum(sizes, ATTRIBUTE_TABLES),
        "events_size": _sum(sizes, EVENT_TABLES),
        "statistics_size": _sum(sizes, STATISTICS_TABLES),
        "states_count": rows.get("states") if rows.get("states") is not None else (stats.get("total_records") or None),
        "events_count": rows.get("events"),
        "statistics_count": _sum(rows, ("statistics", "statistics_short_term")),
        "records_per_day": stats.get("recent_total"),
        "oldest_record": datetime.fromtimestamp(oldest, timezone.utc).isoformat() if oldest else None,
        "growth_per_day": int(per_day) if per_day else None,
        "fragmentation": percent,
        "reclaimable": reclaimable,
        "disk_free": growth.get("disk_free"),
        "days_to_full": growth.get("days_to_full"),
    }
    table_list = [
        {"name": n, "bytes": b, "rows": rows.get(n), "share": round(b * 100 / total, 1) if total else None}
        for n, b in sorted(sizes.items(), key=lambda kv: -kv[1])
    ]
    return {
        "sensors": sensors,
        "tables": table_list,
        "rows_estimated": bool(extra.get("rows_estimated")),
        "fragmentation_kind": "dead_tuples" if extra.get("dead_ratio") is not None else "free_space",
        "generated_at": stats.get("generated_at"),
    }
