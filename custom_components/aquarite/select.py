"""Aquarite Select entities."""
from __future__ import annotations
from collections.abc import Sequence

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AquariteEntity

PUMP_MODE_OPTIONS: tuple[str, ...] = ("Manual", "Auto", "Heat", "Smart", "Intel")
PUMP_SPEED_OPTIONS: tuple[str, ...] = ("Slow", "Medium", "High")

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up select entities."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]
    pool_id, pool_name = dataservice.pool_id, entry.title

    async_add_entities([
        AquaritePumpModeEntity(dataservice, pool_id, pool_name, "Pump Mode", "filtration.mode"),
        AquaritePumpSpeedEntity(dataservice, pool_id, pool_name, "Pump Speed", "filtration.manVel"),
    ])
    return True

class AquariteSelectEntity(AquariteEntity, SelectEntity):
    """Base for Aquarite select entities."""

    def __init__(self, dataservice, pool_id, pool_name, name, value_path, options) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path, self._options_map = value_path, options
        self._attr_unique_id = self.build_unique_id(name, delimiter="")
        self._attr_options = list(options)

    @property
    def current_option(self) -> str | None:
        raw_value = self._dataservice.get_value(self._value_path)
        try:
            return self._options_map[int(raw_value)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        await self._dataservice.api.set_value(
            self._pool_id, self._value_path, self._options_map.index(option)
        )

class AquaritePumpModeEntity(AquariteSelectEntity):
    def __init__(self, dataservice, pool_id, pool_name, name, value_path):
        super().__init__(dataservice, pool_id, pool_name, name, value_path, PUMP_MODE_OPTIONS)

class AquaritePumpSpeedEntity(AquariteSelectEntity):
    def __init__(self, dataservice, pool_id, pool_name, name, value_path):
        super().__init__(dataservice, pool_id, pool_name, name, value_path, PUMP_SPEED_OPTIONS)