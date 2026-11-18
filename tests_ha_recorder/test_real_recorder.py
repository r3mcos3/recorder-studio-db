"""Live apply against a real recorder: a newly excluded entity stops being recorded without a restart."""
from custom_components.recorder_studio_db import live
from custom_components.recorder_studio_db.const import DOMAIN


def activate(config_dir):
    (config_dir / "configuration.yaml").write_text("recorder: !include recorder_studio.yaml\n")
    (config_dir / "recorder_studio.yaml").write_text("exclude:\n  entities:\n    - sensor.skip\n")


async def test_real_recorder_stops_recording_a_newly_excluded_entity(recorder_mock, hass, config_dir):
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.db_schema import StatesMeta
    from homeassistant.components.recorder.util import session_scope
    from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

    hass.data.setdefault(DOMAIN, {})
    # the real recorder uses an in-memory database here; the url comparison then (rightly) asks for a restart for db_url
    hass.states.async_set("sensor.skip", "1")
    hass.states.async_set("sensor.keep", "1")
    await async_wait_recording_done(hass)
    activate(config_dir)
    result = await live.async_apply_live(hass)
    assert result["applied"] and "filter" in result["changed"]
    hass.states.async_set("sensor.skip", "2")
    hass.states.async_set("sensor.keep", "2")
    hass.states.async_set("sensor.new_entity", "1")
    await async_wait_recording_done(hass)

    def known() -> dict:
        with session_scope(hass=hass, read_only=True) as session:
            from homeassistant.components.recorder.db_schema import States

            rows = session.query(StatesMeta.entity_id, States.state).join(States, States.metadata_id == StatesMeta.metadata_id).all()
            return {(r[0], r[1]) for r in rows}

    states = await get_instance(hass).async_add_executor_job(known)
    instance = get_instance(hass)
    # a listener that expects the (dropped) index of queued states would raise on every state change
    assert not (instance._queued_states is None and instance._queued_states_listener is not None)
    assert ("sensor.skip", "2") not in states  # excluded without a restart
    assert ("sensor.keep", "2") in states and ("sensor.new_entity", "1") in states  # everything else is still recorded
