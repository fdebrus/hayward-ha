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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AquariteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aquarite coordinator using Firestore real-time snapshots.

    Since aioaquarite 0.13.0 the library reconciles writes and snapshots
    itself: acknowledged writes are tracked as pending, delivered data
    carries the newest pending value (so a stale pre-write snapshot can
    no longer flicker entity state), writes are delivered to the data
    callback the moment the cloud acks them, and an unconfirmed write is
    healed by an authoritative fetch after its TTL. This coordinator is
    therefore a plain push-to-``async_set_updated_data`` bridge plus the
    Home Assistant availability policy.

    Delivered dicts belong to the library and may be mutated in place
    before the next delivery — they are read, never modified, here.
    """

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
        self.subscription: ResilientPoolSubscription | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Aquarite {pool_name}",
            update_interval=None,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest pool data (manual refresh and health recovery).

        The library overlays the result with still-pending acknowledged
        writes and yields to any snapshot that landed while the fetch
        was in flight, so the returned data is safe to publish as-is.
        """
        try:
            return await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library.

        The resilient subscription supervises itself: it refreshes the auth
        token before expiry, resubscribes after a refresh, reconnects with
        exponential backoff on errors, and health-checks the connection on
        the configured interval. Snapshots, immediate write echoes, and
        the library's reconcile fetches all arrive through the same data
        callback, already reconciled — and on the event loop.
        """
        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id,
            self._async_handle_push,
            health_check_interval=self.config_entry.options.get(
                CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
            ),
            on_health=self._on_health,
        )

    @callback
    def _async_handle_push(self, data: dict[str, Any]) -> None:
        """Publish library-reconciled pool data to the entities."""
        self.async_set_updated_data(data)

    def _on_health(self, healthy: bool) -> None:
        """Reflect subscription connection health in entity availability.

        Invoked by the library from the supervisor's event loop (HA's
        loop), on transitions only. While the Firestore connection is
        down, entities show as unavailable rather than serving stale
        state; on recovery an authoritative refresh re-fetches truth
        (the resubscribed watch also pushes a fresh snapshot).
        """
        if healthy:
            self.hass.async_create_task(self.async_refresh())
            return
        self.async_set_update_error(
            UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )
        )

    async def async_shutdown(self) -> None:
        """Cleanly close the subscription.

        Closing the resilient subscription also releases the library's
        pending-write state for this pool (expiry timers, reconcile
        task), so nothing fires after the entry is unloaded.
        """
        if self.subscription is not None:
            await self.subscription.aclose()
            self.subscription = None
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)

    async def async_set_values(self, updates: dict[str, Any]) -> None:
        """Write several values of one command branch as a single cloud command.

        Thin pass-through to AquariteClient.set_values, which validates
        that every path resolves to the same command branch, sends the
        command, and — since 0.13.0 — records the written values as
        pending and immediately delivers the updated pool data to the
        subscription callback. Entities therefore update the instant the
        cloud acks the command, stale Firestore snapshots inside the
        echo window are suppressed, and an unconfirmed write is healed
        by an authoritative fetch after its TTL — all in the library.
        """
        await self.api.set_values(self.pool_id, updates)

    async def set_pool_time_to_now(self) -> None:
        """Sync the pool controller clock with the current time."""
        now = dt_util.now()
        offset = now.utcoffset()
        utc_offset = int(offset.total_seconds()) if offset else 0
        timestamp = int(now.timestamp()) + utc_offset
        _LOGGER.info("Syncing pool localTime to: %s (%s, UTC offset %+ds)", timestamp, now.isoformat(), utc_offset)
        await self.api.set_value(self.pool_id, "main.localTime", timestamp)
