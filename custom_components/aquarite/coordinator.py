"""Data coordinator for the Aquarite integration."""
from __future__ import annotations

import asyncio
import logging
from time import monotonic
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

# Fallback for when a Firestore push never arrives to confirm an optimistic
# write (controller offline, command dropped somewhere in the cloud); a
# confirming push normally clears the pending entry well before this fires.
OPTIMISTIC_TTL_SECONDS = 10.0


class AquariteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aquarite coordinator using Firestore real-time snapshots."""

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
        self._pending_optimistic: dict[str, tuple[Any, float]] = {}
        self._optimistic_handles: dict[str, asyncio.TimerHandle] = {}

        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquarite",
            update_interval=None,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest pool data (used by the optimistic-write self-heal)."""
        try:
            data = await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        # A refresh (self-heal or manual) must not clobber optimistic writes
        # for other paths that are still inside their own TTL window.
        return self._merge_optimistic(data)

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library.

        The resilient subscription supervises itself: it refreshes the auth
        token before expiry, resubscribes after a refresh, reconnects with
        exponential backoff on errors, and health-checks the connection on
        the configured interval — replacing the hand-rolled token-refresh
        and health-check background loops this coordinator used to run.
        """

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from Firestore thread; push data to HA loop."""
            self.hass.loop.call_soon_threadsafe(self._apply_remote_data, data)

        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id,
            _on_data,
            health_check_interval=self.config_entry.options.get(
                CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
            ),
        )

    async def async_shutdown(self) -> None:
        """Cleanly close the subscription and cancel optimistic timers."""
        for handle in self._optimistic_handles.values():
            handle.cancel()
        self._optimistic_handles.clear()
        self._pending_optimistic.clear()
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
        command, and mirrors accepted changes into the cached pool
        document (the same dict as self.data) on success only — a failed
        command leaves the cache untouched, because no Firestore snapshot
        will correct a value the cloud never received.

        On success, the written values are additionally marked optimistic
        (see apply_optimistic) so entities update instantly instead of
        waiting for the Firestore round-trip, with a TTL fallback in case
        the confirming push never arrives.
        """
        await self.api.set_values(self.pool_id, updates)
        self.apply_optimistic(updates)

    def apply_optimistic(self, updates: dict[str, Any]) -> None:
        """Reflect just-accepted values and protect them from stale Firestore pushes.

        Hayward's cloud can take several seconds to acknowledge a write back
        through Firestore, which would make the UI feel laggy. Writing the
        value into the cache immediately gives entities instant feedback;
        the next matching Firestore push clears the pending entry, and a
        TTL fallback self-heals if that push never arrives (dropped
        command, offline controller).
        """
        now = monotonic()
        for value_path, value in updates.items():
            self._pending_optimistic[value_path] = (value, now)
            _set_path(self.data, value_path, value)
            if (handle := self._optimistic_handles.pop(value_path, None)) is not None:
                handle.cancel()
            self._optimistic_handles[value_path] = self.hass.loop.call_later(
                OPTIMISTIC_TTL_SECONDS, self._expire_optimistic, value_path
            )
        self.async_set_updated_data(self.data)

    def _merge_optimistic(self, data: dict[str, Any]) -> dict[str, Any]:
        """Overlay unconfirmed optimistic writes onto freshly fetched data."""
        now = monotonic()
        for path, (value, written_at) in list(self._pending_optimistic.items()):
            remote_value = AquariteClient.get_value(data, path)
            if (
                _values_agree(remote_value, value)
                or now - written_at >= OPTIMISTIC_TTL_SECONDS
            ):
                self._clear_optimistic(path)
            else:
                _set_path(data, path, value)
        return data

    def _apply_remote_data(self, data: dict[str, Any]) -> None:
        """Apply a Firestore push, preserving unconfirmed optimistic writes."""
        self.async_set_updated_data(self._merge_optimistic(data))

    def _clear_optimistic(self, value_path: str) -> None:
        """Drop a pending optimistic entry and its scheduled expiry."""
        self._pending_optimistic.pop(value_path, None)
        if (handle := self._optimistic_handles.pop(value_path, None)) is not None:
            handle.cancel()

    def _expire_optimistic(self, value_path: str) -> None:
        """TTL fired without a confirming push: drop it and force a refresh."""
        self._optimistic_handles.pop(value_path, None)
        if value_path not in self._pending_optimistic:
            return
        del self._pending_optimistic[value_path]
        self.hass.async_create_task(self.async_refresh())

    async def set_pool_time_to_now(self) -> None:
        """Sync the pool controller clock with the current time."""
        now = dt_util.now()
        offset = now.utcoffset()
        utc_offset = int(offset.total_seconds()) if offset else 0
        timestamp = int(now.timestamp()) + utc_offset
        _LOGGER.info("Syncing pool localTime to: %s (%s, UTC offset %+ds)", timestamp, now.isoformat(), utc_offset)
        await self.api.set_value(self.pool_id, "main.localTime", timestamp)


def _set_path(data: dict[str, Any], value_path: str, value: Any) -> None:
    """Write value into data at a dot-notation path, creating dicts as needed."""
    keys = value_path.split(".")
    target: dict[str, Any] = data
    for key in keys[:-1]:
        child = target.get(key)
        if not isinstance(child, dict):
            child = {}
            target[key] = child
        target = child
    target[keys[-1]] = value


def _values_agree(remote: Any, optimistic: Any) -> bool:
    """Compare values tolerantly: Firestore can return int/str/bool variants."""
    if remote == optimistic:
        return True
    try:
        return float(remote) == float(optimistic)
    except (TypeError, ValueError):
        return False
