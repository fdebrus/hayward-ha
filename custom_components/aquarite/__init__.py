"""The Aquarite integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import logging

from aioaquarite import AquariteAuth, AquariteClient, AuthenticationError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
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
class AquariteRuntimeData:
    """Runtime data for the Aquarite integration."""

    coordinator: AquariteDataUpdateCoordinator
    auth: AquariteAuth
    token_task: asyncio.Task[None] | None = None
    health_task: asyncio.Task[None] | None = None


AquariteConfigEntry = ConfigEntry[AquariteRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up Aquarite from a config entry."""
    try:
        user_config = entry.data
        session = async_get_clientsession(hass)
        pool_id: str = user_config["pool_id"]

        auth = AquariteAuth(
            session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD]
        )
        await auth.authenticate()

        api = AquariteClient(auth)

        coordinator = AquariteDataUpdateCoordinator(hass, entry, auth, api, pool_id)

        # Initial data fetch and subscription
        coordinator.data = await api.fetch_pool_data(pool_id)
        await coordinator.subscribe()

        # Anchor the long-running loops to the entry so HA cancels them
        # automatically on entry unload (see async_unload_entry below).
        token_task = entry.async_create_background_task(
            hass, coordinator.token_refresh_loop(), "Aquarite token refresh"
        )
        health_task = entry.async_create_background_task(
            hass, coordinator.periodic_health_check(), "Aquarite health check"
        )

        entry.runtime_data = AquariteRuntimeData(
            coordinator=coordinator,
            auth=auth,
            token_task=token_task,
            health_task=health_task,
        )

        async def handle_sync_time(call: ServiceCall) -> None:
            """Service call to sync pool time for all loaded entries."""
            for config_entry in hass.config_entries.async_entries(DOMAIN):
                if config_entry.state is ConfigEntryState.LOADED:
                    await config_entry.runtime_data.coordinator.set_pool_time_to_now()

        if not hass.services.has_service(DOMAIN, "sync_pool_time"):
            hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

        def _maybe_remove_service() -> None:
            """Remove service if this is the last loaded entry."""
            remaining = [
                e
                for e in hass.config_entries.async_entries(DOMAIN)
                if e.entry_id != entry.entry_id
                and e.state is ConfigEntryState.LOADED
            ]
            if not remaining:
                hass.services.async_remove(DOMAIN, "sync_pool_time")

        entry.async_on_unload(_maybe_remove_service)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except Exception as exc:
        _LOGGER.error("Error setting up entry %s: %s", entry.entry_id, exc)
        raise ConfigEntryNotReady from exc


async def async_unload_entry(
    hass: HomeAssistant, entry: AquariteConfigEntry
) -> bool:
    """Unload Aquarite config entry."""
    data = entry.runtime_data

    # Cancel background loops first so the resubscription paths can't fire
    # while platforms (and the coordinator) are being torn down.
    for task in (data.health_task, data.token_task):
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        await data.coordinator.async_shutdown()

    return unloaded
