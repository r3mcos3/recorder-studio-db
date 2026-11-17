"""Daily size/ingest snapshots and the growth trend derived from them (pure Python)."""
from __future__ import annotations

from datetime import date
from typing import Any

MAX_POINTS = 400  # about 13 months of daily snapshots
CHART_POINTS = 60


def record_snapshot(history: list[dict[str, Any]], day: str, size: int, records: int, recent: int) -> tuple[list[dict[str, Any]], bool]:
    """Upsert today's snapshot. Returns (history, is_new_day)."""
    entry = {"d": day, "size": int(size), "records": int(records), "recent": int(recent)}
    history = [h for h in history if isinstance(h, dict) and "d" in h]
    if history and history[-1]["d"] == day:
        history[-1] = entry
        return history, False
    history.append(entry)
    return history[-MAX_POINTS:], True


def _ordinal(day: str) -> int:
    return date.fromisoformat(day).toordinal()


def trend(history: list[dict[str, Any]], free_bytes: int | None = None, window: int = 14) -> dict[str, Any]:
    """Size history for the chart plus a least-squares growth rate over the last `window` snapshots.

    The size of a SQLite file only moves when it needs more pages, so a flat line means "stable"; the forecast
    (days until the disk is full) is only given while the file is really growing and there are enough points.
    """
    pts = [h for h in history if h.get("size")]
    out: dict[str, Any] = {
        "points": [{"d": h["d"], "size": h["size"]} for h in pts[-CHART_POINTS:]],
        "growth_per_day": None,
        "days_to_full": None,
        "days_covered": 0,
    }
    recent = pts[-window:]
    if len(recent) < 3:
        return out
    xs = [_ordinal(h["d"]) for h in recent]
    span = xs[-1] - xs[0]
    out["days_covered"] = span
    if span < 2:
        return out
    ys = [h["size"] for h in recent]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
    out["growth_per_day"] = int(slope)
    if free_bytes and slope > 0:
        out["days_to_full"] = int(free_bytes / slope)
    return out


def growth_over(history: list[dict[str, Any]], days: int = 7) -> float | None:
    """Percentage the database grew compared with the newest snapshot that is at least `days - 2` days old."""
    pts = [h for h in history if h.get("size")]
    if len(pts) < 2:
        return None
    now = _ordinal(pts[-1]["d"])
    base = None
    for h in pts[:-1]:
        age = now - _ordinal(h["d"])
        if days - 2 <= age <= days + 7:
            base = h  # keep the newest one inside the window
    if not base or not base["size"]:
        return None
    return (pts[-1]["size"] - base["size"]) * 100 / base["size"]
