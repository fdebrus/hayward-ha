"""Coordinator for Aquarite."""
import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class AquariteDataCoordinator(DataUpdateCoordinator):
    """Aquarite custom coordinator."""

    def __init__(self, hass: HomeAssistant, api) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Aquarite",
        )
        self.api = api

    async def async_updated_data(self, data) -> None:
        """Update data."""
        super().async_set_updated_data(data)

    def set_updated_data(self, data) -> None:
        """Receive Data."""
        asyncio.run_coroutine_threadsafe(self.async_updated_data(data), self.hass.loop).result()

    def get_value(self, path) -> Any:
        """Return part from document."""
        return self.data.get(path)

    def get_pool_name(self, pool_id):
        """Get Pool Name."""
        return self.api.get_pool_name(pool_id)

    async def turn_on_switch(self, value_path) -> None:
        """Turn on hidro cover."""
        await self.api.turn_on_switch(self.data.id, value_path)

    async def turn_off_switch(self, value_path) -> None:
        """Turn off hidro cover."""
        await self.api.turn_off_switch(self.data.id, value_path)

    async def set_pump_mode(self, pool_id, pump_mode) -> None:
        """Set pump mode."""
        await self.api.set_pump_mode(self.data.id, pump_mode)
    
    async def set_pump_speed(self, pool_id, pump_speed) -> None:
        """Set pump speed."""
        await self.api.set_pump_speed(self.data.id, pump_speed)

    async def set_path_value(self, pool_id, value_path, value) -> None:
        """Set value for value_path."""
        await self.api.set_path_value(pool_id, value_path, value)

