"""Aquarite Number entities."""

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:

    dataservice = hass.data[DOMAIN].get(entry.entry_id)

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, "Filtration_Smart_MinTemp", "filtration.smart.tempMin"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, "Filtration_Smart_HighTemp", "filtration.smart.tempHigh")
    ]

    async_add_entities(entities)
    
    return True

class AquariteNumberEntity(CoordinatorEntity, NumberEntity):

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path):
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_native_min_value = 12.0
        self._attr_native_max_value = 35.0
        self._attr_native_step = 0.5
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{self._pool_id}-{name}"
        self._attr_device_class = "temperature"

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
        return self._dataservice.get_value(self._value_path)

    async def async_set_native_value(self, value: float):
        """Update the current native value."""
        await self._dataservice.api.set_path_value(self._pool_id, self._value_path, value)
        self.async_write_ha_state()
