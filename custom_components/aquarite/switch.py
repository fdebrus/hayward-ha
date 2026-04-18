"""Aquarite Switch entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AquariteSwitchEntityDescription(SwitchEntityDescription):
    """Describes an Aquarite switch."""

    value_path: str
    is_relay: bool = False
    exists_fn: Callable[[AquariteDataUpdateCoordinator], bool] | None = None


SWITCHES: tuple[AquariteSwitchEntityDescription, ...] = (
    AquariteSwitchEntityDescription(
        key="electrolysis_cover",
        translation_key="electrolysis_cover",
        value_path="hidro.cover_enabled",
    ),
    AquariteSwitchEntityDescription(
        key="electrolysis_boost",
        translation_key="electrolysis_boost",
        value_path="hidro.cloration_enabled",
    ),
    AquariteSwitchEntityDescription(
        key="relay_1",
        translation_key="relay_1",
        value_path="relays.relay1.info.onoff",
        is_relay=True,
    ),
    AquariteSwitchEntityDescription(
        key="relay_2",
        translation_key="relay_2",
        value_path="relays.relay2.info.onoff",
        is_relay=True,
    ),
    AquariteSwitchEntityDescription(
        key="relay_3",
        translation_key="relay_3",
        value_path="relays.relay3.info.onoff",
        is_relay=True,
    ),
    AquariteSwitchEntityDescription(
        key="relay_4",
        translation_key="relay_4",
        value_path="relays.relay4.info.onoff",
        is_relay=True,
    ),
    AquariteSwitchEntityDescription(
        key="filtration",
        translation_key="filtration",
        value_path="filtration.status",
    ),
    AquariteSwitchEntityDescription(
        key="heating_climate",
        translation_key="heating_climate",
        value_path="filtration.heating.clima",
        exists_fn=lambda c: c.get_bool("filtration.hasHeat"),
    ),
    AquariteSwitchEntityDescription(
        key="smart_mode_freeze",
        translation_key="smart_mode_freeze",
        value_path="filtration.smart.freeze",
        exists_fn=lambda c: c.get_bool("filtration.hasSmart"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite switch platform."""
    async_add_entities(
        AquariteSwitch(coordinator, description)
        for coordinator in entry.runtime_data.coordinators.values()
        for description in SWITCHES
        if description.exists_fn is None or description.exists_fn(coordinator)
    )


class AquariteSwitch(AquariteEntity, SwitchEntity):
    """Aquarite switch entity."""

    entity_description: AquariteSwitchEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        path = self.entity_description.value_path
        onoff = self.coordinator.get_bool(path)
        if self.entity_description.is_relay:
            return onoff or self.coordinator.get_bool(
                path.replace("onoff", "status")
            )
        return onoff

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set(0)

    async def _async_set(self, value: int) -> None:
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id, self.entity_description.value_path, value
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set switch: {err}") from err
