"""Aquarite Select entities."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass : HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN].get(entry.entry_id)

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquaritePumpModeEntity(hass, dataservice, pool_id, pool_name, "Pump Mode", "filtration.mode"),
        AquaritePumpSpeedEntity(hass, dataservice, pool_id, pool_name, "Pump Speed", "filtration.manVel")
    ]

    async_add_entities(entities)

    return True

class AquaritePumpModeEntity(CoordinatorEntity, SelectEntity):

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = dataservice.get_value("id") + name
        self._allowed_values = ["Manual", "Auto", "Heat", "Smart", "Intel"]
    
    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (DOMAIN, self._pool_id)
            },
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def options(self) -> list[str]:
        return list(self._allowed_values)

    @property
    def current_option(self) -> str:
        """Return current pump mode"""      
        return self._allowed_values[self._dataservice.get_value(self._value_path)]

    async def async_select_option(self, option: str):
        """Set pump mode"""
        await self._dataservice.api.set_pump_mode(self._pool_id, self._allowed_values.index(option))

class AquaritePumpSpeedEntity(CoordinatorEntity, SelectEntity):

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        """Initialize a Aquarite Select Entity."""
        super().__init__(dataservice)
        """ self._attr_device_info =  """
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = dataservice.get_value("id") + name
        self._allowed_values = ["Slow", "Medium", "High"]

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (DOMAIN, self._pool_id)
            },
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def options(self) -> list[str]:
        return list(self._allowed_values)

    @property
    def current_option(self) -> str:
        """Return current pump speed"""      
        return self._allowed_values[self._dataservice.get_value(self._value_path)]

    async def async_select_option(self, option: str):
        """Set pump speed"""
        await self._dataservice.api.set_pump_speed(self._pool_id, self._allowed_values.index(option))

