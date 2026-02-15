"""Aquarite Number entities."""
import logging
from typing import Final

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AquariteEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Aquarite number entities."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]
    pool_id, pool_name = dataservice.pool_id, entry.title
    
    # Safely determine max electrolysis
    raw_max = dataservice.get_value("hidro.maxAllowedValue", 0)
    max_electrolysis = int(raw_max) / 10 if raw_max else 50.0

    entities = [
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 500, 800, "Redox Setpoint", "modules.rx.status.value"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 6, 8, "pH Low", "modules.ph.status.low_value"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 6, 8, "pH Max", "modules.ph.status.high_value"),
        AquariteNumberEntity(hass, dataservice, pool_id, pool_name, 0, max_electrolysis, "Electrolysis Setpoint", "hidro.level"),
    ]

    async_add_entities(entities)
    return True


class AquariteNumberEntity(AquariteEntity, NumberEntity):
    """Number entity for Aquarite data points."""
    SCALE_MAP: Final = {
        "modules.ph.status.low_value": 100,
        "modules.ph.status.high_value": 100,
        "hidro.level": 10,
    }
    UNIT_MAP: Final = {
        "modules.rx.status.value": "mV",
        "modules.ph.status.low_value": "pH",
        "modules.ph.status.high_value": "pH",
        "hidro.level": "gr/h",
    }

    def __init__(self, hass, dataservice, pool_id, pool_name, value_min, value_max, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)
        self._attr_unit_of_measurement = self.UNIT_MAP.get(value_path)
        self._attr_native_step = self._get_scaled_step()

    def _get_scaled_step(self) -> float:
        scale = self.SCALE_MAP.get(self._value_path)
        return 1 / scale if scale else 1.0

    @property
    def native_value(self):
        raw_value = self._dataservice.get_value(self._value_path)
        if raw_value is None: return None
        scale = self.SCALE_MAP.get(self._value_path)
        return int(raw_value) / scale if scale else raw_value

    async def async_set_native_value(self, value: float) -> None:
        scale = self.SCALE_MAP.get(self._value_path)
        raw_value = int(value * scale) if scale else value
        await self._dataservice.api.set_value(self._pool_id, self._value_path, raw_value)
        self.async_write_ha_state()