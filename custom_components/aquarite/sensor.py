"""Aquarite Sensor entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import (
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _scaled(path: str, divisor: float) -> Callable[[AquariteDataUpdateCoordinator], float | None]:
    def _fn(coordinator: AquariteDataUpdateCoordinator) -> float | None:
        value = coordinator.get_value(path)
        try:
            return float(value) / divisor
        except (TypeError, ValueError):
            return None
    return _fn


def _path(path: str, converter: Callable[[Any], Any] = _coerce_float) -> Callable[[AquariteDataUpdateCoordinator], Any]:
    def _fn(coordinator: AquariteDataUpdateCoordinator) -> Any:
        return converter(coordinator.get_value(path))
    return _fn


def _form_field(field: str) -> Callable[[AquariteDataUpdateCoordinator], str | None]:
    def _fn(coordinator: AquariteDataUpdateCoordinator) -> str | None:
        form = coordinator.get_value("form")
        return form.get(field) if form else None
    return _fn


@dataclass(frozen=True, kw_only=True)
class AquariteSensorEntityDescription(SensorEntityDescription):
    """Describes an Aquarite sensor."""

    value_fn: Callable[[AquariteDataUpdateCoordinator], Any]
    exists_fn: Callable[[AquariteDataUpdateCoordinator], bool] | None = None


SENSORS: tuple[AquariteSensorEntityDescription, ...] = (
    AquariteSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_path("main.temperature"),
    ),
    AquariteSensorEntityDescription(
        key="cd",
        translation_key="cd",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_scaled("modules.cd.current", 100),
        exists_fn=lambda c: bool(c.get_value(PATH_HASCD)),
    ),
    AquariteSensorEntityDescription(
        key="cl",
        translation_key="cl",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_scaled("modules.cl.current", 100),
        exists_fn=lambda c: bool(c.get_value(PATH_HASCL)),
    ),
    AquariteSensorEntityDescription(
        key="ph",
        translation_key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_scaled("modules.ph.current", 100),
        exists_fn=lambda c: bool(c.get_value(PATH_HASPH)),
    ),
    AquariteSensorEntityDescription(
        key="rx",
        translation_key="rx",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_path("modules.rx.current", _coerce_int),
        exists_fn=lambda c: bool(c.get_value(PATH_HASRX)),
    ),
    AquariteSensorEntityDescription(
        key="uv",
        translation_key="uv",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_scaled("modules.uv.current", 100),
        exists_fn=lambda c: bool(c.get_value(PATH_HASUV)),
    ),
    AquariteSensorEntityDescription(
        key="filtration_intel_time",
        translation_key="filtration_intel_time",
        native_unit_of_measurement="h",
        value_fn=_scaled("filtration.intel.time", 60),
    ),
    AquariteSensorEntityDescription(
        key="city",
        translation_key="city",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_form_field("city"),
    ),
    AquariteSensorEntityDescription(
        key="street",
        translation_key="street",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_form_field("street"),
    ),
    AquariteSensorEntityDescription(
        key="zipcode",
        translation_key="zipcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_form_field("zipcode"),
    ),
    AquariteSensorEntityDescription(
        key="country",
        translation_key="country",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_form_field("country"),
    ),
    AquariteSensorEntityDescription(
        key="latitude",
        translation_key="latitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_form_field("lat"),
    ),
    AquariteSensorEntityDescription(
        key="longitude",
        translation_key="longitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_form_field("lng"),
    ),
    AquariteSensorEntityDescription(
        key="pool_name",
        translation_key="pool_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.pool_name,
    ),
    AquariteSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_path("main.RSSI", _coerce_int),
    ),
)


def _hidro_description(coordinator: AquariteDataUpdateCoordinator) -> AquariteSensorEntityDescription:
    """Return either electrolysis or hydrolysis description for the hidro module."""
    is_electrolysis = bool(coordinator.get_value("hidro.is_electrolysis"))
    key = "electrolysis" if is_electrolysis else "hydrolysis"
    return AquariteSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement="gr/h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_scaled("hidro.current", 10),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite sensors."""
    entities: list[AquariteSensor] = []

    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(
            AquariteSensor(coordinator, description)
            for description in SENSORS
            if description.exists_fn is None or description.exists_fn(coordinator)
        )

        if bool(coordinator.get_value(PATH_HASHIDRO)):
            entities.append(
                AquariteSensor(coordinator, _hidro_description(coordinator))
            )

    async_add_entities(entities)


class AquariteSensor(AquariteEntity, SensorEntity):
    """Aquarite sensor entity."""

    entity_description: AquariteSensorEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
