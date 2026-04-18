"""Aquarite Binary Sensor entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariteConfigEntry
from .const import PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 0

TANK_MODULE_PATHS = (
    "modules.ph.tank",
    "modules.rx.tank",
    "modules.cl.tank",
    "modules.cd.tank",
)


def _bool_path(path: str) -> Callable[[AquariteDataUpdateCoordinator], bool | None]:
    def _fn(coordinator: AquariteDataUpdateCoordinator) -> bool | None:
        if coordinator.get_value(path) is None:
            return None
        return coordinator.get_bool(path)
    return _fn


def _any_tank_low(coordinator: AquariteDataUpdateCoordinator) -> bool:
    return any(coordinator.get_bool(path) for path in TANK_MODULE_PATHS)


def _has_tank_module(coordinator: AquariteDataUpdateCoordinator) -> bool:
    return any(
        coordinator.get_bool(path)
        for path in (PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX)
    )


@dataclass(frozen=True, kw_only=True)
class AquariteBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Aquarite binary sensor."""

    value_fn: Callable[[AquariteDataUpdateCoordinator], bool | None]
    exists_fn: Callable[[AquariteDataUpdateCoordinator], bool] | None = None


BASE_SENSORS: tuple[AquariteBinarySensorEntityDescription, ...] = (
    AquariteBinarySensorEntityDescription(
        key="hidro_flow_status",
        translation_key="hidro_flow_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bool_path("hidro.fl1"),
    ),
    AquariteBinarySensorEntityDescription(
        key="filtration_status",
        translation_key="filtration_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("filtration.status"),
    ),
    AquariteBinarySensorEntityDescription(
        key="backwash_status",
        translation_key="backwash_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("backwash.status"),
    ),
    AquariteBinarySensorEntityDescription(
        key="hidro_cover_reduction",
        translation_key="hidro_cover_reduction",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("hidro.cover"),
    ),
    AquariteBinarySensorEntityDescription(
        key="ph_pump_alarm",
        translation_key="ph_pump_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bool_path("modules.ph.al3"),
    ),
    AquariteBinarySensorEntityDescription(
        key="cd_module_installed",
        translation_key="cd_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_bool_path("main.hasCD"),
    ),
    AquariteBinarySensorEntityDescription(
        key="cl_module_installed",
        translation_key="cl_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_bool_path("main.hasCL"),
    ),
    AquariteBinarySensorEntityDescription(
        key="rx_module_installed",
        translation_key="rx_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_bool_path("main.hasRX"),
    ),
    AquariteBinarySensorEntityDescription(
        key="ph_module_installed",
        translation_key="ph_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_bool_path("main.hasPH"),
    ),
    AquariteBinarySensorEntityDescription(
        key="io_module_installed",
        translation_key="io_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_bool_path("main.hasIO"),
    ),
    AquariteBinarySensorEntityDescription(
        key="hidro_module_installed",
        translation_key="hidro_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_bool_path("main.hasHidro"),
    ),
    AquariteBinarySensorEntityDescription(
        key="ph_acid_pump",
        translation_key="ph_acid_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("modules.ph.pump_high_on"),
    ),
    AquariteBinarySensorEntityDescription(
        key="ph_base_pump",
        translation_key="ph_base_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("modules.ph.pump_low_on"),
    ),
    AquariteBinarySensorEntityDescription(
        key="heating_status",
        translation_key="heating_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("relays.filtration.heating.status"),
    ),
    AquariteBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_bool_path("present"),
    ),
    AquariteBinarySensorEntityDescription(
        key="hidro_fl2_status",
        translation_key="hidro_fl2_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bool_path("hidro.fl2"),
        exists_fn=lambda c: c.get_bool("main.hasCL"),
    ),
    AquariteBinarySensorEntityDescription(
        key="cl_pump_status",
        translation_key="cl_pump_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("modules.cl.pump_status"),
        exists_fn=lambda c: c.get_bool("main.hasCL"),
    ),
    AquariteBinarySensorEntityDescription(
        key="rx_pump_status",
        translation_key="rx_pump_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bool_path("modules.rx.pump_status"),
        exists_fn=lambda c: c.get_bool(PATH_HASRX),
    ),
    AquariteBinarySensorEntityDescription(
        key="acid_tank",
        translation_key="acid_tank",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_any_tank_low,
        exists_fn=_has_tank_module,
    ),
)


def _hidro_low_description(coordinator: AquariteDataUpdateCoordinator) -> AquariteBinarySensorEntityDescription:
    is_electrolysis = coordinator.get_bool("hidro.is_electrolysis")
    key = "electrolysis_low" if is_electrolysis else "hydrolysis_low"
    return AquariteBinarySensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bool_path("hidro.low"),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aquarite binary sensors."""
    entities: list[AquariteBinarySensor] = []

    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(
            AquariteBinarySensor(coordinator, description)
            for description in BASE_SENSORS
            if description.exists_fn is None or description.exists_fn(coordinator)
        )
        entities.append(
            AquariteBinarySensor(coordinator, _hidro_low_description(coordinator))
        )

    async_add_entities(entities)


class AquariteBinarySensor(AquariteEntity, BinarySensorEntity):
    """Aquarite binary sensor entity."""

    entity_description: AquariteBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator)
