"""Apply recorder_studio.yaml to the running recorder, so most changes need no Home Assistant restart.

What can change live (the recorder reads these where they are used, or its event listener can be re-created):
  * the entity filter (include / exclude: domains, entities, globs) and excluded event types
  * purge_keep_days, auto_purge, auto_repack
What still needs a restart: db_url, commit_interval (the database engine and its commit timer are created at start-up).

Home Assistant has no public API for this (see the notes in CLAUDE.md), so this uses two things the recorder itself uses:
the documented `entity_filter` attribute and the stop/`async_initialize` pair that it runs around backups. Every
step is guarded: if the recorder looks different from what we expect we change nothing and ask for a restart.
"""
from __future__ import annotations

from functools import partial
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import CONFIG_FILE, DOMAIN, GENERATED_FILE
from . import migration

_LOGGER = logging.getLogger(__name__)

NEEDED = ("entity_filter", "exclude_event_types", "keep_days", "auto_purge", "auto_repack", "commit_interval", "db_url",
          "async_initialize", "_async_stop_queue_watcher_and_event_listener", "_event_listener")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


@callback
def _swap_filter(instance: Any, entity_filter: Any, exclude_types: set[str]) -> None:
    """Replace the filter of a recorder that is listening. Runs in the event loop in one go, so no event is missed."""
    old_filter, old_types = instance.entity_filter, instance.exclude_event_types
    instance._async_stop_queue_watcher_and_event_listener()
    try:
        instance.entity_filter, instance.exclude_event_types = entity_filter, exclude_types
        instance.async_initialize()
        _drop_stale_state_index(instance)
    except Exception:
        _LOGGER.exception("Could not apply the new recorder filter, restoring the previous one")
        instance.entity_filter, instance.exclude_event_types = old_filter, old_types
        instance.async_initialize()  # the recorder must never be left without its listeners
        _drop_stale_state_index(instance)
        raise


def _drop_stale_state_index(instance: Any) -> None:
    """Once the recorder is ready it has dropped its index of queued state changes (None). async_initialize still starts
    the listener that fills that index, and that listener fails on every state change: remove it again."""
    if getattr(instance, "_queued_states", True) is None and getattr(instance, "_queued_states_listener", None) is not None:
        instance._async_drop_queued_states()  # older recorders have no such index: nothing to do there


def _restart_keys(hass: HomeAssistant, instance: Any, conf: dict[str, Any]) -> list[str]:
    keys = []
    wanted_url = conf.get("db_url") or f"sqlite:///{hass.config.path('home-assistant_v2.db')}"
    if str(instance.db_url) != str(wanted_url):
        keys.append("db_url")
    if int(instance.commit_interval) != int(conf["commit_interval"]):
        keys.append("commit_interval")
    return keys


async def async_apply_live(hass: HomeAssistant) -> dict[str, Any]:
    """Returns {applied, restart: [keys still needing a restart], changed: [...], reason}."""
    result: dict[str, Any] = {"applied": False, "restart": [], "changed": [], "reason": None}
    try:
        from homeassistant.components import recorder as rec
        from homeassistant.helpers.entityfilter import convert_include_exclude_filter
        from homeassistant.helpers.recorder import get_instance
        from homeassistant.util.yaml import load_yaml_dict

        try:
            from homeassistant.util.yaml import Secrets
        except ImportError:  # a Home Assistant without that class: secrets cannot be resolved here
            Secrets = None

        text = await hass.async_add_executor_job(_read, Path(hass.config.path(CONFIG_FILE)))
        if migration.inspect_configuration(text or "", GENERATED_FILE).get("state") != "active":
            result["reason"] = "not_active"  # configuration.yaml does not include our file yet: a restart will not use it either
            result["restart"] = ["configuration"]
            return result
        # the add-on keeps the database password in secrets.yaml and writes `db_url: !secret ...`; the loader only resolves
        # that when it is given the secrets of this config folder
        secrets = Secrets(Path(hass.config.config_dir)) if Secrets else None
        raw = await hass.async_add_executor_job(partial(load_yaml_dict, hass.config.path(GENERATED_FILE), secrets=secrets))
        conf = rec.CONFIG_SCHEMA({rec.DOMAIN: raw or {}})[rec.DOMAIN]
        instance = get_instance(hass)
        missing = [n for n in NEEDED if not hasattr(instance, n)]
        if missing:
            result["reason"] = f"recorder_changed: {', '.join(missing)}"
            result["restart"] = ["all"]
            return result

        _filter = convert_include_exclude_filter(conf)
        entity_filter = None if _filter.empty_filter else _filter.get_filter()
        exclude_types = set(conf["exclude"].get("event_types", []))
        exclude_types.discard("state_changed")  # the recorder refuses this one too

        # Compare the rules, not the function objects: the filter only has to be swapped when the rules differ.
        wanted = {"keep_days": int(conf["purge_keep_days"]), "auto_purge": bool(conf["auto_purge"]), "auto_repack": bool(conf["auto_repack"])}
        for attr, value in wanted.items():
            if getattr(instance, attr) != value:
                setattr(instance, attr, value)
                result["changed"].append(attr)
        rules_key = repr((conf["include"], conf["exclude"]))
        domain_data = hass.data.setdefault(DOMAIN, {})
        if domain_data.get("applied_rules") != rules_key or instance.exclude_event_types != exclude_types:
            if instance._event_listener is None:  # recorder paused (e.g. backup): its next async_initialize picks the new filter up
                instance.entity_filter, instance.exclude_event_types = entity_filter, exclude_types
            else:
                _swap_filter(instance, entity_filter, exclude_types)
            domain_data["applied_rules"] = rules_key
            result["changed"].append("filter")
        result["applied"] = True
        result["restart"] = _restart_keys(hass, instance, conf)
    except Exception as err:  # noqa: BLE001 - reported to the panel, which then asks for a restart
        _LOGGER.warning("Could not apply the recorder configuration live: %s", err)
        result["reason"] = f"{type(err).__name__}: {err}"
        result["restart"] = ["all"]
    return result
