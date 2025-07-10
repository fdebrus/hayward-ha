from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, BRAND, MODEL

import logging

_LOGGER = logging.getLogger(__name__)


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
    data = coordinator.data
    pool_id = coordinator.pool_id
    pool_name = coordinator.get_pool_name()

    entities = [
        AquariteNumberEntity(
            coordinator,
            pool_id,
            pool_name,
            500,
            800,
            "Redox Setpoint",
            "modules.rx.status.value",
        ),
        AquariteNumberEntity(
            coordinator,
            pool_id,
            pool_name,
            6,
            8,
            "pH Low",
            "modules.ph.status.low_value",
        ),
        AquariteNumberEntity(
            coordinator,
            pool_id,
            pool_name,
            6,
            8,
            "pH Max",
            "modules.ph.status.high_value",
        ),
        AquariteNumberEntity(
            coordinator,
            pool_id,
            pool_name,
            0,
            int(get_value(data, "hidro.maxAllowedValue")) / 10,
            "Electrolysis Setpoint",
            "hidro.level",
        ),
    ]
    async_add_entities(entities)
    return True


class AquariteNumberEntity(CoordinatorEntity, NumberEntity):
    SCALE_MAP = {
        "modules.ph.status.low_value": 100,
        "modules.ph.status.high_value": 100,
        "hidro.level": 10,
    }

    UNIT_MAP = {
        "modules.rx.status.value": "mV",
        "modules.ph.status.low_value": "pH",
        "modules.ph.status.high_value": "pH",
        "hidro.level": "gr/h",
    }

    def __init__(
        self, coordinator, pool_id, pool_name, value_min, value_max, name, value_path
    ):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._attr_native_step = 0.01
        self._attr_name = f"{pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._attr_native_unit_of_measurement = self.UNIT_MAP.get(value_path)

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self):
        raw_value = get_value(self.coordinator.data, self._value_path)
        if raw_value is None:
            return None
        scale = self.SCALE_MAP.get(self._value_path)
        return int(raw_value) / scale if scale else float(raw_value)

    async def async_set_native_value(self, value: float):
        scale = self.SCALE_MAP.get(self._value_path)
        raw_value = int(value * scale) if scale else value
        _LOGGER.debug(f"Setting value {raw_value} for {self._attr_name}")
        await self.coordinator.api.set_value(self._pool_id, self._value_path, raw_value)
        self.async_write_ha_state()
