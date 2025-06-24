"""Aquarite Number entities."""

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

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
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 0, dataservice.get_value("hidro.maxAllowedValue"), "Hydrolysis Setpoint", "hidro.level")
    ]

    async_add_entities(entities)
    
    return True

class AquariteNumberEntity(CoordinatorEntity, NumberEntity):

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, value_min, value_max, name, value_path):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._attr_native_step = 0.01
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{self._pool_id}-{name}"
        # self._attr_device_class = "temperature"

    @property
    def unique_id(self):
        """The unique id of the number."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self):
        """Return the current native value."""
        raw_value = self._dataservice.get_value(self._value_path)
        if self._value_path in ["modules.ph.status.low_value", "modules.ph.status.high_value"]:
            return int(raw_value) / 100 if raw_value is not None else None
        return raw_value

    async def async_set_native_value(self, value: float):
        """Update the current native value."""
        if self._value_path in ["modules.ph.status.low_value", "modules.ph.status.high_value"]:
            raw_value = int(value * 100)
        else:
            raw_value = value
        _LOGGER.debug(f"Setting value {raw_value}")
        await self._dataservice.api.set_value(self._pool_id, self._value_path, raw_value)
        self.async_write_ha_state()
