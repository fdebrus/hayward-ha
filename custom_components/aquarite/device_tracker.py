"""Aquarite Device Tracker entity."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity, async_setup_pool_platform

PARALLEL_UPDATES = 0


def _build_entities(
    coordinator: AquariteDataUpdateCoordinator,
) -> list[PoolLocationDeviceTracker]:
    """Build the location tracker for one pool."""
    return [
        PoolLocationDeviceTracker(
            coordinator, coordinator.pool_id, coordinator.pool_name
        )
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool location tracker for every pool on the account."""
    async_setup_pool_platform(hass, entry, async_add_entities, _build_entities)


class PoolLocationDeviceTracker(AquariteEntity, TrackerEntity):
    """Device tracker representing pool location."""

    _attr_source_type = SourceType.GPS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "location"

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, pool_id, pool_name)
        self._attr_unique_id = self.build_unique_id("location-tracker")

    @property
    def latitude(self) -> float | None:
        """Return latitude directly from coordinator data."""
        try:
            val = self.coordinator.get_value("form.lat")
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude directly from coordinator data."""
        try:
            val = self.coordinator.get_value("form.lng")
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None
