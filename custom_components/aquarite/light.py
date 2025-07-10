from homeassistant.components.light import LightEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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

    entities = [
        AquariteLightEntity(coordinator, pool_id, pool_name, "Light", "light.status"),
    ]
    async_add_entities(entities)
    return True


class AquariteLightEntity(CoordinatorEntity, LightEntity):
    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def color_mode(self):
        return "ONOFF"

    @property
    def supported_color_modes(self):
        return {"ONOFF"}

    @property
    def is_on(self):
        return bool(get_value(self.coordinator.data, self._value_path))

    async def async_turn_on(self, **kwargs):
        await self.coordinator.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.api.set_value(self._pool_id, self._value_path, 0)
