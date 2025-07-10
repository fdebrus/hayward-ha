from homeassistant.components.switch import SwitchEntity
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
        AquariteSwitchEntity(
            coordinator, pool_id, pool_name, "Electrolysis Cover", "hidro.cover_enabled"
        ),
        AquariteSwitchEntity(
            coordinator,
            pool_id,
            pool_name,
            "Electrolysis Boost",
            "hidro.cloration_enabled",
        ),
        AquariteSwitchEntity(
            coordinator, pool_id, pool_name, "Relay1", "relays.relay1.info.onoff"
        ),
        AquariteSwitchEntity(
            coordinator, pool_id, pool_name, "Relay2", "relays.relay2.info.onoff"
        ),
        AquariteSwitchEntity(
            coordinator, pool_id, pool_name, "Relay3", "relays.relay3.info.onoff"
        ),
        AquariteSwitchEntity(
            coordinator, pool_id, pool_name, "Relay4", "relays.relay4.info.onoff"
        ),
        AquariteSwitchEntity(
            coordinator, pool_id, pool_name, "Filtration Status", "filtration.status"
        ),
    ]
    async_add_entities(entities)
    return True


class AquariteSwitchEntity(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path

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
    def is_on(self):
        data = self.coordinator.data
        onoff_value = bool(get_value(data, self._value_path))
        if "relay" in self._value_path:
            # Derive the corresponding status path by replacing 'onoff' with 'status'
            status_path = self._value_path.replace("onoff", "status")
            status_value = bool(get_value(data, status_path))
            return onoff_value or status_value
        return onoff_value

    async def async_turn_on(self, **kwargs):
        await self.coordinator.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.api.set_value(self._pool_id, self._value_path, 0)
