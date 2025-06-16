import logging
import json
import copy
import asyncio
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from typing import Any

from .const import DOMAIN, HAYWARD_REST_API, BRAND, MODEL
from .application_credentials import IdentityToolkitAuth

_LOGGER = logging.getLogger(__name__)

class Aquarite:
    """Aquarite API client."""

    def __init__(self, auth: IdentityToolkitAuth, hass: HomeAssistant, aiohttp_session: async_get_clientsession) -> None:
        """Initialize the API client."""
        self.auth = auth
        self.hass = hass
        self.aiohttp_session = aiohttp_session

    async def get_pools(self):
        """Get all pools for the current user."""
        data = {}
        client = await self.auth.get_client()
        user_dict = await asyncio.to_thread(client.collection("users").document(self.auth.tokens["localId"]).get)
        user_dict = user_dict.to_dict()
        for poolId in user_dict.get("pools", []):
            pooldict = await asyncio.to_thread(client.collection("pools").document(poolId).get)
            pooldict = pooldict.to_dict()
            if pooldict is not None:
                try:
                    name = pooldict["form"]["names"][0]["name"]
                except (KeyError, IndexError):
                    name = pooldict.get("form", {}).get("name", "Unknown")
                data[poolId] = name
        return data

    async def fetch_pool_data(self, pool_id) -> dict:
        client = await self.auth.get_client()
        pool_data = await asyncio.to_thread(client.collection("pools").document(pool_id).get)
        return pool_data.to_dict()

    def get_pool_data_as_json(self, pool_id: str) -> dict:
        """Get the pool data."""
        coordinator = self.hass.data[DOMAIN].get("coordinator")
        pool = coordinator.data

        data = {
            "gateway": pool.get("wifi"),
            "poolId": pool_id,
            "operation": "WRP",
            "operationId": None,
            "changes": None,
            "pool": None,
            "source": "web"
        }
        return data

    async def send_command(self, data) -> None:
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        try:
            async with self.aiohttp_session.post(
                f"{HAYWARD_REST_API}/sendPoolCommand",
                json=data,
                headers=headers,
                timeout=15
            ) as response:
                _LOGGER.debug(f"Command sent with response status: {response.status}")
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"Server returned a response error: {e.status} - {e.message}")
            raise
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Aiohttp client encountered an error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred when sending command: {e}")
            raise

### VALUE SETTING

    async def set_value(self, pool_id: str, value_path: str, value: Any) -> None:
        try:
            pool_data = self.get_pool_data_as_json(pool_id)
            coordinator = self.hass.data[DOMAIN].get("coordinator")
            current_path_config = self.extract_complete_info(coordinator.data, value_path)
            self.set_in_dict(current_path_config, value_path, value)
            pool_data['changes'] = json.dumps(current_path_config)
            _LOGGER.debug(f"Setting {value_path} to {value} for pool ID {pool_id} --- {pool_data}")
            await self.send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set value for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set value: {e}") from e

### UTILS

    def set_in_dict(self, data_dict, path, value):
        map_list = path.split(".")
        temp = data_dict
        for key in map_list[:-1]:
            if key not in temp:
                temp[key] = {}
            temp = temp[key]
        last_key = map_list[-1]
        temp[last_key] = value

#    def extract_complete_info(self, data, path):
#        keys = path.split('.')
#        subset = data
#        if len(keys) > 2:
#            keys = keys[:2]
#        elif len(keys) > 1:
#            keys = keys[:1]
#        try:
#            for key in keys:
#                subset = subset[key]
#        except KeyError:
#            return f"Key error: Key '{key}' not found in data"
#        result = subset
#        for key in reversed(keys):
#            result = {key: result}
#        return result

    def extract_complete_info(self, data, path):
        keys = path.split('.')
        subset = data
        trimmed_keys = keys[:2] if len(keys) > 2 else keys[:1]
    
        try:
            for key in trimmed_keys:
                subset = subset[key]
        except KeyError as e:
            raise KeyError(f"Key error: '{e.args[0]}' not found in data")

        result = subset
        for key in reversed(trimmed_keys):
            result = {key: result}
        return result
