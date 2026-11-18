"""Pausing the recorder around a planned database restart."""
from datetime import timedelta
import threading
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.recorder_studio_db import pause
from custom_components.recorder_studio_db.const import DOMAIN


class FakeEngine:
    def __init__(self):
        self.disposed = 0

    def dispose(self):
        self.disposed += 1


class FakeRecorder:
    """Runs queued tasks in a thread, like the real recorder thread does."""

    def __init__(self, dialect="mysql"):
        self.engine, self.dialect_name, self.backlog = FakeEngine(), dialect, 0
        self.threads, self.swallow = [], False

    def queue_task(self, task):
        if self.swallow:  # a recorder that never gets to the task
            return
        thread = threading.Thread(target=task.run, args=(self,), daemon=True)
        thread.start()
        self.threads.append(thread)


@pytest.fixture
def recorder(hass):
    hass.data.setdefault(DOMAIN, {})
    rec = FakeRecorder()
    with patch("homeassistant.helpers.recorder.get_instance", return_value=rec):
        yield rec
    pause.release_now(hass)


async def test_pause_waits_until_resume_and_renews_the_connections(hass, recorder):
    result = await pause.async_pause(hass)
    assert result["paused"] is True
    assert recorder.threads[0].is_alive()  # the recorder thread is waiting, events pile up in its queue
    assert (await pause.async_pause(hass))["reason"] == "already_paused"
    result = await pause.async_resume(hass)
    assert result["resumed"] is True and result["overflow"] is False
    assert recorder.engine.disposed == 1  # fresh connections for the first commit after the restart
    await hass.async_add_executor_job(recorder.threads[0].join, 5)
    assert not recorder.threads[0].is_alive()


async def test_resume_without_pause_is_harmless(hass, recorder):
    assert (await pause.async_resume(hass)) == {"resumed": False, "reason": "not_paused"}
    assert recorder.engine.disposed == 0


async def test_sqlite_keeps_its_connections(hass):
    hass.data.setdefault(DOMAIN, {})
    rec = FakeRecorder(dialect="sqlite")
    with patch("homeassistant.helpers.recorder.get_instance", return_value=rec):
        await pause.async_pause(hass)
        await pause.async_resume(hass)
    pause.release_now(hass)  # also ends the short "hide connection errors" timer that follows a resume
    assert rec.engine.disposed == 0  # disposing would drop an in-memory/WAL database


async def test_recorder_that_never_reaches_the_task_is_not_paused(hass, recorder, monkeypatch):
    monkeypatch.setattr(pause, "LOCK_TIMEOUT", 0.2)
    recorder.swallow = True
    result = await pause.async_pause(hass)
    assert result == {"paused": False, "reason": "timeout"}
    assert "pause" not in hass.data[DOMAIN]


async def test_long_queue_makes_the_recorder_continue_by_itself(hass, recorder):
    recorder.backlog = pause.QUEUE_LIMIT + 1
    task_result = await pause.async_pause(hass)
    assert task_result["paused"] is True
    await hass.async_add_executor_job(recorder.threads[0].join, 5)  # it noticed the long queue and left the wait
    assert not recorder.threads[0].is_alive()
    result = await pause.async_resume(hass)
    assert result["overflow"] is True


async def test_pause_ends_by_itself_after_the_maximum(hass, recorder, monkeypatch):
    monkeypatch.setattr(pause, "MAX_PAUSE", 5)
    await pause.async_pause(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert "pause" not in hass.data[DOMAIN]
    await hass.async_add_executor_job(recorder.threads[0].join, 5)
    assert not recorder.threads[0].is_alive()


async def test_unknown_recorder_is_not_paused(hass):
    hass.data.setdefault(DOMAIN, {})
    with patch("homeassistant.helpers.recorder.get_instance", return_value=object()):
        result = await pause.async_pause(hass)
    assert result["paused"] is False and "recorder_changed" in result["reason"]


async def test_services_pause_and_resume(hass, config_dir, recorder):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    answer = await hass.services.async_call(DOMAIN, "pause_recorder", blocking=True, return_response=True)
    assert answer["paused"] is True
    answer = await hass.services.async_call(DOMAIN, "resume_recorder", blocking=True, return_response=True)
    assert answer["resumed"] is True


async def test_unloading_never_leaves_the_recorder_waiting(hass, config_dir, recorder):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.async_block_till_done()
    await hass.services.async_call(DOMAIN, "pause_recorder", blocking=True, return_response=True)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_add_executor_job(recorder.threads[0].join, 5)
    assert not recorder.threads[0].is_alive()
