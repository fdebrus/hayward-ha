import asyncio
import logging
import json
from datetime import datetime
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from google.cloud import firestore_v1
from google.api_core.exceptions import GoogleAPICallError

from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .const import DOMAIN, HEALTH_CHECK_INTERVAL, POLL_INTERVAL

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
        self.pool_id = None
        self.watch = None
        self.data = None
        super().__init__(hass, logger=_LOGGER, name="Aquarite", update_interval=None)

    async def async_added_to_hass(self):
        """Register update intervals when added to Home Assistant."""
        self.periodic_health_task = asyncio.create_task(self.periodic_health_check())
        self.periodic_polling_task = asyncio.create_task(self.periodic_polling())
        self.token_refresh_task = asyncio.create_task(self.auth.start_token_refresh_routine(self))

    async def async_will_remove_from_hass(self):
        """Cancel tasks when entity is removed."""
        self.periodic_health_task.cancel()
        self.periodic_polling_task.cancel()
        self.token_refresh_task.cancel()
        await self.unsubscribe()

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
        if isinstance(data, str):
            data = json.loads(data)
        _LOGGER.debug(f"{data}")
        asyncio.run_coroutine_threadsafe(self.async_updated_data(data), self.hass.loop).result()

    async def periodic_polling(self):
        """Periodically poll the Firestore document for state reconciliation."""
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            await self.poll_state()

    async def poll_state(self):
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
            doc = await asyncio.to_thread(doc_ref.get)
            latest_data = doc.to_dict()
            if latest_data != self.data:
                _LOGGER.warning("Periodic poll: state out of sync, updating coordinator.")
                await self.async_set_updated_data(latest_data)
        except Exception as e:
            _LOGGER.error(f"Polling error: {e}")

    async def subscribe(self):
        """Subscribe to the pool's updates."""
        _LOGGER.debug(f"Subscribing to updates for pool ID: {self.pool_id}")
        await self.setup_subscription()

    async def setup_subscription(self):
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
            if self.watch is not None:
                self.watch.unsubscribe()  # explicitly unsubscribe previous watcher if existing
            self.watch = doc_ref.on_snapshot(self.on_snapshot)
            _LOGGER.debug(f"Subscribed with new listener for pool_id {self.pool_id}")
        except Exception as e:
            _LOGGER.error(f"Error setting up subscription: {e}")
            await self.refresh_subscription()

    async def refresh_subscription(self):
        """Refresh the subscription to handle invalid client or network issues."""
        _LOGGER.debug(f"Refreshing subscription for pool ID: {self.pool_id}")
        await self.unsubscribe()
        await self.setup_subscription()

    def on_snapshot(self, doc_snapshot, changes, read_time):
        """Handles document snapshots."""
        try:
            _LOGGER.debug(f"Snapshot received at {read_time}. Changes detected: {[change.type.name for change in changes]}")
            for change in changes:
                _LOGGER.debug(f"Received change {change.type} in Firestore")
            for doc in doc_snapshot:
                try:
                    self.set_updated_data(doc.to_dict())
                except Exception as handler_error:
                    _LOGGER.error(f"Error executing handler: {handler_error}")
        except Exception as e:
            _LOGGER.error(f"Error in on_snapshot: {e}")
            asyncio.create_task(self.refresh_subscription())

    async def unsubscribe(self):
        """Unsubscribe from the current watch."""
        if self.watch is not None:
            self.watch.unsubscribe()
            self.watch = None
            _LOGGER.debug(f"Unsubscribed from pool ID: {self.pool_id}")

    async def _async_update_data(self) -> Any:
        """Fetch data from Firestore or your backend."""
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
            doc = await asyncio.to_thread(doc_ref.get)
            data = doc.to_dict()
            if not data:
                raise ValueError("No data returned from Firestore for pool_id %s", self.pool_id)
            _LOGGER.debug("Fetched data for pool_id %s: %s", self.pool_id, data)
            return data
        except Exception as err:
            _LOGGER.error("Error updating data: %s", err, exc_info=True)
            # Optionally: raise UpdateFailed(f"Error fetching data: {err}") for HA retry/backoff logic
            return None

    async def periodic_health_check(self):
        """Periodic task to check the Firestore client connection status."""
        while True:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            await self.check_connection_status()

    async def check_connection_status(self):
        """Check the Firestore client's connection status and refresh if necessary."""
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
            doc = await asyncio.to_thread(doc_ref.get)
            _LOGGER.debug(f"Connection status check successful for pool ID: {self.pool_id}")
        except GoogleAPICallError as e:
            _LOGGER.debug(f"Connection status check failed: {e}, refreshing subscription.")
            await self.refresh_subscription()
        except Exception as e:
            _LOGGER.debug(f"Unexpected error during connection status check: {e}")
            await self.refresh_subscription()

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
