"""Health checks for the database (disk space, growth) and the age of the newest backup (pure Python)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import history as hist

DEFAULT_ALERTS = {"enabled": True, "free_percent": 10, "growth_percent": 25}
FILLING_DAYS = 30


def fmt_bytes(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024 or unit == "TB":
            return f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def evaluate(cfg: dict[str, Any], *, db_size: int, disk_total: int | None, disk_free: int | None, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the issues that are active right now: [{id, severity, placeholders}]."""
    issues: list[dict[str, Any]] = []
    if not cfg.get("enabled", True):
        return issues
    if disk_total and disk_free is not None:
        pct = disk_free * 100 / disk_total
        days = hist.trend(history, disk_free)["days_to_full"]
        if pct < cfg["free_percent"]:
            issues.append(
                {
                    "id": "disk_low",
                    "severity": "error" if pct < cfg["free_percent"] / 2 else "warning",
                    "placeholders": {"free": fmt_bytes(disk_free), "percent": f"{pct:.0f}", "database": fmt_bytes(db_size)},
                }
            )
        elif days is not None and days <= FILLING_DAYS:
            issues.append({"id": "disk_filling", "severity": "warning", "placeholders": {"days": str(days), "free": fmt_bytes(disk_free), "database": fmt_bytes(db_size)}})
    growth = hist.growth_over(history, 7)
    if growth is not None and growth >= cfg["growth_percent"]:
        issues.append({"id": "db_growth", "severity": "warning", "placeholders": {"percent": f"{growth:.0f}", "database": fmt_bytes(db_size)}})
    return issues


def backup_age(dates: list[str], now: datetime | None = None) -> dict[str, Any]:
    """Newest backup out of ISO date strings: {"last": iso|None, "age_hours": float|None, "count": n}."""
    now = now or datetime.now(timezone.utc)
    parsed: list[datetime] = []
    for raw in dates:
        try:
            d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        parsed.append(d if d.tzinfo else d.replace(tzinfo=timezone.utc))
    if not parsed:
        return {"last": None, "age_hours": None, "count": 0}
    newest = max(parsed)
    return {"last": newest.isoformat(), "age_hours": max(0.0, (now - newest).total_seconds() / 3600), "count": len(parsed)}
