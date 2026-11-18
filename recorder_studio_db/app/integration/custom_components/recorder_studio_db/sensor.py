"""Diagnostic sensors with the database figures the Recorder Studio DB add-on measures."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SIGNAL_METRICS

_SIZE = dict(
    device_class=SensorDeviceClass.DATA_SIZE,
    native_unit_of_measurement=UnitOfInformation.BYTES,
    suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    suggested_display_precision=1,
    state_class=SensorStateClass.MEASUREMENT,
)
_COUNT = dict(state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0)

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="database_size", translation_key="database_size", icon="mdi:database", **_SIZE),
    SensorEntityDescription(key="states_size", translation_key="states_size", icon="mdi:table", **_SIZE),
    SensorEntityDescription(key="attributes_size", translation_key="attributes_size", icon="mdi:table", **_SIZE),
    SensorEntityDescription(key="events_size", translation_key="events_size", icon="mdi:table", **_SIZE),
    SensorEntityDescription(key="statistics_size", translation_key="statistics_size", icon="mdi:table", **_SIZE),
    SensorEntityDescription(key="states_count", translation_key="states_count", icon="mdi:counter", **_COUNT),
    SensorEntityDescription(key="events_count", translation_key="events_count", icon="mdi:counter", **_COUNT),
    SensorEntityDescription(key="statistics_count", translation_key="statistics_count", icon="mdi:counter", **_COUNT),
    SensorEntityDescription(key="records_per_day", translation_key="records_per_day", icon="mdi:chart-line", **_COUNT),
    SensorEntityDescription(key="oldest_record", translation_key="oldest_record", device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:history"),
    SensorEntityDescription(key="growth_per_day", translation_key="growth_per_day", icon="mdi:trending-up", **_SIZE),
    SensorEntityDescription(
        key="fragmentation", translation_key="fragmentation", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1, icon="mdi:chart-donut",
    ),
    SensorEntityDescription(key="reclaimable", translation_key="reclaimable", icon="mdi:broom", **_SIZE),
    SensorEntityDescription(key="disk_free", translation_key="disk_free", icon="mdi:harddisk", **{**_SIZE, "suggested_unit_of_measurement": UnitOfInformation.GIGABYTES}),
    SensorEntityDescription(
        key="days_to_full", translation_key="days_to_full", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0, icon="mdi:calendar-alert",
    ),
    SensorEntityDescription(key="engine", translation_key="engine", icon="mdi:database-cog"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(StudioSensor(entry, description) for description in SENSORS)


class StudioSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, description: SensorEntityDescription) -> None:
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="Recorder Studio DB", manufacturer="Recorder Studio DB",
            model="Database monitor", entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_METRICS, self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        value = (self.hass.data.get(DOMAIN, {}).get("metrics") or {}).get(self.entity_description.key)
        if value is None:
            return None
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(str(value))
        return value
