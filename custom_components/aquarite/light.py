"""Aquarite Light entity with State Reconciliation and Failure Handling."""
import time
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AquariteEntity
from .const import DOMAIN

# How long to wait for the cloud to confirm before reverting the UI
RECONCILIATION_TIMEOUT = 20 

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the Aquarite light platform."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]
    pool_id, pool_name = dataservice.pool_id, entry.title

    entities = [
        AquariteLightEntity(hass, dataservice, pool_id, pool_name, "Light", "light.status")
    ]
    async_add_entities(entities)
    return True

class AquariteLightEntity(AquariteEntity, LightEntity):
    def __init__(self, hass, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name, delimiter="")
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        
        # Reconciliation logic
        self._target_state = None
        self._target_set_at = 0

    @property
    def is_on(self):
        """Return true if light is on."""
        actual_state = bool(self._dataservice.get_value(self._value_path))
        
        # 1. If we aren't waiting for a change, show actual state
        if self._target_state is None:
            return actual_state

        # 2. Check if the cloud has finally matched our request
        if actual_state == self._target_state:
            self._target_state = None
            return actual_state

        # 3. Check if we've waited too long (Timeout)
        if (time.time() - self._target_set_at) > RECONCILIATION_TIMEOUT:
            self._target_state = None
            return actual_state

        # 4. Otherwise, stay optimistic
        return self._target_state

    async def _send_command(self, state: bool):
        """Set target state and trigger API."""
        self._target_state = state
        self._target_set_at = time.time()
        self.async_write_ha_state()
        
        try:
            await self._dataservice.api.set_value(self._pool_id, self._value_path, 1 if state else 0)
        except Exception:
            # If the API call fails immediately, reset and revert UI
            self._target_state = None
            self.async_write_ha_state()
            raise

    async def async_turn_on(self, **kwargs):
        await self._send_command(True)

    async def async_turn_off(self, **kwargs):
        await self._send_command(False)