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
from .const import ACTIVE_WINDOW, ENGINES, ATTR_REFRESH_SECONDS, CONFIG_DIR, CONFIG_FILE, DATA_DIR, DEFAULT_SQLITE_FILE, GENERATED_FILE, LEGACY_FILE, STORE_FILE, addon_options, sqlite_file
from . import engines, integration as bundled
from .core import history_copy, alerts, db_stats, db_stats_sql, history, suggestions, tree, yaml_writer
from .ha import HAClient, HAError

_LOGGER = logging.getLogger(__name__)
ALERT_IDS = ("disk_low", "disk_filling", "db_growth")
ALERT_TEXT = {
    "disk_low": ("Disk space is running low", "Only {free} ({percent}%) is left on the disk that holds the Home Assistant database ({database}). Free up space, for example by excluding noisy entities or lowering the retention in Recorder Studio, then repack the database."),
    "disk_filling": ("The database is filling the disk", "At the current growth the disk (free: {free}, database: {database}) is full in about {days} days. Exclude noisy entities in Recorder Studio or lower the retention."),
    "db_growth": ("The database is growing fast", "The recorder database grew {percent}% in the last week (now {database}). Open Recorder Studio to see which entities add the most."),
}


class Studio:
    def __init__(self, ha: HAClient, config_dir: Path = CONFIG_DIR, store_path: Path = STORE_FILE, server: engines.DatabaseServer | None = None) -> None:
        self.ha, self.config_dir, self.store_path = ha, Path(config_dir), Path(store_path)
        self.server = server
        self.backend = "sqlite"  # "sql" while Home Assistant writes into the add-on's PostgreSQL/MariaDB
        self.data: dict[str, Any] = store.load(self.store_path)
        url = self.data.get("options", {}).get("db_url")
        if isinstance(url, str) and url.startswith("mysql+pymysql://"):  # 0.3.0 wrote a driver Home Assistant does not ship
            self.data["options"]["db_url"] = "mysql://" + url[len("mysql+pymysql://"):]
        self.pending_restart = False
        self.live: dict[str, Any] | None = None
        self.integration_checked = 0.0  # time.monotonic() of the last check of the bundled integration
        self.integration: dict[str, Any] = {"state": "unknown", "version": bundled.source_version(), "loaded": None, "message": None}
        self.copy_progress = history_copy.Progress()
        self._copy_task: asyncio.Task | None = None
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

    async def persist(self) -> dict[str, Any]:
        """Save our settings, regenerate the YAML file and have Home Assistant apply it to the running recorder.

        That needs the Recorder Studio integration (service recorder_studio.apply_config). Without it, or for settings the
        recorder reads at start-up only (db_url, commit_interval), a Home Assistant restart is still needed.
        """
        await self.save()
        await self.write_yaml()
        return await self.apply_live()

    async def _call_apply(self) -> dict[str, Any] | None:
        """Ask Home Assistant (our bundled integration) to apply recorder_studio.yaml; None when it is not running."""
        try:
            result = await self.ha.call_service_response(bundled.DOMAIN, "apply_config")
        except HAError as err:
            if "not found" not in str(err):
                raise
            return None
        return result if isinstance(result, dict) else None

    async def apply_live(self) -> dict[str, Any]:
        try:
            result = await self._call_apply()
            if result is None:
                raise HAError("recorder_studio_db.apply_config: service not found")
        except HAError as err:
            _LOGGER.info("Live apply not possible (%s); a Home Assistant restart is needed", err)
            reason = "integration_missing" if "not found" in str(err) else str(err)
            result = {"applied": False, "restart": ["all"], "changed": [], "reason": reason}
        self.live = result
        self.pending_restart = bool(result.get("restart"))
        return result

    # ---- the bundled Home Assistant integration -----------------------
    async def ensure_integration(self) -> dict[str, Any]:
        """Install the bundled integration, make sure Home Assistant runs it, and report what is still needed.

        state: ready | restart_needed | error. Raises HAError when Home Assistant cannot be reached (callers retry).
        """
        info = self.integration
        self.integration_checked = time.monotonic()
        info["version"] = bundled.source_version()
        try:
            await asyncio.to_thread(bundled.install, self.config_dir)
        except OSError as err:
            info.update(state="error", message=f"Could not install the integration into {self.config_dir}/custom_components: {err}")
            return info
        loaded = await self._loaded_integration_version()
        if loaded is None:
            try:
                flow = await self.ha.start_config_flow(bundled.DOMAIN)
            except HAError as err:
                _LOGGER.info("integration not known to Home Assistant yet (%s)", err)
                flow = {}
            if flow.get("type") == "create_entry":
                for _ in range(10):
                    loaded = await self._loaded_integration_version()
                    if loaded:
                        break
                    await asyncio.sleep(1)
        info["loaded"] = loaded
        if loaded == info["version"]:
            info.update(state="ready", message=None)
        elif loaded:
            info.update(state="restart_needed", message=f"Home Assistant runs version {loaded}, {info['version']} is installed. Restart Home Assistant to load it.")
        else:
            info.update(state="restart_needed", message="Restart Home Assistant once to load the Recorder Studio DB integration.")
        return info

    async def _loaded_integration_version(self) -> str | None:
        """The version Home Assistant runs, or None when it has not loaded the integration."""
        try:
            result = await self.ha.call_service_response(bundled.DOMAIN, "status")
        except HAError as err:
            if "not found" in str(err):
                return None
            raise
        return str(result.get("version")) if isinstance(result, dict) and result.get("version") else "unknown"

    # ---- database ----------------------------------------------------
    @property
    def engine(self) -> str:
        """Chosen in the panel; falls back to the add-on option."""
        e = self.data.get("engine") or addon_options().get("engine", "sqlite")
        return e if e in ENGINES else "sqlite"

    @property
    def sqlite_file(self) -> str:
        name = str(self.data.get("sqlite_file") or sqlite_file()).strip().lstrip("/")
        return name if name and ".." not in name else DEFAULT_SQLITE_FILE

    def db_path(self) -> Path:
        return self.config_dir / self.sqlite_file

    def make_server(self) -> engines.DatabaseServer | None:
        return engines.DatabaseServer(self.engine) if self.engine in ("postgresql", "mariadb") else None

    async def set_engine(self, engine: str, sqlite_name: str | None = None) -> None:
        """Switch the database engine this add-on offers; starts/stops the server accordingly."""
        if engine not in ENGINES:
            raise ValueError(f"unknown engine {engine}")
        name = (sqlite_name or "").strip().lstrip("/") or self.sqlite_file
        if ".." in name or "/" in name or not name.endswith((".db", ".sqlite", ".sqlite3")):
            raise ValueError("The SQLite file must be a plain file name in the config folder, ending in .db")
        if (engine, name) == (self.engine, self.sqlite_file):
            return
        old = self.server
        if old and engine != old.engine and (self.backend == "sql" or self.data["options"].get("db_url") == await self.target_url()):
            raise ValueError(
                f"Home Assistant is set up to record into {old.engine}. Switch the recorder back first "
                "(Back to default SQLite), restart Home Assistant, then change the engine."
            )
        self.data["engine"], self.data["sqlite_file"] = engine, name
        if engine != (old.engine if old else "sqlite"):
            if old:
                await old.stop()
            self.server = self.make_server()
            if self.server:
                await self.server.start()
        self.backend = "sqlite"
        await self.save()

    def sqlite_sources(self) -> list[str]:
        """SQLite files in the config folder that can be copied from."""
        try:
            return sorted(p.name for p in self.config_dir.iterdir() if p.suffix in (".db", ".sqlite", ".sqlite3") and p.is_file())
        except OSError:
            return []

    async def start_history_copy(self, source: str | None = None, force: bool = False) -> None:
        """Copy the history of a SQLite file into the server this add-on runs (in the background)."""
        if not (self.server and self.server.running):
            raise ValueError("Start PostgreSQL or MariaDB first (Switch engine) and wait until it is running.")
        if self._copy_task and not self._copy_task.done():
            raise ValueError("A copy is already running.")
        name = (source or "").strip() or self.sqlite_file
        if "/" in name or ".." in name or name not in self.sqlite_sources():
            raise ValueError(f"{name} is not a SQLite file in the config folder.")
        engine = self.server.engine
        if not force and any(c.get("source") == name and c.get("engine") == engine for c in self.data["history_copies"]):
            raise ValueError(f"The history of {name} was already copied into {engine}. Copying again would duplicate it.")
        server, path = self.server, str(self.config_dir / name)
        progress = self.copy_progress = history_copy.Progress()
        progress.source, progress.engine = name, engine

        async def job() -> None:
            await asyncio.to_thread(history_copy.run, path, lambda: server.connect(write=True), server.dialect, progress)
            if progress.state == "done":
                self.data["history_copies"].append({"source": name, "engine": engine, "at": datetime.now().isoformat(timespec="seconds"), "copied": progress.copied})
                await self.save()
            _LOGGER.info("history copy %s -> %s: %s", name, engine, progress.state if progress.state == "done" else progress.error)

        progress.state = "running"
        self._copy_task = asyncio.create_task(job())

    async def _uses_server(self) -> bool:
        """True when Home Assistant is currently recording into the database server run by this add-on."""
        if not (self.server and self.server.running):
            return False

        def probe():
            conn = self.server.connect()
            try:
                return db_stats_sql.latest_ts(conn)
            finally:
                conn.close()

        try:
            ts = await asyncio.to_thread(probe)
        except Exception:  # noqa: BLE001
            return False
        return ts is not None and time.time() - ts < ACTIVE_WINDOW

    async def _collect(self, full: bool, attrs: bool) -> dict[str, Any]:
        if await self._uses_server():
            self.backend = "sql"
            return await asyncio.to_thread(db_stats_sql.analyze, self.server.connect, self.server.dialect, self.server.label, full, attrs)
        self.backend = "sqlite"
        return await asyncio.to_thread(db_stats.analyze, self.db_path(), full, attrs)

    async def target_url(self) -> str | None:
        """The recorder db_url that matches the chosen engine (None = Home Assistant's default SQLite file)."""
        engine = self.engine
        if engine == "sqlite":
            name = self.sqlite_file
            return None if name == DEFAULT_SQLITE_FILE else f"sqlite:////config/{name}"
        return engines.build_db_url(engine, await self.ha.addon_hostname(), self.server.creds if self.server else engines.load_credentials())

    async def analyze(self, full: bool = True) -> dict[str, Any]:
        path = self.db_path()
        d = self.data
        previous = d.get("stats") or {}
        now = time.time()
        want_attrs = full and now - float(previous.get("attr_tried") or 0) > ATTR_REFRESH_SECONDS
        save = full
        try:
            stats = await self._collect(full, want_attrs)
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
                u = shutil.disk_usage(DATA_DIR if self.backend == "sql" else self.db_path().parent)
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
