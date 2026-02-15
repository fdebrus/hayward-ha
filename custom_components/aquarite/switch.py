from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .entity import AquariteEntity

# Added Relay 3 and Relay 4 to the definitions
SWITCH_DEFINITIONS = (
    ("Electrolysis Cover", "hidro.cover_enabled"),
    ("Electrolysis Boost", "hidro.cloration_enabled"),
    ("Relay1", "relays.relay1.info.onoff"),
    ("Relay2", "relays.relay2.info.onoff"),
    ("Relay3", "relays.relay3.info.onoff"),
    ("Relay4", "relays.relay4.info.onoff"),
    ("Filtration Status", "filtration.status"),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> bool:
    """Set up the Aquarite switch platform."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]
    pool_id, pool_name = dataservice.pool_id, entry.title

    async_add_entities([
        AquariteSwitchEntity(hass, dataservice, pool_id, pool_name, name, path)
        for name, path in SWITCH_DEFINITIONS
    ])
    return True

class AquariteSwitchEntity(AquariteEntity, SwitchEntity):
    """Representation of an Aquarite switch."""
    
    def __init__(self, hass, dataservice, pool_id, pool_name, name, value_path):
        """Initialize the switch."""
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name, delimiter="")

    @property
    def is_on(self):
        """Return true if switch is on."""
        onoff = bool(self._dataservice.get_value(self._value_path))
        # Logic to check both the command (onoff) and the feedback status for relays
        if "relay" in self._value_path:
            status_path = self._value_path.replace('onoff', 'status')
            status = bool(self._dataservice.get_value(status_path))
            return onoff or status
        return onoff

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 0)