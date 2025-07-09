"""Aquarite Device Tracker entity."""

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker import SourceType

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]

    # Create and add the device tracker
    async_add_entities([PoolLocationDeviceTracker(hass, coordinator)])

class PoolLocationDeviceTracker(TrackerEntity):
    def __init__(self, hass, coordinator):
        self.hass = hass
        self.coordinator = coordinator
        self._attr_name = "Pool Location"
        self._attr_unique_id = "pool_location_tracker"
        self._attr_source_type = SourceType.GPS

    @property
    def latitude(self):
        # Example: fetch from sensor state
        return float(self.hass.states.get('sensor.pool_latitude').state)

    @property
    def longitude(self):
        return float(self.hass.states.get('sensor.pool_longitude').state)
