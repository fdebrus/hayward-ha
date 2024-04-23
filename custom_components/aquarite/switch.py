"""Aquarite Switch entity."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN].get(entry.entry_id)

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Electrolysis Cover", "hidro.cover_enabled"),
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Electrolysis Boost", "hidro.cloration_enabled"),
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Relay1", "relays.relay1.info.onoff"),
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Relay2", "relays.relay2.info.onoff"),
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Relay3", "relays.relay3.info.onoff"),
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Filtration Status", "filtration.status")
    ]
    
    async_add_entities(entities)

    return True

class AquariteSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Aquarite Switch Entity."""

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        """Initialize a Aquarite Switch Entity."""
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

    # @property
    # def extra_state_attributes(self) -> dict[str, str] | None:
    #     """Return extra attributes."""
    #     return {"name": self._dataservice.get_value(f"relays.{self._value_path.lower()}.name")}

    @property
    def is_on(self):
        """Return true if the device is on."""
        return bool(self._dataservice.get_value(self._value_path))
        
    async def async_turn_on(self):
        """Turn the entity on."""
        await self._dataservice.api.turn_on_switch(self._pool_id, self._value_path)

    async def async_turn_off(self):
        """Turn the entity off."""
        await self._dataservice.api.turn_off_switch(self._pool_id, self._value_path)

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id
