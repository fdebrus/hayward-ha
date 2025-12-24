"""Aquarite Number entities."""

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant

from .entity import AquariteEntity
from .const import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:

    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 500, 800, "Redox Setpoint", "modules.rx.status.value"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 6, 8, "pH Low", "modules.ph.status.low_value"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 6, 8, "pH Max", "modules.ph.status.high_value"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 0, int(dataservice.get_value("hidro.maxAllowedValue"))/10, "Electrolysis Setpoint", "hidro.level")
    ]

    async_add_entities(entities)
    
    return True

class AquariteNumberEntity(AquariteEntity, NumberEntity):

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

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, value_min, value_max, name, value_path):
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._attr_native_step = 0.01
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)
        self._attr_unit_of_measurement = self.UNIT_MAP.get(value_path)

    @property
    def native_value(self):
        """Return the current native value."""
        raw_value = self._dataservice.get_value(self._value_path)
        if raw_value is None:
            return None
        scale = self.SCALE_MAP.get(self._value_path)
        return int(raw_value) / scale if scale else raw_value

    async def async_set_native_value(self, value: float):
        """Update the current native value."""
        scale = self.SCALE_MAP.get(self._value_path)
        raw_value = int(value * scale) if scale else value

        _LOGGER.debug(f"Setting value {raw_value}")
        await self._dataservice.api.set_value(self._pool_id, self._value_path, raw_value)
        self.async_write_ha_state()