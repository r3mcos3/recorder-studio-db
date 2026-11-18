"""Command dispatcher: the panel's former websocket commands, over one POST endpoint."""
from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .const import ADDON_VERSION, DEFAULT_SQLITE_FILE, ENGINES, CONFIG_FILE, GENERATED_FILE, LEGACY_FILE, READ_ONLY_MODE, addon_options
from .core import db_stats, migration
from .core.rules import parse_manual_rules
from .core.yaml_writer import atomic_write
from . import engines
from .ha import HAError
from .service import Studio


class ApiError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _need_write() -> None:
    if READ_ONLY_MODE:
        raise ApiError("read_only", "Recorder Studio is in read-only mode: write actions are disabled.")


def _need_confirm(msg: dict) -> None:
    if msg.get("confirm") is not True:
        raise ApiError("confirm_required", "This action needs confirm: true.")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _int(msg: dict, key: str, lo: int, hi: int) -> int:
    try:
        v = int(msg[key])
    except (KeyError, TypeError, ValueError):
        raise ApiError("invalid_format", f"{key} must be a number") from None
    if not lo <= v <= hi:
        raise ApiError("invalid_format", f"{key} must be between {lo} and {hi}")
    return v


async def _config_info(s: Studio) -> dict[str, Any]:
    text = await asyncio.to_thread(_read, s.config_dir / CONFIG_FILE) or ""
    info = migration.inspect_configuration(text, GENERATED_FILE)
    info["legacy_file_present"] = await asyncio.to_thread(_read, s.config_dir / LEGACY_FILE) is not None
    return info


async def get_state(s: Studio, msg: dict) -> dict:
    await s.refresh_entities()
    if s.integration["state"] != "ready" and time.monotonic() - s.integration_checked > 15:
        # e.g. Home Assistant was restarted meanwhile: notice that the integration runs now, without a button press
        with contextlib.suppress(Exception):
            await s.ensure_integration()
    d = s.data
    return {
        "version": ADDON_VERSION,
        "engine": s.engine,
        "db_files": (d.get("stats") or {}).get("files") if s.backend == "sql" else await asyncio.to_thread(db_stats.file_sizes, s.db_path()),
        "backend": s.backend,
        "sqlite": True,
        "options": d["options"],
        "rules_text": d["rules_text"],
        "tree": s.build_tree(),
        "summary": s.summary(),
        "suggestions": s.build_suggestions(),
        "growth": await s.growth(),
        "alerts": {**d["alerts"], "active": s.active_alerts},
        "config": await _config_info(s),
        "pending_restart": s.pending_restart,
        "live": s.live,
        "integration": dict(s.integration),
        "yaml_file": GENERATED_FILE,
        "read_only": READ_ONLY_MODE,
    }


async def set_recorded(s: Studio, msg: dict) -> dict:
    _need_write()
    d = s.data
    ids = {e.strip() for e in msg.get("entity_ids", []) if isinstance(e, str) and e.strip()}
    recorded = bool(msg.get("recorded"))
    current = set(d["excluded_entities"])
    d["excluded_entities"] = sorted(current - ids if recorded else current | ids)
    if not recorded:
        d["rescued_entities"] = sorted(set(d["rescued_entities"]) - ids)
    live = await s.persist()
    return {"excluded": len(d["excluded_entities"]), "summary": s.summary(), "live": live}


async def save_settings(s: Studio, msg: dict) -> dict:
    _need_write()
    opts = {
        "purge_keep_days": _int(msg, "purge_keep_days", 1, 3650),
        "commit_interval": _int(msg, "commit_interval", 0, 86400),
        "auto_purge": bool(msg.get("auto_purge")),
        "auto_repack": bool(msg.get("auto_repack")),
    }
    try:
        parse_manual_rules(str(msg.get("rules_text", "")))
    except ValueError as err:
        raise ApiError("invalid_rules", str(err)) from None
    s.data["options"].update(opts)
    s.data["rules_text"] = msg["rules_text"]
    live = await s.persist()
    return {"ok": True, "live": live}


async def analyze(s: Studio, msg: dict) -> dict:
    await s.refresh_entities()
    await s.analyze(full=not msg.get("light", False))
    return {"summary": s.summary(), "tree": s.build_tree()}


def _targets(s: Studio, msg: dict) -> list[str]:
    if msg.get("kind") == "excluded":
        return list(s.data["excluded_entities"])
    return sorted({e for e in msg.get("entity_ids", []) if isinstance(e, str)})


async def preview_purge(s: Studio, msg: dict) -> dict:
    if msg.get("kind") == "retention":
        return {"keep_days": s.data["options"]["purge_keep_days"]}
    return db_stats.estimate_impact(s.need_stats(), _targets(s, msg))


async def purge(s: Studio, msg: dict) -> dict:
    _need_write()
    _need_confirm(msg)
    keep = s.data["options"]["purge_keep_days"]
    repack = bool(msg.get("repack"))
    if msg.get("kind") == "retention":
        await s.ha.call_service("recorder", "purge", {"keep_days": keep, "repack": repack})
        return {"queued": True}
    ids = _targets(s, msg)
    if not ids:
        raise ApiError("nothing_to_purge", "No entities selected.")
    await s.ha.call_service("recorder", "purge_entities", {"entity_id": ids, "keep_days": 0})
    if repack:
        await s.ha.call_service("recorder", "purge", {"keep_days": keep, "repack": True})
    return {"queued": True, "entities": len(ids)}


async def repack(s: Studio, msg: dict) -> dict:
    _need_write()
    _need_confirm(msg)
    await s.ha.call_service("recorder", "purge", {"keep_days": s.data["options"]["purge_keep_days"], "repack": True})
    return {"queued": True}


async def restart(s: Studio, msg: dict) -> dict:
    _need_write()
    _need_confirm(msg)
    try:
        await s.ha.call_service("homeassistant", "restart")
    except Exception as err:  # noqa: BLE001
        raise ApiError("restart_failed", str(err)) from None
    return {"ok": True}


async def remove_orphans(s: Studio, msg: dict) -> dict:
    _need_write()
    summ = s.summary()
    orphans = set(summ["orphan_exclusions"]) if summ else set()
    d = s.data
    d["excluded_entities"] = sorted(set(d["excluded_entities"]) - orphans)
    d["rescued_entities"] = sorted(set(d["rescued_entities"]) - orphans)
    live = await s.persist()
    return {"removed": len(orphans), "summary": s.summary(), "live": live}


async def save_alerts(s: Studio, msg: dict) -> dict:
    _need_write()
    s.data["alerts"] = {"enabled": bool(msg.get("enabled")), "free_percent": _int(msg, "free_percent", 1, 90), "growth_percent": _int(msg, "growth_percent", 5, 1000)}
    await s.save()
    await s.check_alerts()
    return {"active": s.active_alerts}


async def dismiss_suggestions(s: Studio, msg: dict) -> dict:
    _need_write()
    d = s.data
    ids = {e.strip() for e in msg.get("entity_ids", []) if isinstance(e, str) and e.strip()}
    d["dismissed"] = [] if msg.get("reset") else sorted(set(d["dismissed"]) | ids)
    await s.save()
    return {"suggestions": s.build_suggestions()}


async def backup_status(s: Studio, msg: dict) -> dict:
    return await s.backup_status()


# ---- migration -----------------------------------------------------------
def _source(msg: dict) -> str:
    import re

    src = str(msg.get("source", ""))
    if not re.fullmatch(r"(configuration|legacy|paste|file:.{1,200})", src):
        raise ApiError("invalid_format", "invalid source")
    if len(str(msg.get("text", ""))) > 200_000:
        raise ApiError("invalid_format", "text too long")
    return src


def _load_source(config_dir: Path, source: str, text: str | None, config_text: str):
    if source == "configuration":
        return migration.inspect_configuration(config_text, GENERATED_FILE).get("imported"), CONFIG_FILE
    if source == "paste":
        return migration.parse_text(text or ""), "pasted YAML"
    rel = LEGACY_FILE if source == "legacy" else source[len("file:"):]
    path = migration.safe_config_path(config_dir, rel)
    return migration.parse_text(path.read_text(encoding="utf-8")), rel


async def _load_import(s: Studio, msg: dict):
    src = _source(msg)
    config_text = await asyncio.to_thread(_read, s.config_dir / CONFIG_FILE) or ""
    try:
        imp, label = await asyncio.to_thread(_load_source, s.config_dir, src, msg.get("text"), config_text)
    except (ValueError, OSError) as err:
        raise ApiError("nothing_to_import", str(err)) from None
    if imp is None:
        raise ApiError("nothing_to_import", "No recorder configuration found at that source.")
    return imp, label


async def migration_sources(s: Studio, msg: dict) -> dict:
    text = await asyncio.to_thread(_read, s.config_dir / CONFIG_FILE) or ""
    return {"sources": await asyncio.to_thread(migration.discover_sources, s.config_dir, GENERATED_FILE, text, LEGACY_FILE)}


async def migration_preview(s: Studio, msg: dict) -> dict:
    imp, label = await _load_import(s, msg)
    cfg = await _config_info(s)
    text = await asyncio.to_thread(_read, s.config_dir / CONFIG_FILE) or ""
    after = migration.activate(text, GENERATED_FILE)
    note = ""
    if msg["source"].startswith("file:") and label != str(cfg.get("include_target", "")).strip().strip("'\""):
        note = f"{label} is not changed by Recorder Studio. After activation, remove its recorder: section yourself, otherwise Home Assistant reports a duplicate recorder configuration."
    return {
        "import": {**imp, "excluded_count": len(imp["excluded_entities"])}, "label": label, "note": note, "config_state": cfg["state"],
        "diff": migration.diff_text(text, after, CONFIG_FILE) if cfg["state"] != "active" else "", "current_excluded": len(s.data["excluded_entities"]),
    }


async def migration_import(s: Studio, msg: dict) -> dict:
    _need_write()
    _need_confirm(msg)
    imp, _ = await _load_import(s, msg)
    d = s.data
    warnings = list(imp["warnings"])
    if msg.get("merge"):
        merged, extra = migration.merge_import(
            {"options": d["options"], "excluded_entities": d["excluded_entities"], "rescued_entities": d["rescued_entities"], "rules_text": d["rules_text"]}, imp)
        d["options"].update(merged["options"])
        d["excluded_entities"], d["rescued_entities"], d["rules_text"] = merged["excluded_entities"], merged["rescued_entities"], merged["rules_text"]
        warnings += extra
    else:
        d["options"].update(imp["options"])
        d["excluded_entities"], d["rescued_entities"], d["rules_text"] = imp["excluded_entities"], imp["rescued_entities"], imp["rules_text"]
    live = await s.persist()
    return {"warnings": warnings, "excluded": len(d["excluded_entities"]), "live": live}


def _activate_files(config_path: Path) -> str:
    before = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    after = migration.activate(before, GENERATED_FILE)
    backup = config_path.with_name(f"{config_path.name}.recorder_studio_backup_{datetime.now():%Y%m%d_%H%M%S}")
    if before:
        atomic_write(backup, before)
    atomic_write(config_path, after)
    return backup.name if before else ""


async def migration_activate(s: Studio, msg: dict) -> dict:
    _need_write()
    _need_confirm(msg)
    await s.write_yaml()
    backup = await asyncio.to_thread(_activate_files, s.config_dir / CONFIG_FILE)
    s.pending_restart = True
    return {"backup": backup}


async def db_status(s: Studio, msg: dict) -> dict:
    engine = s.engine
    info = await asyncio.to_thread(s.server.info) if s.server else {"engine": s.engine, "state": "n/a", "error": None}
    target = await s.target_url()
    current = s.data["options"].get("db_url")
    return {
        **info,
        "engine": engine,
        "sqlite_file": s.sqlite_file,
        "backend": s.backend,
        "engines": list(ENGINES),
        "target_url": engines.mask_url(target) if target else None,
        "current_url": engines.mask_url(current) if current else None,
        "configured": (current or None) == target,
        "pending_restart": s.pending_restart,
        "default_sqlite": s.sqlite_file == DEFAULT_SQLITE_FILE,
    }


async def db_set_engine(s: Studio, msg: dict) -> dict:
    _need_write()
    _need_confirm(msg)
    try:
        await s.set_engine(str(msg.get("engine", "")), msg.get("sqlite_file"))
    except ValueError as err:
        raise ApiError("invalid_engine", str(err)) from None
    return {"engine": s.engine}


async def db_activate(s: Studio, msg: dict) -> dict:
    """Point the recorder at the database chosen in the add-on options (written to recorder_studio.yaml, restart needed)."""
    _need_write()
    _need_confirm(msg)
    if s.server and not s.server.running:
        raise ApiError("db_not_running", "The database server is not running yet.")
    target = await s.target_url()
    if target:
        s.data["options"]["db_url"] = target
    else:
        s.data["options"].pop("db_url", None)
    live = await s.persist()
    return {"configured": True, "live": live}


async def db_deactivate(s: Studio, msg: dict) -> dict:
    """Back to Home Assistant's own default SQLite file."""
    _need_write()
    _need_confirm(msg)
    s.data["options"].pop("db_url", None)
    live = await s.persist()
    return {"configured": False, "live": live}


async def db_metrics(s: Studio, msg: dict) -> dict:
    """Detailed database figures: sizes per table, rows, fragmentation, growth (also what the sensors show)."""
    return await s.metrics()


async def integration_status(s: Studio, msg: dict) -> dict:
    return dict(s.integration)


async def integration_ensure(s: Studio, msg: dict) -> dict:
    """Check again (after a Home Assistant restart) and, if needed, install/activate the bundled integration."""
    try:
        return dict(await s.ensure_integration())
    except HAError as err:
        raise ApiError("ha_unreachable", f"Home Assistant cannot be reached: {err}") from None


async def history_status(s: Studio, msg: dict) -> dict:
    running = bool(s.server and s.server.running)
    return {
        **s.copy_progress.as_dict(),
        "available": running,
        "engine": s.server.engine if s.server else None,
        "sources": s.sqlite_sources(),
        "default_source": s.sqlite_file,
        "done_before": s.data["history_copies"],
    }


async def history_copy_start(s: Studio, msg: dict) -> dict:
    """Copy the history of a SQLite file into the add-on's PostgreSQL/MariaDB (Home Assistant may keep recording)."""
    _need_write()
    _need_confirm(msg)
    try:
        await s.start_history_copy(msg.get("source"), bool(msg.get("force")))
    except ValueError as err:
        raise ApiError("history_copy", str(err)) from None
    return {"started": True}


COMMANDS = {f.__name__: f for f in (
    get_state, set_recorded, save_settings, analyze, preview_purge, purge, repack, restart, remove_orphans, save_alerts,
    dismiss_suggestions, backup_status, db_status, db_metrics, integration_status, integration_ensure, history_status, history_copy_start, db_set_engine, db_activate, db_deactivate, migration_sources, migration_preview, migration_import, migration_activate)}
