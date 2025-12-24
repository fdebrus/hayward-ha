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
    """Set up Aquarite number entities from a config entry."""

    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)
    max_electrolysis = int(dataservice.get_value("hidro.maxAllowedValue")) / 10

    entities = [
        AquariteNumberEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            500,
            800,
            "Redox Setpoint",
            "modules.rx.status.value",
        ),
        AquariteNumberEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            6,
            8,
            "pH Low",
            "modules.ph.status.low_value",
        ),
        AquariteNumberEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            6,
            8,
            "pH Max",
            "modules.ph.status.high_value",
        ),
        AquariteNumberEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            0,
            max_electrolysis,
            "Electrolysis Setpoint",
            "hidro.level",
        ),
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

    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        pool_id,
        pool_name,
        value_min,
        value_max,
        name,
        value_path,
    ) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)
        self._attr_unit_of_measurement = self.UNIT_MAP.get(value_path)
        self._attr_native_step = self._calculate_step(value_path)

    @property
    def native_value(self):
        """Return the current native value."""
        raw_value = self._dataservice.get_value(self._value_path)
        if raw_value is None:
            return None
        scale = self.SCALE_MAP.get(self._value_path)
        return int(raw_value) / scale if scale else raw_value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current native value."""
        scale = self.SCALE_MAP.get(self._value_path)
        raw_value = int(value * scale) if scale else value

        _LOGGER.debug(f"Setting value {raw_value}")
        await self._dataservice.api.set_value(
            self._pool_id,
            self._value_path,
            raw_value,
        )
        self.async_write_ha_state()

    def _calculate_step(self, value_path: str) -> float:
        """Return a step value that matches the configured scale."""
        scale = self.SCALE_MAP.get(value_path)
        return 1 / scale if scale else 1.0
