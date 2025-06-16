import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import binary_sensor, light, switch, sensor, select, number
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .application_credentials import IdentityToolkitAuth
from .aquarite import Aquarite
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    binary_sensor.DOMAIN, light.DOMAIN, switch.DOMAIN,
    sensor.DOMAIN, select.DOMAIN, number.DOMAIN
]

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aquarite from a config entry."""
    try:
        user_config = entry.data

        # Authenticate using credentials from config entry
        auth = IdentityToolkitAuth(hass, user_config["username"], user_config["password"])
        await auth.authenticate()

        # Create Aquarite API client and coordinator
        aiohttp_session = async_get_clientsession(hass)
        api = Aquarite(auth, hass, aiohttp_session)
        coordinator = AquariteDataUpdateCoordinator(hass, auth, api)
        coordinator.set_pool_id(user_config["pool_id"])

        # First refresh: ensures data is loaded before platforms/entities initialize
        await coordinator.async_config_entry_first_refresh()
        await coordinator.subscribe()

        # Store in hass.data for access by platforms/entities
        hass.data[DOMAIN]["coordinator"] = coordinator
        hass.data[DOMAIN]["aiohttp_session"] = aiohttp_session

        # Forward setup to all supported platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    except Exception as e:
        _LOGGER.error(f"Error setting up entry {entry.entry_id}: {e}", exc_info=True)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Aquarite config entry and clean up resources."""
    try:
        coordinator = hass.data[DOMAIN].get("coordinator")
        if coordinator:
            await coordinator.unsubscribe()
            await coordinator.auth.close()
        aiohttp_session = hass.data[DOMAIN].get("aiohttp_session")
        if aiohttp_session:
            await aiohttp_session.close()

        # Unload the platforms associated with this entry
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        # Clean up hass.data
        hass.data[DOMAIN].pop("coordinator", None)
        hass.data[DOMAIN].pop("aiohttp_session", None)
        hass.data[DOMAIN].pop("token_refresh_task", None)

        return unload_ok

    except Exception as e:
        _LOGGER.error(f"Error unloading entry {entry.entry_id}: {e}", exc_info=True)
        return False
