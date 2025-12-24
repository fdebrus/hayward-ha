"""Aquarite Select entities."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant

from .entity import AquariteEntity
from .const import DOMAIN

async def async_setup_entry(hass : HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]
    
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

class AquaritePumpModeEntity(AquariteEntity, SelectEntity):

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name, delimiter="")
        self._allowed_values = ["Manual", "Auto", "Heat", "Smart", "Intel"]

    @property
    def options(self) -> list[str]:
        return list(self._allowed_values)

    @property
    def current_option(self) -> str:
        """Return current pump mode"""      
        return self._allowed_values[self._dataservice.get_value(self._value_path)]

    async def async_select_option(self, option: str):
        """Set pump mode"""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, self._allowed_values.index(option))

class AquaritePumpSpeedEntity(AquariteEntity, SelectEntity):

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        """Initialize a Aquarite Select Entity."""
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name, delimiter="")
        self._allowed_values = ["Slow", "Medium", "High"]

    @property
    def options(self) -> list[str]:
        return list(self._allowed_values)

    @property
    def current_option(self) -> str:
        """Return current pump speed"""      
        return self._allowed_values[self._dataservice.get_value(self._value_path)]

    async def async_select_option(self, option: str):
        """Set pump speed"""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, self._allowed_values.index(option))

