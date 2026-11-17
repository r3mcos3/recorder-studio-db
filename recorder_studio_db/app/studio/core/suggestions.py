"""Suggestions for entities worth excluding from the recorder (pure Python, heuristic)."""
from __future__ import annotations

import re
from typing import Any

# Only these domains are ever suggested. Lights, switches, climate, locks, covers, alarms, persons, trackers and
# the like are deliberately left out: their history is what people usually want to keep.
SUGGEST_DOMAINS = {"sensor", "binary_sensor", "update", "number", "select", "text", "button", "event", "image", "sun"}
NOISY = re.compile(r"(uptime|linkquality|link_quality|\blqi\b|rssi|signal|last_seen|last_boot|last_restart|ssid|bssid|ip_address|mac_address|wifi)")
CHATTY = re.compile(r"(voltage|frequency|current|power_factor|load|cpu|memory|ping|latency|jitter|throughput|packets|download|upload|_rx|_tx)")
# Entities of these device classes feed the Energy dashboard or other long-term views: never suggested on size alone.
KEEP_CLASSES = {"energy", "gas", "water", "monetary", "battery", "temperature", "humidity", "carbon_dioxide", "pm25", "pm10", "pressure"}
STATS_CLASSES = {"measurement", "total", "total_increasing"}

MAX_SUGGESTIONS = 12
MIN_SHARE = 0.05  # percent of the database below which a suggestion is not worth showing


def suggest(
    entities: list[dict[str, Any]],
    stats: dict[str, Any],
    sizes: dict[str, int],
    excluded: set[str],
    dismissed: set[str],
    limit: int = MAX_SUGGESTIONS,
) -> dict[str, Any]:
    """entities: {entity_id, name, device, category, state_class, device_class}. Returns the ranked candidates."""
    counts: dict[str, int] = stats.get("entity_counts") or {}
    recent: dict[str, int] = stats.get("recent_counts") or {}
    total = int(stats.get("total_records") or 0)
    total_bytes = sum(sizes.values()) or 1
    out: list[dict[str, Any]] = []
    for ent in entities:
        eid = ent["entity_id"]
        domain = eid.split(".", 1)[0]
        if eid in excluded or eid in dismissed or domain not in SUGGEST_DOMAINS or not counts.get(eid):
            continue
        share = counts[eid] * 100 / total if total else 0.0
        if share < MIN_SHARE:
            continue
        text = f"{eid} {(ent.get('name') or '').lower()}".lower()
        diagnostic = ent.get("category") == "diagnostic"
        reasons: list[str] = []
        score = 0
        if diagnostic:
            reasons.append("Diagnostic entity")
            score += 2
        if NOISY.search(text):
            reasons.append("Name suggests technical noise (signal, uptime, …)")
            score += 2
        elif CHATTY.search(text):
            reasons.append("Name suggests a rapidly changing value")
            score += 1
        if share >= 3:
            score += 2
        elif share >= 1:
            score += 1
        per_day = recent.get(eid, 0)
        if per_day >= 2000:
            score += 1
        if score < 3:
            continue
        has_stats = (ent.get("state_class") in STATS_CLASSES) and not diagnostic
        keep_class = ent.get("device_class") in KEEP_CLASSES and not diagnostic
        if keep_class and not NOISY.search(text):
            continue  # temperature, energy, battery… are the data people want to look back at
        reasons.append(f"{share:.1f}% of the database" if share >= 0.1 else "Small share of the database")
        if per_day:
            reasons.append(f"{per_day:,} records in the last 24 h")
        warn = ""
        if has_stats:
            warn = "Has long-term statistics: excluding it stops those too (and any Energy dashboard use)."
        out.append(
            {
                "entity_id": eid,
                "name": ent.get("name") or eid,
                "device": ent.get("device") or "",
                "records": counts[eid],
                "bytes": sizes.get(eid, 0),
                "percent": round(share, 2),
                "per_day": per_day,
                "reasons": reasons,
                "warn": warn,
                "confidence": "check" if warn else "high",
                "_score": (0 if warn else 1, sizes.get(eid, 0)),
            }
        )
    out.sort(key=lambda s: s["_score"], reverse=True)
    top = out[:limit]
    for s in top:
        s.pop("_score", None)
    saved = sum(s["bytes"] for s in top if not s["warn"])
    return {
        "items": top,
        "total_found": len(out),
        "save_bytes": saved,
        "save_percent": round(saved * 100 / total_bytes, 1),
        "dismissed": len(dismissed),
    }
