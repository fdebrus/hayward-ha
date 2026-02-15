"""The Aquarite integration."""
from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .application_credentials import IdentityToolkitAuth, UnauthorizedException
from .aquarite import Aquarite
from .coordinator import AquariteDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aquarite from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        user_config = entry.data
        auth = IdentityToolkitAuth(hass, user_config[CONF_USERNAME], user_config[CONF_PASSWORD])
        await auth.authenticate()

        api = Aquarite(auth, hass, async_get_clientsession(hass))
        coordinator = AquariteDataUpdateCoordinator(hass, auth, api)
        coordinator.set_pool_id(user_config["pool_id"])
        
        auth.set_coordinator(coordinator)
        api.set_coordinator(coordinator)
        
        # Initial data fetch and subscription
        coordinator.data = await api.fetch_pool_data(user_config["pool_id"])
        await coordinator.subscribe()

        # Start all background tasks (Refresh, Health, and Polling) via coordinator
        await coordinator.setup_tasks()

        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "auth": auth,
        }

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        async def handle_sync_time(call):
            """Service call to sync pool time."""
            await coordinator.set_pool_time_to_now()

        if not hass.services.has_service(DOMAIN, "sync_pool_time"):
            hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

        return True

    except UnauthorizedException as exc:
        raise ConfigEntryAuthFailed from exc
    except Exception as exc:
        _LOGGER.error("Error setting up entry %s: %s", entry.entry_id, exc)
        raise ConfigEntryNotReady from exc

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Aquarite config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        return False

    coordinator = entry_data.get("coordinator")
    
    # Forward unloading to platforms first
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        # Cancel all tasks (polling, health, and snapshots)
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded