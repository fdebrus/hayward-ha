from homeassistant.components.select import SelectEntity
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
        AquaritePumpModeEntity(
            coordinator, pool_id, pool_name, "Pump Mode", "filtration.mode"
        ),
        AquaritePumpSpeedEntity(
            coordinator, pool_id, pool_name, "Pump Speed", "filtration.manVel"
        ),
    ]
    async_add_entities(entities)
    return True


class AquaritePumpModeEntity(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._allowed_values = ["Manual", "Auto", "Heat", "Smart", "Intel"]

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def options(self):
        return list(self._allowed_values)

    @property
    def current_option(self):
        idx = get_value(self.coordinator.data, self._value_path)
        try:
            return self._allowed_values[int(idx)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str):
        await self.coordinator.api.set_value(
            self._pool_id, self._value_path, self._allowed_values.index(option)
        )


class AquaritePumpSpeedEntity(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._allowed_values = ["Slow", "Medium", "High"]

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def options(self):
        return list(self._allowed_values)

    @property
    def current_option(self):
        idx = get_value(self.coordinator.data, self._value_path)
        try:
            return self._allowed_values[int(idx)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str):
        await self.coordinator.api.set_value(
            self._pool_id, self._value_path, self._allowed_values.index(option)
        )
