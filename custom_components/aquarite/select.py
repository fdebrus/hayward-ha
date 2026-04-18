"""Aquarite Select entities."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1

PUMP_MODE_OPTIONS: tuple[str, ...] = ("manual", "auto", "heat", "smart", "intel")
SPEED_OPTIONS: tuple[str, ...] = ("slow", "medium", "high")


@dataclass(frozen=True, kw_only=True)
class AquariteSelectEntityDescription(SelectEntityDescription):
    """Describes an Aquarite select entity."""

    value_path: str
    options_map: tuple[str, ...]


SELECTS: tuple[AquariteSelectEntityDescription, ...] = (
    AquariteSelectEntityDescription(
        key="pump_mode",
        translation_key="pump_mode",
        options=list(PUMP_MODE_OPTIONS),
        options_map=PUMP_MODE_OPTIONS,
        value_path="filtration.mode",
    ),
    AquariteSelectEntityDescription(
        key="pump_speed",
        translation_key="pump_speed",
        options=list(SPEED_OPTIONS),
        options_map=SPEED_OPTIONS,
        value_path="filtration.manVel",
    ),
    *(
        AquariteSelectEntityDescription(
            key=f"filtration_timer_speed_{i}",
            translation_key=f"filtration_timer_speed_{i}",
            options=list(SPEED_OPTIONS),
            options_map=SPEED_OPTIONS,
            value_path=f"filtration.timerVel{i}",
        )
        for i in range(1, 4)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    async_add_entities(
        AquariteSelect(coordinator, description)
        for coordinator in entry.runtime_data.coordinators.values()
        for description in SELECTS
    )


class AquariteSelect(AquariteEntity, SelectEntity):
    """Aquarite select entity."""

    entity_description: AquariteSelectEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        raw = self.coordinator.get_value(self.entity_description.value_path)
        try:
            return self.entity_description.options_map[int(raw)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                self.entity_description.options_map.index(option),
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to select option: {err}") from err
