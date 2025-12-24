"""Aquarite Light entity."""

from homeassistant.components.light import LightEntity
from homeassistant.core import HomeAssistant

from .entity import AquariteEntity
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:

    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False
        
    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)
    
    entities = [
        AquariteLightEntity(hass, dataservice, pool_id, pool_name, "Light", "light.status")
    ]

    async_add_entities(entities)

    return True

class AquariteLightEntity(AquariteEntity, LightEntity):

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name, delimiter="")

    @property
    def color_mode(self):
        return "ONOFF"

    @property
    def supported_color_modes(self):
        return {"ONOFF"}

    @property
    def is_on(self):
        """Return true if the device is on."""
        return bool(self._dataservice.get_value(self._value_path))

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 0)
