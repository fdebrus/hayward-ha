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
            logger=_LOGGER,
            name="Aquarite"
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

    def set_value(self, value_path: str, value: any) -> None:
        """Update data by a dynamic path."""
        nested_dict = self.data.to_dict()
        keys = value_path.split('.')
        current_dict = nested_dict
        for key in keys[:-1]:
            current_dict = current_dict.setdefault(key, {})
        current_dict[keys[-1]] = value
        self.data = nested_dict
        _LOGGER.debug(f"{self.data}")

    def get_pool_name(self, pool_id):
        """Return the name of the pool from document."""
        data_dict = self.data.to_dict()
        if data_dict.get("id") == pool_id:
            try:
                pool_name = data_dict["form"]["names"][0]["name"]
            except (KeyError, IndexError):
                pool_name = data_dict.get("form", {}).get("name", "Unknown")
        else:
            _LOGGER.error(f"Pool ID {pool_id} does not match the document's ID.")
            pool_name = "Unknown"
        return pool_name

    def handle_update(self, doc_snapshot, changes, read_time):
        try:
            for change in changes:
                if change.type == 'modified':
                    _LOGGER.debug("Data modified")
                    self.set_updated_data(change.document)
        except Exception as e:
            _LOGGER.error(f"Error handling data update: {e}")
