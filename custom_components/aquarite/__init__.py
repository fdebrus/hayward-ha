"""The Aquarite integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import logging

from aioaquarite import (
    AquariteAuth,
    AquariteClient,
    AquariteError,
    AuthenticationError,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, HEALTH_CHECK_INTERVAL
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


@dataclass
class AquariteData:
    """Runtime data for the Aquarite integration."""

    auth: AquariteAuth
    api: AquariteClient
    coordinators: dict[str, AquariteDataUpdateCoordinator] = field(default_factory=dict)
    health_task: asyncio.Task[None] | None = None
    token_task: asyncio.Task[None] | None = None


type AquariteConfigEntry = ConfigEntry[AquariteData]


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up Aquarite from a config entry."""
    session = async_get_clientsession(hass)
    auth = AquariteAuth(session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    try:
        await auth.authenticate()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except AquariteError as err:
        raise ConfigEntryNotReady from err

    api = AquariteClient(auth)

    try:
        pools = await api.get_pools()
    except AquariteError as err:
        raise ConfigEntryNotReady from err

    if not pools:
        raise ConfigEntryNotReady("No pools found for this account")

    data = AquariteData(auth=auth, api=api)

    for pool_id, pool_name in pools.items():
        coordinator = AquariteDataUpdateCoordinator(
            hass, entry, auth, api, pool_id, pool_name
        )
        try:
            coordinator.data = await api.fetch_pool_data(pool_id)
            await coordinator.subscribe()
        except AquariteError as err:
            for existing in data.coordinators.values():
                await existing.async_shutdown()
            raise ConfigEntryNotReady from err
        data.coordinators[pool_id] = coordinator

    data.token_task = entry.async_create_background_task(
        hass, _token_refresh_loop(hass, data), "Aquarite token refresh"
    )
    data.health_task = entry.async_create_background_task(
        hass, _health_check_loop(hass, data), "Aquarite health check"
    )

    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_service(hass)

    entry.async_on_unload(lambda: _async_maybe_unregister_service(hass, entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Unload Aquarite config entry."""
    data = entry.runtime_data

    for task in (data.health_task, data.token_task):
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()

    return unloaded


async def _token_refresh_loop(hass: HomeAssistant, data: AquariteData) -> None:
    """Refresh the auth token and resubscribe all coordinators on rotation."""
    retry_delay = 10
    while not hass.is_stopping:
        try:
            if data.auth.is_token_expiring():
                _LOGGER.debug("Token expiring soon, refreshing")
                _, refreshed = await data.auth.get_client()
                if refreshed:
                    for coordinator in data.coordinators.values():
                        await coordinator.refresh_subscription()
            retry_delay = 10
            await asyncio.sleep(data.auth.calculate_sleep_duration())
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error maintaining token: %s, retrying in %ss", err, retry_delay
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 600)


async def _health_check_loop(hass: HomeAssistant, data: AquariteData) -> None:
    """Periodically verify connectivity and resubscribe all pools on failure."""
    while not hass.is_stopping:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            await data.auth.get_client()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Health check failed, resubscribing all pools: %s", err)
            for coordinator in data.coordinators.values():
                with contextlib.suppress(Exception):  # noqa: BLE001
                    await coordinator.refresh_subscription()


def _async_register_service(hass: HomeAssistant) -> None:
    """Register the sync_pool_time service if not already registered."""
    if hass.services.has_service(DOMAIN, "sync_pool_time"):
        return

    async def handle_sync_time(_call: ServiceCall) -> None:
        """Sync pool time across all loaded entries and pools."""
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if config_entry.state is not ConfigEntryState.LOADED:
                continue
            for coordinator in config_entry.runtime_data.coordinators.values():
                await coordinator.set_pool_time_to_now()

    hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)


def _async_maybe_unregister_service(
    hass: HomeAssistant, unloading_entry: AquariteConfigEntry
) -> None:
    """Remove the sync_pool_time service if no other entries remain loaded."""
    remaining = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != unloading_entry.entry_id and e.state is ConfigEntryState.LOADED
    ]
    if not remaining:
        hass.services.async_remove(DOMAIN, "sync_pool_time")
