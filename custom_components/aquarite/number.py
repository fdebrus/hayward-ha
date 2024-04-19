from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN].get(entry.entry_id)
    if not dataservice:
        return False

    entities = [
        AquariteNumberEntity(hass, dataservice, "Filtration_Smart_MinTemp", "filtration.smart.tempMin"),
        AquariteNumberEntity(hass, dataservice, "Filtration_Smart_HighTemp", "filtration.smart.tempHigh")
    ]

    async_add_entities(entities)
    return True

class AquariteNumberEntity(CoordinatorEntity, NumberEntity):
    """Define a number entity for adjusting temperature settings on an Aqua Rite device."""

    def __init__(self, hass: HomeAssistant, dataservice, name, value_path):
        """Initialize."""
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = dataservice.get_value("id")
        self._attr_native_min_value = 12.0
        self._attr_native_max_value = 35.0
        self._attr_native_step = 0.5
        self._attr_name = f"{dataservice.get_pool_name(self._pool_id)}_{name}"
        self._value_path = value_path
        self._unique_id = f"{self._pool_id}-{name}"
        self._attr_device_class = "temperature"

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        pool_name = self._dataservice.get_pool_name(self._pool_id)
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self):
        """Return the current native value."""
        return self._dataservice.get_value(self._value_path)

    async def async_set_native_value(self, value: float):
        """Update the current native value."""
        await self._dataservice.set_path_value(self._pool_id, self._value_path, value)
        self.async_write_ha_state()
