"""Do not call a planned database restart an error.

While the add-on restarts the database on purpose (the recorder is paused), Home Assistant itself and other integrations that
read from the database log "Can't connect" / "Lost connection" errors. Those are expected for those few seconds and not worth an
error in the log. This hides only *connection* errors, only while the planned restart runs (plus a short grace period for
queries that are still on their way), and says afterwards how many it hid. A database that goes away at any other moment is
still logged as an error.
"""
from __future__ import annotations

import logging
import re
import time
import traceback
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

GRACE = 30  # seconds after the recorder continues
CONNECTION_ERROR = re.compile(
    r"\((?:2002|2003|2006|2013)\b|Lost connection to (?:MySQL )?server|Can't connect to (?:MySQL )?server|MySQL server has gone away"
    r"|server closed the connection unexpectedly|could not connect to server|terminating connection due to administrator command"
    r"|the database system is (?:shutting down|starting up)|connection to server .* failed|Connection refused",
    re.IGNORECASE,
)


class PlannedRestartFilter(logging.Filter):
    """Drops database connection errors while `active` or until `until` (monotonic time)."""

    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.until = 0.0
        self.hidden = 0

    def window_open(self) -> bool:
        return self.active or time.monotonic() < self.until

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.WARNING or not self.window_open():
            return True
        try:
            text = record.getMessage()
            if record.exc_info:
                text += "".join(traceback.format_exception_only(record.exc_info[0], record.exc_info[1]))
            if record.exc_text:
                text += record.exc_text
        except Exception:  # noqa: BLE001 - never lose a log record because of this filter
            return True
        if CONNECTION_ERROR.search(text):
            if not getattr(record, "_rs_counted", False):  # the filter sits on every log handler: count a record once
                record._rs_counted = True  # type: ignore[attr-defined]
                self.hidden += 1
            return False
        return True


def _handlers() -> list[logging.Handler]:
    return list(logging.getLogger().handlers)


def start(hass: HomeAssistant) -> None:
    """The recorder is paused for a planned restart: hide the connection errors that follow."""
    state = hass.data.setdefault(DOMAIN, {})
    quiet = state.get("quiet")
    if quiet:
        quiet["filter"].active = True
        if quiet.get("cancel"):
            quiet["cancel"]()
            quiet["cancel"] = None
        return
    flt = PlannedRestartFilter()
    flt.active = True
    attached = []
    for handler in _handlers():
        handler.addFilter(flt)
        attached.append(handler)
    state["quiet"] = {"filter": flt, "handlers": attached, "cancel": None}


def end_soon(hass: HomeAssistant) -> None:
    """The recorder continues: keep hiding for a short grace period, then report what was hidden."""
    quiet = (hass.data.get(DOMAIN) or {}).get("quiet")
    if not quiet:
        return
    flt: PlannedRestartFilter = quiet["filter"]
    flt.active = False
    flt.until = time.monotonic() + GRACE

    @callback
    def _done(_now: Any) -> None:
        quiet["cancel"] = None
        stop(hass)

    quiet["cancel"] = async_call_later(hass, GRACE + 1, _done)


def stop(hass: HomeAssistant) -> None:
    """Remove the filter (also on unload) and say once how many errors were hidden."""
    quiet = (hass.data.get(DOMAIN) or {}).pop("quiet", None)
    if not quiet:
        return
    if quiet.get("cancel"):
        quiet["cancel"]()
    flt: PlannedRestartFilter = quiet["filter"]
    flt.active, flt.until = False, 0.0
    for handler in quiet["handlers"]:
        handler.removeFilter(flt)
    if flt.hidden:
        _LOGGER.info("Hid %s database connection error(s) during the planned database restart", flt.hidden)
