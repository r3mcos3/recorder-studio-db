"""Recorder Studio DB: lets the add-on of the same name apply recorder settings without a Home Assistant restart.

This integration is installed and updated by the add-on (it copies this folder into custom_components). It has no UI of
its own: the panel lives in the add-on. It only offers the service recorder_studio_db.apply_config.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DOMAIN, SIGNAL_METRICS, STORAGE_KEY, STORAGE_VERSION, VERSION
from .live import async_apply_live
from .pause import async_pause, async_resume, release_now

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = ["sensor"]


async def _async_handle_apply_config(call: ServiceCall) -> dict:
    """Apply recorder_studio.yaml to the running recorder; answers what was applied and what still needs a restart."""
    result = await async_apply_live(call.hass)
    result["version"] = VERSION
    return result


async def _async_handle_pause(call: ServiceCall) -> dict:
    """The add-on is about to stop the database on purpose: let the recorder wait instead of failing."""
    return await async_pause(call.hass)


async def _async_handle_resume(call: ServiceCall) -> dict:
    return await async_resume(call.hass)


async def _async_handle_status(call: ServiceCall) -> dict:
    """Which version runs. Changes nothing (the add-on uses it to check the integration is loaded)."""
    return {"version": VERSION}


async def _async_handle_update_metrics(call: ServiceCall) -> None:
    """The add-on hands over the figures it measured; they become the state of the sensors."""
    metrics = call.data.get("metrics")
    if not isinstance(metrics, dict):
        raise ServiceValidationError("metrics must be a mapping of sensor key to value")
    domain = call.hass.data.setdefault(DOMAIN, {})
    domain["metrics"] = metrics
    store = domain.get("store")
    if store:
        await store.async_save(metrics)
    async_dispatcher_send(call.hass, SIGNAL_METRICS)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain = hass.data.setdefault(DOMAIN, {})
    domain["store"] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    domain["metrics"] = await domain["store"].async_load() or {}  # the last figures survive a restart until the add-on sends new ones
    hass.services.async_register(DOMAIN, "update_metrics", _async_handle_update_metrics)
    hass.services.async_register(DOMAIN, "pause_recorder", _async_handle_pause, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "resume_recorder", _async_handle_resume, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "apply_config", _async_handle_apply_config, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "status", _async_handle_status, supports_response=SupportsResponse.ONLY)
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "apply_config"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "status"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "update_metrics"))
    for name in ("pause_recorder", "resume_recorder"):
        entry.async_on_unload(lambda name=name: hass.services.async_remove(DOMAIN, name))
    entry.async_on_unload(lambda: release_now(hass))  # never leave the recorder waiting
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, lambda _event: release_now(hass)))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
