"""Recorder Studio DB: lets the add-on of the same name apply recorder settings without a Home Assistant restart.

This integration is installed and updated by the add-on (it copies this folder into custom_components). It has no UI of
its own: the panel lives in the add-on. It only offers the service recorder_studio_db.apply_config.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, VERSION
from .live import async_apply_live

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_handle_apply_config(call: ServiceCall) -> dict:
    """Apply recorder_studio.yaml to the running recorder; answers what was applied and what still needs a restart."""
    result = await async_apply_live(call.hass)
    result["version"] = VERSION
    return result


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_register(DOMAIN, "apply_config", _async_handle_apply_config, supports_response=SupportsResponse.OPTIONAL)
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "apply_config"))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True
