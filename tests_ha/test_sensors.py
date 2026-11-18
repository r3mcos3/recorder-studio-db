"""The sensors that show the database figures measured by the add-on."""
import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.recorder_studio_db.const import DOMAIN
from custom_components.recorder_studio_db.sensor import SENSORS

METRICS = {
    "engine": "MariaDB 11.8.9", "database_size": 5_000_000, "states_size": 3_000_000, "attributes_size": 1_000_000, "events_size": 500_000,
    "statistics_size": 400_000, "states_count": 641_768, "events_count": 57_157, "statistics_count": 2_038_417, "records_per_day": 45_000,
    "oldest_record": "2026-11-04T04:12:05+00:00", "growth_per_day": 1_000_000, "fragmentation": 3.5, "reclaimable": 175_000,
    "disk_free": 20_000_000_000, "days_to_full": 400,
}


@pytest.fixture
async def entry(hass, config_dir):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


def state_of(hass, entry, key):
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id, f"no sensor for {key}"
    return hass.states.get(entity_id)


async def test_every_figure_has_a_diagnostic_sensor(hass, entry):
    reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(reg, entry.entry_id)
    assert len(entities) == len(SENSORS) == 16
    assert all(e.entity_category and e.entity_category.value == "diagnostic" for e in entities)
    assert state_of(hass, entry, "database_size").state == "unknown"  # nothing measured yet


async def test_service_fills_the_sensors(hass, entry):
    await hass.services.async_call(DOMAIN, "update_metrics", {"metrics": METRICS}, blocking=True)
    await hass.async_block_till_done()
    assert float(state_of(hass, entry, "database_size").state) == pytest.approx(5.0)  # shown in MB
    assert float(state_of(hass, entry, "disk_free").state) == pytest.approx(20.0)  # shown in GB
    assert state_of(hass, entry, "states_count").state == "641768"
    assert float(state_of(hass, entry, "fragmentation").state) == 3.5
    assert state_of(hass, entry, "engine").state == "MariaDB 11.8.9"
    assert state_of(hass, entry, "oldest_record").state.startswith("2026-11-04T04:12:05")
    assert float(state_of(hass, entry, "days_to_full").state) == 400


async def test_unknown_figures_stay_unknown(hass, entry):
    await hass.services.async_call(DOMAIN, "update_metrics", {"metrics": {**METRICS, "fragmentation": None, "oldest_record": None}}, blocking=True)
    await hass.async_block_till_done()
    assert state_of(hass, entry, "fragmentation").state == "unknown"
    assert state_of(hass, entry, "oldest_record").state == "unknown"
    assert float(state_of(hass, entry, "database_size").state) == pytest.approx(5.0)


async def test_last_figures_survive_a_reload(hass, entry):
    await hass.services.async_call(DOMAIN, "update_metrics", {"metrics": METRICS}, blocking=True)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert state_of(hass, entry, "states_count").state == "641768"


async def test_wrong_payload_is_refused(hass, entry):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "update_metrics", {"metrics": "nope"}, blocking=True)
