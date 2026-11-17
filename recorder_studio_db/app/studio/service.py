"""Studio logic: the former Home Assistant glue, running in the add-on and talking to Core over the Supervisor API."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from pathlib import Path
import shutil
import time
from typing import Any

from . import store
from .const import ATTR_REFRESH_SECONDS, CONFIG_DIR, CONFIG_FILE, GENERATED_FILE, LEGACY_FILE, STORE_FILE
from .core import alerts, db_stats, history, suggestions, tree, yaml_writer
from .ha import HAClient, HAError

_LOGGER = logging.getLogger(__name__)
ALERT_IDS = ("disk_low", "disk_filling", "db_growth")
ALERT_TEXT = {
    "disk_low": ("Disk space is running low", "Only {free} ({percent}%) is left on the disk that holds the Home Assistant database ({database}). Free up space, for example by excluding noisy entities or lowering the retention in Recorder Studio, then repack the database."),
    "disk_filling": ("The database is filling the disk", "At the current growth the disk (free: {free}, database: {database}) is full in about {days} days. Exclude noisy entities in Recorder Studio or lower the retention."),
    "db_growth": ("The database is growing fast", "The recorder database grew {percent}% in the last week (now {database}). Open Recorder Studio to see which entities add the most."),
}


class Studio:
    def __init__(self, ha: HAClient, config_dir: Path = CONFIG_DIR, store_path: Path = STORE_FILE) -> None:
        self.ha, self.config_dir, self.store_path = ha, Path(config_dir), Path(store_path)
        self.data: dict[str, Any] = store.load(self.store_path)
        self.pending_restart = False
        self.active_alerts: list[str] = []
        self._rows: list[dict[str, Any]] = []
        self._names: dict[str, str] = {}
        self._known: set[str] = set()

    # ---- persistence -------------------------------------------------
    async def save(self) -> None:
        self.data = store.merge(self.data)
        await asyncio.to_thread(store.save, self.store_path, self.data)

    def generated_path(self) -> Path:
        return self.config_dir / GENERATED_FILE

    async def write_yaml(self) -> None:
        d = self.data
        content = yaml_writer.render_yaml(d["options"], d["excluded_entities"], d["rescued_entities"], d["rules_text"])
        await asyncio.to_thread(yaml_writer.atomic_write, self.generated_path(), content)

    async def persist(self) -> None:
        """Save our settings and regenerate the YAML file (a Home Assistant restart applies it)."""
        await self.save()
        await self.write_yaml()
        self.pending_restart = True

    # ---- database ----------------------------------------------------
    def db_path(self) -> Path:
        return db_stats.resolve_db_path(str(self.config_dir), None)

    async def analyze(self, full: bool = True) -> dict[str, Any]:
        path = self.db_path()
        d = self.data
        previous = d.get("stats") or {}
        now = time.time()
        want_attrs = full and now - float(previous.get("attr_tried") or 0) > ATTR_REFRESH_SECONDS
        save = full
        try:
            stats = await asyncio.to_thread(db_stats.analyze, path, full, want_attrs)
            if full:
                stats["full_at"] = stats["generated_at"]
                stats["attr_tried"] = now if want_attrs else previous.get("attr_tried")
                if stats.get("attr_bytes") is None:
                    stats["attr_bytes"] = previous.get("attr_bytes")
            else:
                for key in ("tables", "free_bytes", "full_at", "attr_bytes", "attr_tried"):
                    stats[key] = previous.get(key)
                stats["tables"] = stats["tables"] or []
                stats["free_bytes"] = stats["free_bytes"] or 0
            d["history"], new_day = history.record_snapshot(
                d.get("history") or [], datetime.now().date().isoformat(), stats["db_size_bytes"], stats["total_records"], stats.get("recent_total", 0)
            )
            save = save or new_day
        except Exception as err:  # noqa: BLE001
            stats = {"entity_counts": {}, "total_records": 0, "db_path": str(path), "db_size_bytes": 0, "generated_at": None, "error": str(err)}
        d["stats"] = stats
        if save:
            await self.save()
        return stats

    # ---- entities ----------------------------------------------------
    async def refresh_entities(self) -> None:
        """Entity and device registry plus current states (cached a minute by the client)."""
        try:
            ents = await self.ha.ws("config/entity_registry/list")
            devs = await self.ha.ws("config/device_registry/list")
            states = {s["entity_id"]: s for s in await self.ha.states()}
        except (HAError, OSError) as err:
            _LOGGER.warning("Cannot read Home Assistant registries: %s", err)
            return
        seen: dict[str, dict[str, Any]] = {}
        for e in ents:
            st = states.get(e["entity_id"])
            seen[e["entity_id"]] = {
                "entity_id": e["entity_id"],
                "name": e.get("name") or e.get("original_name") or e["entity_id"],
                "device_id": e.get("device_id"),
                "platform": e.get("platform") or "",
                "category": e.get("entity_category"),
                "device_class": e.get("device_class") or e.get("original_device_class"),
                "state_class": (st or {}).get("attributes", {}).get("state_class"),
            }
        for eid, s in states.items():
            a = s.get("attributes", {})
            seen.setdefault(eid, {"entity_id": eid, "name": a.get("friendly_name") or eid, "device_id": None, "platform": "", "category": None,
                                  "device_class": a.get("device_class"), "state_class": a.get("state_class")})
        self._rows = list(seen.values())
        self._names = {d["id"]: (d.get("name_by_user") or d.get("name") or "") for d in devs}
        self._known = set(seen)

    def known_entity_ids(self) -> set[str]:
        return self._known

    def entity_sizes(self) -> dict[str, int]:
        return db_stats.estimate_entity_bytes(self.data.get("stats") or {})

    def build_tree(self) -> list[dict[str, Any]]:
        devices = [{"id": i, "name": n} for i, n in self._names.items()]
        stats = self.data.get("stats") or {}
        return tree.build_tree(devices, self._rows, set(self.data["excluded_entities"]), stats.get("entity_counts", {}), stats.get("total_records"), self.entity_sizes())

    def build_suggestions(self) -> dict[str, Any]:
        d = self.data
        stats = d.get("stats") or {}
        if not stats.get("entity_counts"):
            return {"items": [], "total_found": 0, "save_bytes": 0, "save_percent": 0.0, "dismissed": len(d["dismissed"])}
        rows = [{**r, "device": self._names.get(r.get("device_id"), "")} for r in self._rows]
        return suggestions.suggest(rows, stats, self.entity_sizes(), set(d["excluded_entities"]), set(d["dismissed"]))

    def summary(self) -> dict[str, Any] | None:
        stats = self.data.get("stats")
        if not stats:
            return None
        return db_stats.summarize(stats, self.data["excluded_entities"], self.known_entity_ids())

    def need_stats(self) -> dict[str, Any]:
        return self.data.get("stats") or {"entity_counts": {}, "total_records": 0, "db_size_bytes": 0}

    # ---- growth / alerts ---------------------------------------------
    async def disk(self) -> tuple[int | None, int | None]:
        def _usage():
            try:
                u = shutil.disk_usage(self.db_path().parent)
                return u.total, u.free
            except OSError:
                return None, None

        return await asyncio.to_thread(_usage)

    async def growth(self) -> dict[str, Any]:
        stats = self.data.get("stats") or {}
        total, free = await self.disk()
        info = history.trend(self.data.get("history") or [], free)
        info.update(
            recent_total=int(stats.get("recent_total") or 0),
            bytes_per_day=db_stats.estimate_daily_bytes(stats, self.entity_sizes()),
            disk_total=total, disk_free=free, snapshots=len(self.data.get("history") or []),
        )
        return info

    async def check_alerts(self) -> list[dict[str, Any]]:
        """Raise or clear persistent notifications for low disk space and fast growth."""
        stats = self.data.get("stats") or {}
        if stats.get("error") or not stats.get("db_size_bytes"):
            return []
        total, free = await self.disk()
        issues = alerts.evaluate(self.data["alerts"], db_size=stats["db_size_bytes"], disk_total=total, disk_free=free, history=self.data.get("history") or [])
        active = {i["id"] for i in issues}
        try:
            for issue in issues:
                title, text = ALERT_TEXT[issue["id"]]
                await self.ha.call_service("persistent_notification", "create", {
                    "notification_id": f"recorder_studio_{issue['id']}", "title": f"Recorder Studio: {title}", "message": text.format(**issue["placeholders"])})
            for issue_id in ALERT_IDS:
                if issue_id not in active:
                    await self.ha.call_service("persistent_notification", "dismiss", {"notification_id": f"recorder_studio_{issue_id}"})
        except HAError as err:
            _LOGGER.warning("Could not update alert notifications: %s", err)
        self.active_alerts = sorted(active)
        return issues

    async def backup_status(self) -> dict[str, Any]:
        try:
            dates = await self.ha.backups()
        except Exception:  # noqa: BLE001 - never block a purge on this
            return {"known": False}
        return {"known": True, **alerts.backup_age(dates)}

    async def background_check(self) -> None:
        await self.analyze(full=False)
        await self.save()
        await self.check_alerts()


__all__ = ["Studio", "CONFIG_FILE", "LEGACY_FILE"]
