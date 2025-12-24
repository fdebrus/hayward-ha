import asyncio
import contextlib
import logging

from homeassistant.components import binary_sensor, device_tracker, light, number, select, sensor, switch
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .const import API_KEY, DOMAIN
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [binary_sensor.DOMAIN, light.DOMAIN, switch.DOMAIN, sensor.DOMAIN, select.DOMAIN, number.DOMAIN, device_tracker.DOMAIN]

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aquarite from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        # Get user configuration from the entry
        user_config = entry.data
        
        # Authenticate using the provided credentials
        auth = IdentityToolkitAuth(
            hass,
            user_config["username"],
            user_config["password"],
            user_config.get("api_key", API_KEY),
        )
        await auth.authenticate()

        # Initialize aiohttp session using Home Assistant's helper
        aiohttp_session = async_get_clientsession(hass)

        # Create an instance of the Aquarite API client
        api = Aquarite(auth, hass, aiohttp_session)

        # Initialize the coordinator with the API client
        coordinator = AquariteDataUpdateCoordinator(hass, auth, api)
        coordinator.set_pool_id(user_config["pool_id"])
        auth.set_coordinator(coordinator)
        api.set_coordinator(coordinator)
        
        # Fetch initial pool data
        coordinator.data = await api.fetch_pool_data(user_config["pool_id"])
        await coordinator.subscribe()

        # Start the token refresh routine
        refresh_task = hass.async_create_background_task(
            auth.start_token_refresh_routine(coordinator),
            name="Aquarite token refresh",
        )

        # Store the coordinator and aiohttp session in Home Assistant's data per entry
        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "aiohttp_session": aiohttp_session,
            "auth": auth,
            "token_task": refresh_task,
        }

        # Forward the entry setups for the defined platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        async def handle_sync_time(call):
            await coordinator.set_pool_time_to_now()

        if not hass.services.has_service(DOMAIN, "sync_pool_time"):
            hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

        return True

    except Exception as e:
        _LOGGER.error(f"Error setting up entry {entry.entry_id}: {e}")
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Aquarite config entry."""
    try:
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not entry_data:
            _LOGGER.error("No entry data found for unload.")
            return False

        coordinator: AquariteDataUpdateCoordinator = entry_data.get("coordinator")
        token_task: asyncio.Task | None = entry_data.get("token_task")

        if token_task:
            token_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await token_task

        if coordinator:
            await coordinator.async_shutdown()
            await coordinator.auth.close()

        # Unload the platforms associated with this entry
        unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        if unloaded:
            hass.data[DOMAIN].pop(entry.entry_id, None)
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN)

        return unloaded
    except Exception as e:
        _LOGGER.error(f"Error unloading entry {entry.entry_id}: {e}")
        return False
