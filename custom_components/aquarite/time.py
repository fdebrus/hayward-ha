"""Aquarite Time entities for filtration interval control."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from aioaquarite import AquariteError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AquariteTimeEntityDescription(TimeEntityDescription):
    """Describes an Aquarite time entity."""

    value_path: str


TIMES: tuple[AquariteTimeEntityDescription, ...] = tuple(
    AquariteTimeEntityDescription(
        key=f"filtration_interval_{i}_{which}",
        translation_key=f"filtration_interval_{i}_{which}",
        value_path=f"filtration.interval{i}.{which}",
    )
    for i in range(1, 4)
    for which in ("from", "to")
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aquarite time entities."""
    async_add_entities(
        AquariteTime(coordinator, description)
        for coordinator in entry.runtime_data.coordinators.values()
        for description in TIMES
    )


class AquariteTime(AquariteEntity, TimeEntity):
    """Aquarite time entity for filtration interval from/to values."""

    entity_description: AquariteTimeEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteTimeEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def native_value(self) -> datetime.time | None:
        """Return the interval time as a time object."""
        raw = self.coordinator.get_value(self.entity_description.value_path)
        try:
            seconds = int(raw)
            hours = (seconds // 3600) % 24
            minutes = (seconds % 3600) // 60
            return datetime.time(hours, minutes)
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: datetime.time) -> None:
        """Set the interval time."""
        seconds = value.hour * 3600 + value.minute * 60
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                seconds,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
