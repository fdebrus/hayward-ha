import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AquariteDataUpdateCoordinator(DataUpdateCoordinator):
    """Aquarite Data Coordinator."""

    def __init__(self, hass: HomeAssistant, api, pool_id: str) -> None:
        """Initialize the coordinator with pool_id."""
        self.api = api
        self.pool_id: Optional[str] = pool_id  # Set on creation!
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquarite",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )

    async def _async_update_data(self) -> Any:
        """Fetch data from the API."""
        if not self.pool_id:
            _LOGGER.error("No pool_id set in coordinator!")
            return None
        try:
            pool_data = await self.api.get_pool_data(self.pool_id)
            return pool_data
        except Exception as err:
            _LOGGER.error(f"Error updating data for pool_id {self.pool_id}: {err}")
            # Defensive: return old data if available, else None
            return getattr(self, "data", None)

    def get_value(self, path: str) -> Any:
        """Return value from nested dict by dot path."""
        value = getattr(self, "data", None)
        if value is None:
            return None
        for key in path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list):
                try:
                    key = int(key)
                    value = value[key]
                except Exception:
                    return None
            else:
                return None
        return value

    def get_pool_name(self):
        """
        Return the pool name for this config entry's pool.
        Looks for form.names[0].name, falling back to form.name.
        """
        data = getattr(self, "data", None)
        if not data:
            _LOGGER.debug("get_pool_name: No data available in coordinator")
            return "Unknown"

        try:
            form = data.get("form", {})
            names = form.get("names", [])
            _LOGGER.debug(f"get_pool_name: form={form}, names={names}")
            if isinstance(names, list) and names:
                name = names[0].get("name")
                _LOGGER.debug(f"get_pool_name: Found names[0].name = {name}")
                if name:
                    return name
            name = form.get("name")
            _LOGGER.debug(f"get_pool_name: Fallback form.name = {name}")
            if name:
                return name
        except Exception as e:
            _LOGGER.error(f"Error extracting pool name: {e}")
        _LOGGER.debug("get_pool_name: Pool name not found, returning 'Unknown'")
        return "Unknown"

    async def set_pool_time_to_now(self):
        """Set the pool device time to Home Assistant's current local time."""
        import time

        if not self.pool_id:
            _LOGGER.error("No pool_id set in coordinator!")
            return
        unix_timestamp_local = int(time.time())
        _LOGGER.info(
            f"Setting Aquarite pool time to {unix_timestamp_local} for pool_id {self.pool_id}"
        )
        try:
            await self.api.set_value(
                self.pool_id, "main.localTime", unix_timestamp_local
            )
        except Exception as e:
            _LOGGER.error(f"Failed to set pool time: {e}")
