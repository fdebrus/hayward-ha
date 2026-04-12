"""Aquarite Button entities."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import PATH_HASLED
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite button platform."""
    dataservice = entry.runtime_data.coordinator
    pool_id, pool_name = dataservice.pool_id, entry.title

    entities: list[AquariteEntity] = []

    if dataservice.get_value(PATH_HASLED):
        entities.append(
            AquariteLEDPulseButtonEntity(dataservice, pool_id, pool_name)
        )

    async_add_entities(entities)


class AquariteLEDPulseButtonEntity(AquariteEntity, ButtonEntity):
    """Button that power-cycles the pool light to advance the LED color.

    Mirrors the "Next" button under LED Color in the Hayward app's
    Illumination screen.  Sends a WRP command with light.status=1,
    which causes the controller to briefly power-cycle the light
    output; the physical LED fixture then advances to the next colour
    in its internal sequence.
    """

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the LED pulse button."""
        super().__init__(coordinator, pool_id, pool_name)
        self._attr_translation_key = "led_pulse"
        self._attr_unique_id = self.build_unique_id("LEDPulse", delimiter="")

    async def async_press(self) -> None:
        """Send a pulse to the pool LED."""
        await self.coordinator.api.set_value(self._pool_id, "light.status", 1)
