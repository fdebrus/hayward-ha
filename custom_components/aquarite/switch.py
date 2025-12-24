"""Aquarite Switch entity."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant

from .entity import AquariteEntity
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]

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
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Relay4", "relays.relay4.info.onoff"),
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, "Filtration Status", "filtration.status")
    ]
    
    async_add_entities(entities)

    return True

class AquariteSwitchEntity(AquariteEntity, SwitchEntity):
    """Aquarite Switch Entity."""

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        """Initialize a Aquarite Switch Entity."""
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name, delimiter="")

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return extra attributes."""
        if "relay" in self._attr_name: 
            return {"name": self._dataservice.get_value(f"relays.{self._value_path}.name")}

    @property
    def is_on(self):
        """Return true if the device is on."""
        return bool(self._dataservice.get_value(self._value_path))

    @property
    def is_on(self):
        """Return true if the device is on."""
        onoff_value = bool(self._dataservice.get_value(self._value_path))
    
        if "relay" in self._value_path:
            # Derive the corresponding status path by replacing 'onoff' with 'status'
            status_path = self._value_path.replace('onoff', 'status')
            status_value = bool(self._dataservice.get_value(status_path))
            return onoff_value or status_value

        return onoff_value

    async def async_turn_on(self):
        """Turn the entity on."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self):
        """Turn the entity off."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 0)

