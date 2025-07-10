import logging
import asyncio
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from pyaquarite import AquariteAuth, AquariteAPI, AuthenticationError

from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator

PLATFORMS = [
    "sensor",
    "switch",
    "light",
    "number",
    "select",
    "binary_sensor",
    "device_tracker",
]
_LOGGER = logging.getLogger(__name__)

async def start_firestore_listener(auth, pool_id, update_callback):
    # Use your custom authenticated Firestore client (user-token based)
    client = await auth.get_client()
    doc_ref = client.collection("pools").document(pool_id)

    def on_snapshot(doc_snapshot, changes, read_time):
        for doc in doc_snapshot:
            data = doc.to_dict()
            _LOGGER.debug("Firestore update for pool %s: %s", pool_id, data)
            update_callback(data)
    return doc_ref.on_snapshot(on_snapshot)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aquarite integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        api_key = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"
        auth = AquariteAuth(
            entry.data["username"], entry.data["password"], api_key=api_key
        )
        await auth.authenticate()

        api = AquariteAPI(auth)
        coordinator = AquariteDataUpdateCoordinator(hass, api, entry.data["pool_id"])
        await coordinator.async_config_entry_first_refresh()

        # Start Firestore listener using user-token-based client
        firestore_watch = await start_firestore_listener(
            auth, entry.data["pool_id"], coordinator.handle_firestore_update
        )
        coordinator.firestore_watch = firestore_watch

        hass.data[DOMAIN][entry.entry_id] = {
            "auth": auth,
            "api": api,
            "coordinator": coordinator,
        }

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        async def handle_sync_time(call):
            import time
            timestamp = call.data.get("timestamp", int(time.time()))
            await api.set_value(entry.data["pool_id"], "main.localTime", timestamp)

        hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

        return True

    except AuthenticationError as e:
        _LOGGER.error(f"Authentication failed: {e}")
        return False
    except Exception as e:
        _LOGGER.error(f"Setup failed: {e}")
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Aquarite integration entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        await data["auth"].close()
        await data["api"].close()
        coordinator = data.get("coordinator")
        if coordinator and hasattr(coordinator, "async_close"):
            await coordinator.async_close()

    return unload_ok
