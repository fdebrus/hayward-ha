import logging
import aiohttp
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import binary_sensor, light, switch, sensor, select, number

from .const import DOMAIN
from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [binary_sensor.DOMAIN, light.DOMAIN, switch.DOMAIN, sensor.DOMAIN, select.DOMAIN, number.DOMAIN]

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aquarite from a config entry."""
    try:
        user_config = entry.data
        auth = IdentityToolkitAuth(hass, user_config["username"], user_config["password"])
        await auth.authenticate()

        aiohttp_session = aiohttp.ClientSession()

        api = Aquarite(auth, hass, aiohttp_session)

        coordinator = AquariteDataUpdateCoordinator(hass, auth, api)
        coordinator.set_pool_id(user_config["pool_id"])
        coordinator.data = await api.fetch_pool_data(user_config["pool_id"])

        await coordinator.subscribe()

        hass.data[DOMAIN]["coordinator"] = coordinator
        hass.data[DOMAIN]["aiohttp_session"] = aiohttp_session

        asyncio.create_task(auth.start_token_refresh_routine(coordinator))

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    except Exception as e:
        _LOGGER.error(f"Error setting up entry {entry.entry_id}: {e}")
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Aquarite config entry."""
    try:
        coordinator = hass.data[DOMAIN].get("coordinator")
        if coordinator:
            await coordinator.auth.close()
        
        aiohttp_session = hass.data[DOMAIN].get("aiohttp_session")
        if aiohttp_session:
            await aiohttp_session.close()

        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except Exception as e:
        _LOGGER.error(f"Error unloading entry {entry.entry_id}: {e}")
        return False
