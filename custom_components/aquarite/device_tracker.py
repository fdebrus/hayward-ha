"""Aquarite Device Tracker entity."""

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker import SourceType

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]

    pool_id = coordinator.get_value("id")
    pool_name = coordinator.get_pool_name(pool_id)
    lat_sensor = f"sensor.{pool_name}_latitude"
    lon_sensor = f"sensor.{pool_name}_longitude"
    icon = "mdi:pool"

    async_add_entities([
        PoolLocationDeviceTracker(
            hass,
            coordinator,
            pool_id,
            pool_name,
            lat_sensor,
            lon_sensor,
            icon,
        )
    ])


class PoolLocationDeviceTracker(TrackerEntity):
    def __init__(self, hass, coordinator, pool_id, pool_name, latitude_sensor, longitude_sensor, icon):
        self.hass = hass
        self.coordinator = coordinator
        self.pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name} Location"
        self._attr_unique_id = f"{pool_name}_location_tracker"
        self._attr_source_type = SourceType.GPS
        self._attr_icon = icon
        self.latitude_sensor = latitude_sensor
        self.longitude_sensor = longitude_sensor

    @property
    def device_info(self):
        """Group tracker with the pool device."""
        return {
            "identifiers": {(DOMAIN, self.pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def latitude(self):
        state_obj = self.hass.states.get(self.latitude_sensor)
        if state_obj is None or state_obj.state in (None, "unknown", "unavailable"):
            return None
        try:
            return float(state_obj.state)
        except ValueError:
            return None

    @property
    def longitude(self):
        state_obj = self.hass.states.get(self.longitude_sensor)
        if state_obj is None or state_obj.state in (None, "unknown", "unavailable"):
            return None
        try:
            return float(state_obj.state)
        except ValueError:
            return None
