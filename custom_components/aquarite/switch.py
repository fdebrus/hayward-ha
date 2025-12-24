"""Aquarite Switch entity."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import AquariteEntity


SWITCH_ENTITY_DEFINITIONS = (
    ("Electrolysis Cover", "hidro.cover_enabled"),
    ("Electrolysis Boost", "hidro.cloration_enabled"),
    ("Relay1", "relays.relay1.info.onoff"),
    ("Relay2", "relays.relay2.info.onoff"),
    ("Relay3", "relays.relay3.info.onoff"),
    ("Relay4", "relays.relay4.info.onoff"),
    ("Filtration Status", "filtration.status"),
)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up a config entry."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, name, value_path)
        for name, value_path in SWITCH_ENTITY_DEFINITIONS
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
        if "relays." in self._value_path:
            relay_name_path = self._value_path.replace(".onoff", ".name")
            relay_name = self._dataservice.get_value(relay_name_path)
            if relay_name is not None:
                return {"name": relay_name}

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

