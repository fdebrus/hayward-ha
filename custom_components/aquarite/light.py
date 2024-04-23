"""Aquarite Light entity."""

from homeassistant.components.light import LightEntity
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
        AquariteLightEntity(hass, dataservice, pool_id, pool_name, "Light", "light.status")
    ]

    async_add_entities(entities)

    return True

class AquariteLightEntity(CoordinatorEntity, LightEntity):

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{self._pool_id}{name}"

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
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id

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
        await self._dataservice.api.turn_on_switch(self._pool_id, self._value_path)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._dataservice.api.turn_off_switch(self._pool_id, self._value_path)

