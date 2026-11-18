"""Let the recorder wait while the database server is restarted on purpose, so no history is lost.

Home Assistant's own database lock (used for backups) only exists for SQLite: for MariaDB/PostgreSQL it does nothing, and its
task even runs SQLite statements. So this module queues a small task of its own, in the recorder's own queue: the recorder
commits what it has, then waits. Events that arrive meanwhile stay in its in-memory queue and are written once it continues.

Safety nets (a recorder that waits forever would record nothing):
  * it continues by itself after MAX_PAUSE seconds, and as soon as its queue gets long
  * it continues when Home Assistant stops or this integration is unloaded
  * the connection pool is renewed before it continues, so the first commit does not hit a connection that died with the server
Every step is guarded: if anything looks different from what we expect, nothing is paused and the add-on just goes ahead.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from . import quiet
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MAX_PAUSE = 180  # seconds
LOCK_TIMEOUT = 20  # seconds to wait for the recorder to reach the pause task
QUEUE_LIMIT = 30_000  # events; Home Assistant itself gives up (and drops events) at 65,000


def _make_task(locked: asyncio.Event, release: threading.Event, loop: asyncio.AbstractEventLoop):
    """Built on demand: the base class is a recorder internal that may change between Home Assistant versions."""
    from dataclasses import dataclass

    from homeassistant.components.recorder.tasks import RecorderTask

    @dataclass(slots=True)
    class PauseTask(RecorderTask):
        locked: asyncio.Event
        release: threading.Event
        loop: asyncio.AbstractEventLoop
        overflow: bool = False

        def run(self, instance: Any) -> None:  # runs in the recorder thread
            self.loop.call_soon_threadsafe(self.locked.set)
            while not self.release.wait(timeout=1):
                if int(getattr(instance, "backlog", 0) or 0) > QUEUE_LIMIT:
                    self.overflow = True
                    _LOGGER.warning("Recorder queue is long (%s events) while paused: continuing writing", getattr(instance, "backlog", "?"))
                    return

    return PauseTask(locked, release, loop)


async def async_pause(hass: HomeAssistant) -> dict[str, Any]:
    state = hass.data.setdefault(DOMAIN, {})
    if state.get("pause"):
        return {"paused": True, "reason": "already_paused"}
    try:
        from homeassistant.helpers.recorder import get_instance

        instance = get_instance(hass)
        if not callable(getattr(instance, "queue_task", None)):
            return {"paused": False, "reason": "recorder_changed: queue_task"}
        locked, release = asyncio.Event(), threading.Event()
        task = _make_task(locked, release, hass.loop)
        instance.queue_task(task)
        try:
            async with asyncio.timeout(LOCK_TIMEOUT):
                await locked.wait()
        except TimeoutError:
            release.set()  # it will fall through the task whenever the recorder gets to it
            return {"paused": False, "reason": "timeout"}
    except Exception as err:  # noqa: BLE001 - the add-on simply carries on without a pause
        _LOGGER.warning("Could not pause the recorder: %s", err)
        return {"paused": False, "reason": f"{type(err).__name__}: {err}"}
    cancel = async_call_later(hass, MAX_PAUSE, _auto_resume(hass))
    state["pause"] = {"task": task, "release": release, "cancel": cancel, "since": time.monotonic()}
    quiet.start(hass)  # the restart that follows is planned: its connection errors are not errors
    _LOGGER.info("Recorder paused (events are queued) for a planned database restart")
    return {"paused": True, "reason": None}


def _auto_resume(hass: HomeAssistant):
    @callback
    def _fire(_now) -> None:
        _LOGGER.warning("The recorder was paused for %s seconds without a resume: continuing", MAX_PAUSE)
        hass.async_create_task(async_resume(hass, auto=True), "recorder_studio_db auto resume")

    return _fire


async def async_resume(hass: HomeAssistant, auto: bool = False) -> dict[str, Any]:
    state = hass.data.setdefault(DOMAIN, {})
    pause = state.pop("pause", None)
    if not pause:
        return {"resumed": False, "reason": "not_paused"}
    pause["cancel"]()
    try:
        from homeassistant.helpers.recorder import get_instance

        instance = get_instance(hass)
        engine = getattr(instance, "engine", None)
        if engine is not None and str(getattr(instance, "dialect_name", "")) != "sqlite":
            # connections to the restarted server are dead: start the next commit on fresh ones
            await hass.async_add_executor_job(engine.dispose)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not renew the recorder's connections: %s", err)
    pause["release"].set()
    quiet.end_soon(hass)
    paused_for = round(time.monotonic() - pause["since"], 1)
    _LOGGER.info("Recorder continues after %s s (%s)", paused_for, "automatically" if auto else "on request")
    return {"resumed": True, "auto": auto, "seconds": paused_for, "overflow": bool(pause["task"].overflow)}


def release_now(hass: HomeAssistant) -> None:
    """Synchronous release for shutdown/unload."""
    pause = (hass.data.get(DOMAIN) or {}).pop("pause", None)
    if pause:
        pause["cancel"]()
        pause["release"].set()
    quiet.stop(hass)
