import asyncio
import logging
import json
from datetime import datetime
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from google.cloud import firestore_v1

from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# suppress warning message from google.api_core.bidi
logger = logging.getLogger('google.api_core.bidi')
logger.setLevel(logging.ERROR)

class AquariteDataUpdateCoordinator(DataUpdateCoordinator):
    """Aquarite custom coordinator."""

    def __init__(self, hass: HomeAssistant, auth: IdentityToolkitAuth, api: Aquarite) -> None:
        """Initialize the coordinator."""
        self.auth = auth
        self.api = api
        self.pool_id: Optional[str] = None
        self.watch = None
        super().__init__(hass, logger=_LOGGER, name="Aquarite", update_interval=None)

    def set_pool_id(self, pool_id: str):
        """Set the pool ID."""
        _LOGGER.debug(f"Setting pool ID: {pool_id}")
        self.pool_id = pool_id

    async def async_set_updated_data(self, data) -> None:
        """Update data and notify listeners."""
        self.data = data
        self.async_update_listeners()

    async def async_updated_data(self, data) -> None:
        """Update data."""
        await self.auth.get_client()
        super().async_set_updated_data(data)

    def set_updated_data(self, data) -> None:
        """Receive Data."""
        # Ensure data is a dictionary
        if isinstance(data, str):
            data = json.loads(data)
        asyncio.run_coroutine_threadsafe(self.async_updated_data(data), self.hass.loop).result()

    async def subscribe(self):
        """Subscribe to the pool's updates."""
        _LOGGER.debug(f"Subscribing to updates for pool ID: {self.pool_id}")

        async def on_snapshot(doc_snapshot, changes, read_time):
            """Handles document snapshots."""
            try:
                _LOGGER.debug(f"Snapshot received. Changes: {changes}, Read Time: {read_time}")
                for change in changes:
                    _LOGGER.debug(f"Received change {change.type} in Firestore")
                for doc in doc_snapshot:
                    try:
                        self.set_updated_data(doc.to_dict())
                    except Exception as handler_error:
                        _LOGGER.error(f"Error executing handler: {handler_error}")
            except Exception as e:
                _LOGGER.error(f"Error in on_snapshot: {e}")

        client = await self.auth.get_client()
        doc_ref = client.collection("pools").document(self.pool_id)
        self.watch = doc_ref.on_snapshot(on_snapshot)

        _LOGGER.debug(f"Subscribed with new listener for pool_id {self.pool_id}")


    async def refresh_listener(self):
        """Refresh the Firestore listener if token was refreshed."""
        if self.watch:
            _LOGGER.debug(f"Unsubscribing old listener: {self.watch}")
            try:
                self.watch.unsubscribe()
                _LOGGER.debug("Unsubscribed successfully")
            except Exception as e:
                _LOGGER.error(f"Error while unsubscribing: {e}")
        _LOGGER.debug("Re-subscribing with new token")
        await self.subscribe()

    async def _async_update_data(self) -> Any:
        """No-op update method."""
        _LOGGER.debug("No-op update method called.")
        return

    def get_value(self, path: str) -> Any:
        """Return part from document."""
        keys = path.split('.')
        value = self.data
        try:
            for key in keys:
                value = value[key]
        except (TypeError, KeyError):
            value = None
        return value
    
    def get_pool_name(self, pool_id: str) -> str:
        """Return the name of the pool from document."""
        data_dict = self.data
        if data_dict and data_dict.get("id") == pool_id:
            try:
                pool_name = data_dict["form"]["names"][0]["name"]
            except (KeyError, IndexError):
                pool_name = data_dict.get("form", {}).get("name", "Unknown")
        else:
            _LOGGER.error(f"Pool ID {pool_id} does not match the document's ID.")
            pool_name = "Unknown"
        return pool_name
