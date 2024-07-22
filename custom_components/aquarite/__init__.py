import logging
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import binary_sensor, light, switch, sensor, select, number

from .application_credentials import IdentityToolkitAuth
from .const import DOMAIN
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
        credentials = entry.data
        auth = IdentityToolkitAuth(hass, credentials["username"], credentials["password"])
        await auth.authenticate()

        aiohttp_session = aiohttp.ClientSession()

        api = Aquarite(auth.client, auth.tokens, aiohttp_session)

        coordinator = AquariteDataUpdateCoordinator(hass, auth, api)
        coordinator.set_pool_id(credentials["pool_id"])
        coordinator.data = await api.fetch_pool_data(credentials["pool_id"])
        
        await coordinator.subscribe()
        
        hass.data[DOMAIN][entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        return True
        
    except Exception as e:
        _LOGGER.error(f"Error setting up entry {entry.entry_id}: {e}")
        return False
