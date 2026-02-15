import asyncio
import logging
import contextlib
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import HEALTH_CHECK_INTERVAL, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

class AquariteDataUpdateCoordinator(DataUpdateCoordinator):
    """Aquarite custom coordinator using Firestore Real-time Snapshots."""

    def __init__(self, hass: HomeAssistant, auth: Any, api: Any) -> None:
        """Initialize the coordinator."""
        self.auth = auth
        self.api = api
        self.pool_id: Optional[str] = None
        self.watch = None
        self._health_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None

        super().__init__(hass, logger=_LOGGER, name="Aquarite", update_interval=None)

    def set_pool_id(self, pool_id: str):
        """Set the pool ID for queries."""
        self.pool_id = pool_id

    async def subscribe(self):
        """Initialize Firestore Snapshot listener."""
        client = await self.auth.get_client()
        doc_ref = client.collection("pools").document(self.pool_id)
        
        # Snapshot runs in a background thread; must use thread-safe calls for HA
        self.watch = await asyncio.to_thread(doc_ref.on_snapshot, self._on_snapshot)
        _LOGGER.debug("Firestore subscription active for %s", self.pool_id)

    def _on_snapshot(self, doc_snapshot, changes, read_time):
        """Callback from Firestore thread; push data to HA loop."""
        for doc in doc_snapshot:
            data = doc.to_dict()
            # Schedule the update on the main HA event loop
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

    async def setup_tasks(self):
        """Start background polling and health monitoring."""
        self._health_task = self.hass.async_create_background_task(
            self.periodic_health_check(), "Aquarite health check"
        )
        self._poll_task = self.hass.async_create_background_task(
            self.periodic_polling(), "Aquarite state poll"
        )

    async def periodic_polling(self):
        """Periodic poll to ensure data consistency."""
        while not self.hass.is_stopping:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                data = await self.api.fetch_pool_data(self.pool_id)
                if data != self.data:
                    self.async_set_updated_data(data)
            except Exception as e:
                _LOGGER.error("Polling failed: %s", e)

    async def periodic_health_check(self):
        """Monitor connection and refresh tokens/subscriptions."""
        while not self.hass.is_stopping:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            try:
                await self.auth.get_client() 
            except Exception as e:
                _LOGGER.error("Health check failed, resubscribing: %s", e)
                await self.subscribe()

    async def async_shutdown(self) -> None:
        """Cleanly unsubscribe and cancel tasks."""
        if self.watch:
            await asyncio.to_thread(self.watch.unsubscribe)
        
        for task in (self._health_task, self._poll_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot notation."""
        if not self.data:
            return default
        keys = path.split(".")
        val = self.data
        try:
            for key in keys:
                val = val[key]
            return val if val is not None else default
        except (KeyError, TypeError):
            return default

    async def set_pool_time_to_now(self):
        """Service call to sync the pool's internal clock with the current time."""
        now = datetime.now()
        # Format required by Hayward: Day of week (1-7), HH, MM
        # ISO weekday is 1 (Mon) - 7 (Sun)
        payload = {
            "day": now.isoweekday(),
            "hour": now.hour,
            "min": now.minute
        }
        _LOGGER.info("Syncing pool time to: %s", payload)
        # Re-uses the optimized set_value logic from your API class
        await self.api.set_value(self.pool_id, "main.time", payload)