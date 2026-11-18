"""Connection errors during a planned database restart are not shown as errors; any other moment they are."""
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.recorder_studio_db import pause, quiet
from custom_components.recorder_studio_db.const import DOMAIN

from test_pause import FakeRecorder

LOST = "Error executing query: (MySQLdb.OperationalError) (2013, 'Lost connection to server during query')"
CANT = "(MySQLdb.OperationalError) (2002, \"Can't connect to server on '455b5752-recorder-studio-db' (115)\")"


class Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@pytest.fixture
def sink():
    handler = Collect()
    root = logging.getLogger()
    old = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield handler
    root.removeHandler(handler)
    root.setLevel(old)


@pytest.fixture
def recorder(hass):
    hass.data.setdefault(DOMAIN, {})
    rec = FakeRecorder()
    with patch("homeassistant.helpers.recorder.get_instance", return_value=rec):
        yield rec
    pause.release_now(hass)


def _record(msg, level=logging.ERROR, exc=None):
    return logging.LogRecord("x", level, __file__, 1, msg, None, exc)


def test_filter_hides_only_connection_errors_while_the_window_is_open():
    f = quiet.PlannedRestartFilter()
    assert f.filter(_record(LOST)) is True  # window closed: a real error
    f.active = True
    assert f.filter(_record(LOST)) is False and f.filter(_record(CANT, logging.WARNING)) is False
    assert f.filter(_record("Error executing query: (1146, \"Table 'states' doesn't exist\")")) is True  # not a connection error
    assert f.filter(_record("something", logging.INFO)) is True
    assert f.hidden == 2


def test_filter_looks_into_the_exception_too():
    f = quiet.PlannedRestartFilter()
    f.active = True
    try:
        raise RuntimeError(CANT)
    except RuntimeError:
        import sys

        assert f.filter(_record("Unexpected exception", exc=sys.exc_info())) is False


async def test_errors_during_a_paused_restart_are_hidden_and_counted(hass, recorder, sink):
    log = logging.getLogger("homeassistant.components.recorder.util")
    log.error(LOST)
    assert LOST in sink.messages  # before the pause: reported
    sink.messages.clear()

    await pause.async_pause(hass)
    log.error(LOST)
    log.error(CANT)
    log.error("Error executing query: (1146, \"Table 'states' doesn't exist\")")
    assert sink.messages == ["Error executing query: (1146, \"Table 'states' doesn't exist\")"]  # only the real error shows

    await pause.async_resume(hass)
    log.error(LOST)  # still inside the grace period
    assert len(sink.messages) == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=quiet.GRACE + 5))
    await hass.async_block_till_done()
    assert any("Hid 3 database connection error" in m for m in sink.messages)
    log.error(LOST)  # the window is over: reported again
    assert sink.messages[-1] == LOST
    assert "quiet" not in hass.data[DOMAIN]


async def test_unload_removes_the_filter(hass, recorder, sink):
    await pause.async_pause(hass)
    assert any(isinstance(f, quiet.PlannedRestartFilter) for f in sink.filters)
    pause.release_now(hass)
    assert not any(isinstance(f, quiet.PlannedRestartFilter) for f in sink.filters)
