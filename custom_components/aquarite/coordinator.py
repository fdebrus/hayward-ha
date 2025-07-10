import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

class AquariteDataUpdateCoordinator(DataUpdateCoordinator):
    """Aquarite Data Coordinator."""

    def __init__(self, hass: HomeAssistant, api, pool_id: str) -> None:
        """Initialize the coordinator with pool_id."""
        self.api = api
        self.pool_id: Optional[str] = pool_id
        self.firestore_watch = None
        self._pending_data = None
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquarite",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )

    async def _async_update_data(self) -> Any:
        """Fetch data from the API (called ONLY by main event loop)."""
        if not self.pool_id:
            _LOGGER.error("No pool_id set in coordinator!")
            return None
        try:
            pool_data = await self.api.get_pool_data(self.pool_id)
            return pool_data
        except Exception as err:
            _LOGGER.error(f"Error updating data for pool_id {self.pool_id}: {err}")
            return getattr(self, "data", None)

    def handle_firestore_update(self, data):
        """
        This is ALWAYS called from the Firestore callback thread.
        It MUST NOT call any async methods or use `await`.
        It MUST only schedule async work to the main event loop.
        """
        _LOGGER.debug("handle_firestore_update: Got Firestore update for pool %s", self.pool_id)
        self._pending_data = data
        # Use call_soon_threadsafe to ensure this happens in the HA event loop!
        self.hass.loop.call_soon_threadsafe(
            lambda: self.safe_create_task(self.async_handle_update())
        )

    def safe_create_task(self, coro):
        """Safely create an async task in the main event loop."""
        import asyncio
        try:
            asyncio.create_task(coro)
        except Exception as e:
            _LOGGER.error(f"Failed to create async task: {e}")

    async def async_handle_update(self):
        """
        This runs on the Home Assistant event loop (safe for async).
        It copies _pending_data into self.data, and triggers entity updates.
        """
        if self._pending_data is not None:
            _LOGGER.debug("async_handle_update: Applying pending Firestore data for pool %s", self.pool_id)
            self.data = self._pending_data
            self._pending_data = None
        else:
            _LOGGER.debug("async_handle_update: No pending Firestore data for pool %s", self.pool_id)
        await self.async_request_refresh()

    def get_value(self, path: str) -> Any:
        """Return value from nested dict by dot path."""
        value = getattr(self, "data", None)
        if value is None:
            return None
        for key in path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list):
                try:
                    key = int(key)
                    value = value[key]
                except Exception:
                    return None
            else:
                return None
        return value

    def get_pool_name(self):
        """Return the pool name for this config entry's pool."""
        data = getattr(self, "data", None)
        if not data:
            _LOGGER.debug("get_pool_name: No data available in coordinator")
            return "Unknown"
        try:
            form = data.get("form", {})
            names = form.get("names", [])
            _LOGGER.debug(f"get_pool_name: form={form}, names={names}")
            if isinstance(names, list) and names:
                name = names[0].get("name")
                _LOGGER.debug(f"get_pool_name: Found names[0].name = {name}")
                if name:
                    return name
            name = form.get("name")
            _LOGGER.debug(f"get_pool_name: Fallback form.name = {name}")
            if name:
                return name
        except Exception as e:
            _LOGGER.error(f"Error extracting pool name: {e}")
        _LOGGER.debug("get_pool_name: Pool name not found, returning 'Unknown'")
        return "Unknown"

    async def set_pool_time_to_now(self):
        """Set the pool device time to Home Assistant's current local time."""
        import time
        if not self.pool_id:
            _LOGGER.error("No pool_id set in coordinator!")
            return
        unix_timestamp_local = int(time.time())
        _LOGGER.info(
            f"Setting Aquarite pool time to {unix_timestamp_local} for pool_id {self.pool_id}"
        )
        try:
            await self.api.set_value(
                self.pool_id, "main.localTime", unix_timestamp_local
            )
        except Exception as e:
            _LOGGER.error(f"Failed to set pool time: {e}")

    async def async_close(self):
        """Call this on unload to clean up Firestore listener."""
        if self.firestore_watch:
            _LOGGER.info("Unsubscribing Firestore watch for pool %s", self.pool_id)
            self.firestore_watch.unsubscribe()
            self.firestore_watch = None
