"""Aquarite Light entity."""
from __future__ import annotations

from typing import Any

from aioaquarite import AquariteError

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite light platform."""
    dataservice = entry.runtime_data.coordinator
    pool_id, pool_name = dataservice.pool_id, entry.title

    async_add_entities([
        AquariteLightEntity(dataservice, pool_id, pool_name, "Light", "pool_light", "light.status")
    ])


class AquariteLightEntity(AquariteEntity, LightEntity):
    """Representation of an Aquarite pool light.

    Relies on the coordinator's optimistic-write tracking (see
    AquariteDataUpdateCoordinator.apply_optimistic) for instant UI
    feedback instead of tracking a local target state: is_on reads
    straight from coordinator data, which async_set_values already
    updates before the Firestore push round-trips.
    """

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self.coordinator.get_value(self._value_path))

    async def _send_command(self, state: bool) -> None:
        """Write the new state through the coordinator."""
        try:
            await self.coordinator.async_set_values(
                {self._value_path: 1 if state else 0}
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._send_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._send_command(False)
