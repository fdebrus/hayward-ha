import asyncio
import contextlib
import logging
import json
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from google.api_core.exceptions import GoogleAPICallError

from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .const import HEALTH_CHECK_INTERVAL, POLL_INTERVAL

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
        self.data = None
        self._health_task: asyncio.Task | None = None
        self._poll_task: asyncio.Task | None = None

        super().__init__(hass, logger=_LOGGER, name="Aquarite", update_interval=None)
        self._health_task = hass.async_create_task(self.periodic_health_check())
        self._poll_task = hass.async_create_task(self.periodic_polling())

    def set_pool_id(self, pool_id: str):
        """Set the pool ID."""
        _LOGGER.debug(f"Setting pool ID: {pool_id}")
        self.pool_id = pool_id

    async def async_set_updated_data(self, data: Any) -> None:
        """Update data and notify listeners via the coordinator."""
        await self.auth.get_client()
        super().async_set_updated_data(data)

    def set_updated_data(self, data) -> None:
        """Receive Data."""
        if isinstance(data, str):
            data = json.loads(data)
        _LOGGER.debug(f"{data}")
        future = asyncio.run_coroutine_threadsafe(
            self.async_set_updated_data(data), self.hass.loop
        )

        def _log_future_exception(fut: asyncio.Future):
            if (exc := fut.exception()) is not None:
                _LOGGER.error("Error executing handler", exc_info=exc)

        future.add_done_callback(_log_future_exception)

    async def periodic_polling(self):
        """Periodically poll the Firestore document for state reconciliation."""
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            if not self.pool_id:
                _LOGGER.debug("Skipping poll; pool_id not yet set.")
                continue
            await self.poll_state()

    async def poll_state(self):
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
            doc = await asyncio.to_thread(doc_ref.get)
            latest_data = doc.to_dict()
            if latest_data != self.data:
                _LOGGER.warning(
                    "Periodic poll: state out of sync, updating coordinator."
                )
                await self.async_set_updated_data(latest_data)
        except Exception as e:
            _LOGGER.error("Polling error", exc_info=e)

    async def subscribe(self):
        """Subscribe to the pool's updates."""
        _LOGGER.debug(f"Subscribing to updates for pool ID: {self.pool_id}")
        await self.setup_subscription()

    async def setup_subscription(self):
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
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
            asyncio.create_task(self.refresh_subscription())

    async def unsubscribe(self):
        """Unsubscribe from the current watch."""
        if self.watch is not None:
            self.watch.unsubscribe()
            self.watch = None
            _LOGGER.debug(f"Unsubscribed from pool ID: {self.pool_id}")

    async def async_shutdown(self) -> None:
        """Cancel background tasks and unsubscribe from updates."""

        await self.unsubscribe()

        for task in (self._health_task, self._poll_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _async_update_data(self) -> Any:
        """No-op update method."""
        _LOGGER.debug("No-op update method called.")
        return

    async def set_pool_time_to_now(self):
        """Set the pool device time to Home Assistant's current LOCAL time as seconds since 1970-01-01 00:00:00 LOCAL."""
        if not self.pool_id:
            _LOGGER.error("No pool_id set in coordinator!")
            return

        ha_tz_name = self.hass.config.time_zone
        if not ha_tz_name:
            _LOGGER.error("HA timezone not set, defaulting to UTC")
            ha_tz = timezone.utc
        else:
            ha_tz = ZoneInfo(ha_tz_name)

        now_local = datetime.now(ha_tz)
        now_naive = now_local.replace(tzinfo=None)
        local_epoch = datetime(1970, 1, 1)
        unix_timestamp_local = int((now_naive - local_epoch).total_seconds())

        _LOGGER.info(f"Setting Aquarite pool time to {unix_timestamp_local} (Local: {now_local}) for pool_id {self.pool_id}")

        try:
            await self.api.set_value(self.pool_id, "main.localTime", unix_timestamp_local)
        except Exception as e:
            _LOGGER.error(f"Failed to set pool time: {e}")

    async def periodic_health_check(self):
        """Periodic task to check the Firestore client connection status."""
        while True:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            if not self.pool_id:
                _LOGGER.debug("Skipping health check; pool_id not yet set.")
                continue
            await self.check_connection_status()

    async def check_connection_status(self):
        """Check the Firestore client's connection status and refresh if necessary."""
        try:
            client = await self.auth.get_client()
            doc_ref = client.collection("pools").document(self.pool_id)
            await asyncio.to_thread(doc_ref.get)
            _LOGGER.debug(
                "Connection status check successful for pool ID: %s", self.pool_id
            )
        except GoogleAPICallError as e:
            _LOGGER.debug(
                "Connection status check failed: %s, refreshing subscription.", e
            )
            await self.refresh_subscription()
        except Exception as e:
            _LOGGER.debug(
                "Unexpected error during connection status check: %s", e
            )
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
    
    def get_pool_name(self, pool_id: str) -> str:
        """Return the name of the pool from document."""
        data_dict = self.data
        _LOGGER.debug(f"-- DATA -- {self.data} / POOLID {pool_id}")
        if data_dict and data_dict.get("id") == pool_id:
            try:
                pool_name = data_dict["form"]["names"][0]["name"]
            except (KeyError, IndexError):
                pool_name = data_dict.get("form", {}).get("name", "Unknown")
        else:
            _LOGGER.error(f"Pool ID {pool_id} does not match the document's ID.")
            pool_name = "Unknown"
        return pool_name
