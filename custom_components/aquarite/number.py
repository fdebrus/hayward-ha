"""Aquarite Number entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aioaquarite import AquariteError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AquariteNumberEntityDescription(NumberEntityDescription):
    """Describes an Aquarite number entity."""

    value_path: str
    scale: int = 1
    max_fn: Callable[[AquariteDataUpdateCoordinator], float] | None = None
    exists_fn: Callable[[AquariteDataUpdateCoordinator], bool] | None = None


def _max_electrolysis(coordinator: AquariteDataUpdateCoordinator) -> float:
    raw = coordinator.get_value("hidro.maxAllowedValue", 0)
    try:
        return int(raw) / 10 if raw else 50.0
    except (TypeError, ValueError):
        return 50.0


NUMBERS: tuple[AquariteNumberEntityDescription, ...] = (
    AquariteNumberEntityDescription(
        key="redox_setpoint",
        translation_key="redox_setpoint",
        native_min_value=500,
        native_max_value=800,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_path="modules.rx.status.value",
    ),
    AquariteNumberEntityDescription(
        key="ph_low",
        translation_key="ph_low",
        native_min_value=6,
        native_max_value=8,
        native_unit_of_measurement="pH",
        value_path="modules.ph.status.low_value",
        scale=100,
    ),
    AquariteNumberEntityDescription(
        key="ph_max",
        translation_key="ph_max",
        native_min_value=6,
        native_max_value=8,
        native_unit_of_measurement="pH",
        value_path="modules.ph.status.high_value",
        scale=100,
    ),
    AquariteNumberEntityDescription(
        key="electrolysis_setpoint",
        translation_key="electrolysis_setpoint",
        native_min_value=0,
        native_max_value=50,  # overridden by max_fn at runtime
        native_unit_of_measurement="g/h",
        value_path="hidro.level",
        scale=10,
        max_fn=_max_electrolysis,
    ),
    AquariteNumberEntityDescription(
        key="intel_mode_temperature",
        translation_key="intel_mode_temperature",
        native_min_value=5,
        native_max_value=40,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_path="filtration.intel.temp",
    ),
    AquariteNumberEntityDescription(
        key="heating_mode_min_temperature",
        translation_key="heating_mode_min_temperature",
        native_min_value=5,
        native_max_value=40,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_path="filtration.heating.temp",
        exists_fn=lambda c: c.get_bool("filtration.hasHeat"),
    ),
    AquariteNumberEntityDescription(
        key="heating_mode_max_temperature",
        translation_key="heating_mode_max_temperature",
        native_min_value=5,
        native_max_value=40,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_path="filtration.heating.tempHi",
        exists_fn=lambda c: c.get_bool("filtration.hasHeat"),
    ),
    AquariteNumberEntityDescription(
        key="smart_mode_min_temperature",
        translation_key="smart_mode_min_temperature",
        native_min_value=5,
        native_max_value=40,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_path="filtration.smart.tempMin",
        exists_fn=lambda c: c.get_bool("filtration.hasSmart"),
    ),
    AquariteNumberEntityDescription(
        key="smart_mode_max_temperature",
        translation_key="smart_mode_max_temperature",
        native_min_value=5,
        native_max_value=40,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_path="filtration.smart.tempHigh",
        exists_fn=lambda c: c.get_bool("filtration.hasSmart"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aquarite number entities."""
    async_add_entities(
        AquariteNumber(coordinator, description)
        for coordinator in entry.runtime_data.coordinators.values()
        for description in NUMBERS
        if description.exists_fn is None or description.exists_fn(coordinator)
    )


class AquariteNumber(AquariteEntity, NumberEntity):
    """Aquarite number entity."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: AquariteNumberEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)
        self._attr_native_step = (
            1 / description.scale if description.scale != 1 else 1.0
        )
        if description.max_fn is not None:
            self._attr_native_max_value = description.max_fn(coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw = self.coordinator.get_value(self.entity_description.value_path)
        if raw is None:
            return None
        scale = self.entity_description.scale
        try:
            return int(raw) / scale if scale != 1 else float(raw)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        scale = self.entity_description.scale
        raw = int(round(value * scale)) if scale != 1 else value
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                raw,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
