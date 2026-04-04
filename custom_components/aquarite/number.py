"""Aquarite Number entities."""
from __future__ import annotations

from typing import Final

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite number entities."""
    dataservice = entry.runtime_data.coordinator
    pool_id, pool_name = dataservice.pool_id, entry.title

    # Safely determine max electrolysis
    raw_max = dataservice.get_value("hidro.maxAllowedValue", 0)
    max_electrolysis = int(raw_max) / 10 if raw_max else 50.0

    entities = [
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            500, 800, "redox_setpoint", "modules.rx.status.value",
        ),
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            6, 8, "ph_low", "modules.ph.status.low_value",
        ),
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            6, 8, "ph_max", "modules.ph.status.high_value",
        ),
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            0, max_electrolysis, "electrolysis_setpoint", "hidro.level",
        ),
    ]

    async_add_entities(entities)


class AquariteNumberEntity(AquariteEntity, NumberEntity):
    """Number entity for Aquarite data points."""

    _attr_entity_category = EntityCategory.CONFIG

    SCALE_MAP: Final[dict[str, int]] = {
        "modules.ph.status.low_value": 100,
        "modules.ph.status.high_value": 100,
        "hidro.level": 10,
    }
    UNIT_MAP: Final[dict[str, str]] = {
        "modules.rx.status.value": "mV",
        "modules.ph.status.low_value": "pH",
        "modules.ph.status.high_value": "pH",
        "hidro.level": "gr/h",
    }

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        value_min: float,
        value_max: float,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)
        self._attr_native_unit_of_measurement = self.UNIT_MAP.get(value_path)
        self._attr_native_step = self._get_scaled_step()

    def _get_scaled_step(self) -> float:
        """Return step size based on scale factor."""
        scale = self.SCALE_MAP.get(self._value_path)
        return 1 / scale if scale else 1.0

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw_value = self.coordinator.get_value(self._value_path)
        if raw_value is None:
            return None
        scale = self.SCALE_MAP.get(self._value_path)
        return int(raw_value) / scale if scale else float(raw_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        scale = self.SCALE_MAP.get(self._value_path)
        raw_value = int(value * scale) if scale else value
        await self.coordinator.api.set_value(
            self._pool_id, self._value_path, raw_value
        )
