"""Data coordinator for the Aquarite integration."""
from __future__ import annotations

import logging
from typing import Any

from aioaquarite import (
    AquariteAuth,
    AquariteClient,
    AquariteError,
    ResilientPoolSubscription,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AquariteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aquarite coordinator using the library's resilient Firestore subscription."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        auth: AquariteAuth,
        api: AquariteClient,
        pool_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.auth = auth
        self.api = api
        self.pool_id: str = pool_id
        self.subscription: ResilientPoolSubscription | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquarite",
            update_interval=None,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest pool data (used for the initial/manual refresh)."""
        try:
            return await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library.

        The library owns reconnection/health monitoring through the resilient
        subscription; the (optional) health-check interval is taken from the
        config entry options.
        """

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from the Firestore thread; push data to the HA loop."""
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

        health_check_interval = self.config_entry.options.get(
            CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
        )
        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id,
            _on_data,
            health_check_interval=health_check_interval,
        )

    async def async_shutdown(self) -> None:
        """Cleanly close the resilient subscription."""
        if self.subscription is not None:
            await self.subscription.aclose()
            self.subscription = None
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)

    async def set_pool_time_to_now(self) -> None:
        """Sync the pool controller clock with the current time."""
        now = dt_util.now()
        offset = now.utcoffset()
        utc_offset = int(offset.total_seconds()) if offset else 0
        timestamp = int(now.timestamp()) + utc_offset
        _LOGGER.debug(
            "Syncing pool localTime to %s (%s, UTC offset %+ds)",
            timestamp,
            now.isoformat(),
            utc_offset,
        )
        await self.api.set_value(self.pool_id, "main.localTime", timestamp)
