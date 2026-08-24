"""Data coordinator for the Aquarite integration."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from time import monotonic
from typing import Any

from aioaquarite import AquariteAuth, AquariteClient, AquariteError

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
        self.watch: Any | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._token_task: asyncio.Task[None] | None = None
        self._subscription_lock = asyncio.Lock()
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
        """Subscribe to Firestore real-time updates via the library."""

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from Firestore thread; push data to HA loop."""
            self.hass.loop.call_soon_threadsafe(self._apply_remote_data, data)

        self.watch = await self.api.subscribe_pool(self.pool_id, _on_data)

    async def setup_tasks(self) -> None:
        """Start background health monitoring and token refresh."""
        self._health_task = self.hass.async_create_background_task(
            self.periodic_health_check(), "Aquarite health check"
        )
        self._token_task = self.hass.async_create_background_task(
            self._token_refresh_loop(), "Aquarite token refresh"
        )

    async def _token_refresh_loop(self) -> None:
        """Maintain token validity with exponential backoff on error."""
        retry_delay = 10
        while not self.hass.is_stopping:
            try:
                if self.auth.is_token_expiring():
                    _LOGGER.debug("Token expiring soon, refreshing...")
                    _, refreshed = await self.auth.get_client()
                    if refreshed:
                        await self.refresh_subscription()
                retry_delay = 10
                sleep_time = self.auth.calculate_sleep_duration()
                await asyncio.sleep(sleep_time)
            except Exception as err:
                _LOGGER.error(
                    "Error maintaining token: %s. Retrying in %ss", err, retry_delay
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 600)

    async def periodic_health_check(self) -> None:
        """Monitor connection and resubscribe if needed."""
        while not self.hass.is_stopping:
            interval = self.config_entry.options.get(
                CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
            )
            await asyncio.sleep(interval)
            try:
                await self.auth.get_client()
            except Exception as err:
                _LOGGER.error("Health check failed, resubscribing: %s", err)
                await self.refresh_subscription()

    async def refresh_subscription(self) -> None:
        """Resubscribe to Firestore after a token refresh."""
        async with self._subscription_lock:
            _LOGGER.debug("Refreshing Firestore subscription for %s", self.pool_id)
            if self.watch:
                await asyncio.to_thread(self.watch.unsubscribe)
            await self.subscribe()

    async def async_shutdown(self) -> None:
        """Cleanly unsubscribe and cancel tasks."""
        for handle in self._optimistic_handles.values():
            handle.cancel()
        self._optimistic_handles.clear()
        self._pending_optimistic.clear()
        if self.watch:
            await asyncio.to_thread(self.watch.unsubscribe)
        for task in (self._health_task, self._token_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
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
