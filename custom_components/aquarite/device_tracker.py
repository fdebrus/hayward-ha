"""Aquarite Device Tracker entity."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AquariteEntity

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the pool location tracker."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return

    coordinator = entry_data["coordinator"]
    pool_id = coordinator.pool_id
    pool_name = entry.title

    async_add_entities([
        PoolLocationDeviceTracker(coordinator, pool_id, pool_name)
    ])

class PoolLocationDeviceTracker(AquariteEntity, TrackerEntity):
    """Device tracker representing pool location."""

    _attr_source_type = SourceType.GPS
    _attr_icon = "mdi:pool"

    def __init__(self, coordinator, pool_id, pool_name) -> None:
        """Initialize the tracker."""
        # Inherits Device Info and Coordinator logic from your base class
        super().__init__(coordinator, pool_id, pool_name, name_suffix="Location")
        # Uses a stable unique ID based on the pool_id
        self._attr_unique_id = f"{pool_id}-location-tracker"

    @property
    def latitude(self) -> float | None:
        """Return latitude directly from coordinator data."""
        try:
            # Pulls from 'form.lat' in the Firestore document
            val = self._dataservice.get_value("form.lat")
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude directly from coordinator data."""
        try:
            # Pulls from 'form.lng' in the Firestore document
            val = self._dataservice.get_value("form.lng")
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None