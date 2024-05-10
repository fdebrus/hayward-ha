"""The Aquarite integration."""

from homeassistant import config_entries, core
from homeassistant.components import binary_sensor, light, switch, sensor, select, number
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import AquariteDataCoordinator
from .aquarite import Aquarite

PLATFORMS = [binary_sensor.DOMAIN, light.DOMAIN, switch.DOMAIN, sensor.DOMAIN, select.DOMAIN, number.DOMAIN]

async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up the Hayward component."""

    api = await Aquarite.create(async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    coordinator = AquariteDataCoordinator(hass, api)

    api.set_coordinator(coordinator)

    coordinator.data = await api.fetch_pool_data(entry.data["pool_id"])
    coordinator.pool_id = entry.data["pool_id"]
    
    await api.subscribe()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Async setup component."""
    return True
