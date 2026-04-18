"""Data coordinator for the Aquarite integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioaquarite import AquariteAuth, AquariteClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class AquariteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aquarite coordinator for a single pool using Firestore real-time snapshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        auth: AquariteAuth,
        api: AquariteClient,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the coordinator."""
        self.auth = auth
        self.api = api
        self.pool_id: str = pool_id
        self.pool_name: str = pool_name
        self.watch: Any | None = None
        self._subscription_lock = asyncio.Lock()

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Aquarite {pool_name}",
            update_interval=None,
            config_entry=entry,
        )

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates."""

        def _on_data(data: dict[str, Any]) -> None:
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

        self.watch = await self.api.subscribe_pool(self.pool_id, _on_data)

    async def refresh_subscription(self) -> None:
        """Tear down and re-establish the Firestore subscription."""
        async with self._subscription_lock:
            _LOGGER.debug("Refreshing Firestore subscription for %s", self.pool_id)
            watch = self.watch
            self.watch = None
            if watch is not None:
                await asyncio.to_thread(watch.unsubscribe)
            await self.subscribe()

    async def async_shutdown(self) -> None:
        """Cleanly unsubscribe."""
        async with self._subscription_lock:
            watch = self.watch
            self.watch = None
            if watch is not None:
                await asyncio.to_thread(watch.unsubscribe)
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)

    def get_bool(self, path: str) -> bool:
        """Read a boolean field, coercing string "0" / "1" correctly."""
        try:
            return bool(int(self.get_value(path) or 0))
        except (TypeError, ValueError):
            return False

    async def set_pool_time_to_now(self) -> None:
        """Sync the pool controller clock with the current time."""
        now = dt_util.now()
        offset = now.utcoffset()
        utc_offset = int(offset.total_seconds()) if offset else 0
        timestamp = int(now.timestamp()) + utc_offset
        _LOGGER.info(
            "Syncing pool localTime to %s (%s, UTC offset %+ds)",
            timestamp,
            now.isoformat(),
            utc_offset,
        )
        await self.api.set_value(self.pool_id, "main.localTime", timestamp)
