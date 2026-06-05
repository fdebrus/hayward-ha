"""The Aquarite integration."""

from __future__ import annotations

from dataclasses import dataclass
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


AquariteConfigEntry = ConfigEntry[AquariteRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up Aquarite from a config entry."""
    user_config = entry.data
    session = async_get_clientsession(hass)
    pool_id: str = user_config["pool_id"]

    auth = AquariteAuth(session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD])
    try:
        await auth.authenticate()
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from exc
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    api = AquariteClient(auth)
    coordinator = AquariteDataUpdateCoordinator(hass, entry, auth, api, pool_id)

    # Initial data fetch (raises ConfigEntryNotReady on failure) and subscription.
    await coordinator.async_config_entry_first_refresh()
    try:
        await coordinator.subscribe()
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc
    entry.async_on_unload(coordinator.async_shutdown)

    entry.runtime_data = AquariteRuntimeData(coordinator=coordinator, auth=auth)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
            if e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, "sync_pool_time")

    entry.async_on_unload(_maybe_remove_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Unload Aquarite config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
