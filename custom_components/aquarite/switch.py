"""Aquarite Switch entity."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False

    pool_id = entry.data["pool_id"]
    pool_name = entry.data.get("pool_name", pool_id)

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

class AquariteSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Aquarite Switch Entity."""

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._attr_unique_id = f"{self._pool_id}-{name}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._dataservice.data is not None

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
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return extra attributes (relay name if relay)."""
        try:
            if "relay" in self._attr_name:
                relay_name_path = self._value_path.replace(".onoff", ".name")
                relay_name = self._dataservice.get_value(relay_name_path)
                return {"name": relay_name}
        except Exception:
            return None
        return None

    @property
    def is_on(self):
        """Return true if the device is on."""
        try:
            onoff_value = bool(self._dataservice.get_value(self._value_path))
            if "relay" in self._value_path:
                # Derive the corresponding status path by replacing 'onoff' with 'status'
                status_path = self._value_path.replace('onoff', 'status')
                status_value = bool(self._dataservice.get_value(status_path))
                return onoff_value or status_value
            return onoff_value
        except Exception:
            return False

    async def async_turn_on(self):
        """Turn the entity on."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self):
        """Turn the entity off."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 0)
