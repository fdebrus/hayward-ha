"""Aquarite Button entities."""
from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import LED_PULSE_DELAY, PATH_HASLED
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite button platform."""
    async_add_entities(
        AquariteLEDPulseButtonEntity(dataservice)
        for dataservice in entry.runtime_data.coordinators.values()
        if dataservice.get_value(PATH_HASLED)
    )


class AquariteLEDPulseButtonEntity(AquariteEntity, ButtonEntity):
    """Button that power-cycles the pool light to advance the LED color.

    Mirrors the "Next" button under LED Color in the Hayward app's
    Illumination screen.  Sends a WRP command with light.status=1,
    which causes the controller to briefly power-cycle the light
    output; the physical LED fixture then advances to the next colour
    in its internal sequence.
    """

    _attr_translation_key = "led_pulse"

    def __init__(self, coordinator: AquariteDataUpdateCoordinator) -> None:
        """Initialize the LED pulse button."""
        super().__init__(coordinator)
        self._attr_unique_id = self.build_unique_id("LEDPulse")

    async def async_press(self) -> None:
        """Send a pulse to the pool LED.

        If the light is already on, turn it off, wait LED_PULSE_DELAY
        seconds, then turn it back on — the physical LED fixture
        advances to the next colour on power-on.  If the light is off,
        simply turn it on.
        """
        try:
            if self.coordinator.get_value("light.status"):
                await self.coordinator.api.set_value(
                    self.coordinator.pool_id, "light.status", 0
                )
                await asyncio.sleep(LED_PULSE_DELAY)
            await self.coordinator.api.set_value(
                self.coordinator.pool_id, "light.status", 1
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to pulse LED: {err}") from err
