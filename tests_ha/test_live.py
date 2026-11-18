"""Live apply of recorder_studio.yaml to a running recorder (no restart)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.recorder_studio_db import live
from custom_components.recorder_studio_db.const import DOMAIN, VERSION


class FakeRecorder:
    """Has the attributes and methods live.py relies on; records what was done to it."""

    def __init__(self, listening=True):
        self.entity_filter = None
        self.exclude_event_types = set()
        self.keep_days, self.auto_purge, self.auto_repack, self.commit_interval = 10, True, True, 5
        self.db_url = ""
        self._event_listener = object() if listening else None
        self.calls = []
        self.fail_init = False

    def _async_stop_queue_watcher_and_event_listener(self):
        self.calls.append("stop")
        self._event_listener = None

    def async_initialize(self):
        self.calls.append("init")
        if self.fail_init and self.entity_filter is not None:
            raise RuntimeError("boom")
        self._event_listener = object()


def activate(config_dir, extra=""):
    (config_dir / "configuration.yaml").write_text("recorder: !include recorder_studio.yaml\n")
    (config_dir / "recorder_studio.yaml").write_text(
        "purge_keep_days: 3\nauto_purge: false\ncommit_interval: 5\nexclude:\n  entities:\n    - sensor.skip\n" + extra
    )


@pytest.fixture
def recorder(hass, config_dir):
    hass.data.setdefault(DOMAIN, {})
    rec = FakeRecorder()
    rec.db_url = f"sqlite:///{config_dir}/home-assistant_v2.db"
    with patch("homeassistant.helpers.recorder.get_instance", return_value=rec):
        yield rec


async def test_applies_filter_and_retention_without_restart(hass, config_dir, recorder):
    activate(config_dir)
    result = await live.async_apply_live(hass)
    assert result["applied"] and result["restart"] == [] and set(result["changed"]) == {"keep_days", "auto_purge", "filter"}
    assert (recorder.keep_days, recorder.auto_purge) == (3, False)
    assert recorder.entity_filter("sensor.skip") is False and recorder.entity_filter("sensor.other") is True
    assert recorder.calls == ["stop", "init"]


async def test_unchanged_rules_do_not_touch_the_listener_again(hass, config_dir, recorder):
    activate(config_dir)
    await live.async_apply_live(hass)
    recorder.calls.clear()
    result = await live.async_apply_live(hass)
    assert result["changed"] == [] and recorder.calls == []


async def test_database_url_and_commit_interval_still_need_a_restart(hass, config_dir, recorder):
    activate(config_dir, "db_url: mysql://u:p@h/db\n")
    (config_dir / "recorder_studio.yaml").write_text(
        (config_dir / "recorder_studio.yaml").read_text().replace("commit_interval: 5", "commit_interval: 30")
    )
    result = await live.async_apply_live(hass)
    assert result["applied"] and sorted(result["restart"]) == ["commit_interval", "db_url"]


async def test_not_included_in_configuration_yaml_means_restart(hass, config_dir, recorder):
    activate(config_dir)
    (config_dir / "configuration.yaml").write_text("recorder:\n  purge_keep_days: 5\n")
    result = await live.async_apply_live(hass)
    assert not result["applied"] and result["reason"] == "not_active" and result["restart"] == ["configuration"]
    assert recorder.calls == []  # the running recorder is not changed to something a restart would not use


async def test_paused_recorder_only_gets_the_new_filter_for_its_next_start(hass, config_dir, recorder):
    activate(config_dir)
    recorder._event_listener = None
    result = await live.async_apply_live(hass)
    assert result["applied"] and recorder.calls == [] and recorder.entity_filter("sensor.skip") is False


async def test_unknown_recorder_changes_nothing(hass, config_dir):
    activate(config_dir)
    hass.data.setdefault(DOMAIN, {})
    with patch("homeassistant.helpers.recorder.get_instance", return_value=SimpleNamespace(entity_filter=None)):
        result = await live.async_apply_live(hass)
    assert not result["applied"] and result["restart"] == ["all"] and "recorder_changed" in result["reason"]


async def test_failed_swap_restores_the_listener(hass, config_dir, recorder):
    activate(config_dir)
    recorder.fail_init = True
    result = await live.async_apply_live(hass)
    assert not result["applied"] and result["restart"] == ["all"]
    assert recorder._event_listener is not None  # never left without its event listener
    assert recorder.entity_filter is None  # the old filter is back


async def test_config_flow_creates_the_entry_and_the_service_answers(hass, config_dir, recorder):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    activate(config_dir)
    response = await hass.services.async_call(DOMAIN, "apply_config", blocking=True, return_response=True)
    assert response["applied"] is True and response["version"] == VERSION
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert again["type"] == "abort" and again["reason"] == "single_instance_allowed"
