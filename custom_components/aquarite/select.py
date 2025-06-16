"""Aquarite Select entities."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up Aquarite select entities from a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]
    
    if not dataservice:
        return False

    pool_id = entry.data["pool_id"]
    pool_name = entry.data.get("pool_name", pool_id)

    entities = [
        AquaritePumpModeEntity(hass, dataservice, pool_id, pool_name, "Pump Mode", "filtration.mode"),
        AquaritePumpSpeedEntity(hass, dataservice, pool_id, pool_name, "Pump Speed", "filtration.manVel")
    ]

    async_add_entities(entities)
    return True

class AquaritePumpModeEntity(CoordinatorEntity, SelectEntity):
    """Aquarite Select Entity for Pump Mode."""

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._value_path = value_path
        self._attr_name = f"{self._pool_name}_{name}"
        self._attr_unique_id = f"{self._pool_id}-{name}"
        self._allowed_values = ["Manual", "Auto", "Heat", "Smart", "Intel"]

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
    def options(self) -> list[str]:
        return list(self._allowed_values)

    @property
    def current_option(self) -> str:
        """Return current pump mode."""
        idx = self._dataservice.get_value(self._value_path)
        try:
            return self._allowed_values[idx]
        except Exception:
            return None

    async def async_select_option(self, option: str):
        """Set pump mode."""
        if option in self._allowed_values:
            await self._dataservice.api.set_value(self._pool_id, self._value_path, self._allowed_values.index(option))

class AquaritePumpSpeedEntity(CoordinatorEntity, SelectEntity):
    """Aquarite Select Entity for Pump Speed."""

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._value_path = value_path
        self._attr_name = f"{self._pool_name}_{name}"
        self._attr_unique_id = f"{self._pool_id}-{name}"
        self._allowed_values = ["Slow", "Medium", "High"]

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
    def options(self) -> list[str]:
        return list(self._allowed_values)

    @property
    def current_option(self) -> str:
        """Return current pump speed."""
        idx = self._dataservice.get_value(self._value_path)
        try:
            return self._allowed_values[idx]
        except Exception:
            return None

    async def async_select_option(self, option: str):
        """Set pump speed."""
        if option in self._allowed_values:
            await self._dataservice.api.set_value(self._pool_id, self._value_path, self._allowed_values.index(option))
