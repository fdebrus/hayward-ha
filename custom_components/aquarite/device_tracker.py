from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker import SourceType
from .const import DOMAIN, BRAND, MODEL


def get_value(data, path):
    keys = path.split(".")
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    pool_id = coordinator.pool_id
    pool_name = coordinator.get_pool_name()
    icon = "mdi:pool"

    async_add_entities(
        [PoolLocationDeviceTracker(coordinator, pool_id, pool_name, icon)]
    )


class PoolLocationDeviceTracker(TrackerEntity):
    def __init__(self, coordinator, pool_id, pool_name, icon):
        self.coordinator = coordinator
        self.pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name} Location"
        self._attr_unique_id = f"{pool_name}_location_tracker"
        self._attr_source_type = SourceType.GPS
        self._attr_icon = icon

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def latitude(self):
        lat = get_value(self.coordinator.data, "form.lat")
        try:
            return float(lat) if lat not in (None, "unknown", "unavailable") else None
        except ValueError:
            return None

    @property
    def longitude(self):
        lng = get_value(self.coordinator.data, "form.lng")
        try:
            return float(lng) if lng not in (None, "unknown", "unavailable") else None
        except ValueError:
            return None
