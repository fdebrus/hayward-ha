import logging
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import binary_sensor, light, switch, sensor, select, number, device_tracker
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [binary_sensor.DOMAIN, light.DOMAIN, switch.DOMAIN, sensor.DOMAIN, select.DOMAIN, number.DOMAIN, device_tracker.DOMAIN]

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aquarite from a config entry."""
    try:
        # Get user configuration from the entry
        user_config = entry.data
        
        # Authenticate using the provided credentials
        auth = IdentityToolkitAuth(hass, user_config["username"], user_config["password"])
        await auth.authenticate()

        # Initialize aiohttp session using Home Assistant's helper
        aiohttp_session = async_get_clientsession(hass)

        # Create an instance of the Aquarite API client
        api = Aquarite(auth, hass, aiohttp_session)

        # Initialize the coordinator with the API client
        coordinator = AquariteDataUpdateCoordinator(hass, auth, api)
        coordinator.set_pool_id(user_config["pool_id"])
        
        # Fetch initial pool data
        coordinator.data = await api.fetch_pool_data(user_config["pool_id"])
        await coordinator.subscribe()

        # Store the coordinator and aiohttp session in Home Assistant's data
        hass.data[DOMAIN]["coordinator"] = coordinator
        hass.data[DOMAIN]["aiohttp_session"] = aiohttp_session

        # Start the token refresh routine
        asyncio.create_task(auth.start_token_refresh_routine(coordinator))

        # Forward the entry setups for the defined platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        async def handle_sync_time(call):
            await coordinator.set_pool_time_to_now()
        hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

        return True

    except Exception as e:
        _LOGGER.error(f"Error setting up entry {entry.entry_id}: {e}")
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Aquarite config entry."""
    try:
        # Unload the platforms associated with this entry
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except Exception as e:
        _LOGGER.error(f"Error unloading entry {entry.entry_id}: {e}")
        return False
