"""Aquarite Device Tracker entity."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BRAND, DOMAIN, MODEL


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the pool location tracker."""

    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return

    coordinator = entry_data["coordinator"]

    pool_id = coordinator.get_value("id")
    pool_name = coordinator.get_pool_name(pool_id)
    lat_sensor = f"sensor.{pool_name}_latitude"
    lon_sensor = f"sensor.{pool_name}_longitude"

    async_add_entities(
        [
            PoolLocationDeviceTracker(
                hass,
                coordinator,
                pool_id,
                pool_name,
                lat_sensor,
                lon_sensor,
                "mdi:pool",
            )
        ]
    )


class PoolLocationDeviceTracker(TrackerEntity):
    """Device tracker representing pool location."""

    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        pool_id: str,
        pool_name: str,
        latitude_sensor: str,
        longitude_sensor: str,
        icon: str,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name} Location"
        self._attr_unique_id = f"{pool_name}_location_tracker"
        self._attr_icon = icon
        self.latitude_sensor = latitude_sensor
        self.longitude_sensor = longitude_sensor
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.pool_id)},
            name=self._pool_name,
            manufacturer=BRAND,
            model=MODEL,
        )

    @staticmethod
    def _state_to_float(state: State | None) -> float | None:
        """Convert a state object to a float if possible."""

        if state is None or state.state in (None, "unknown", "unavailable"):
            return None

        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    @property
    def latitude(self) -> float | None:
        """Return the latitude from the linked sensor."""

        return self._state_to_float(self.hass.states.get(self.latitude_sensor))

    @property
    def longitude(self) -> float | None:
        """Return the longitude from the linked sensor."""

        return self._state_to_float(self.hass.states.get(self.longitude_sensor))
