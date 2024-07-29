import logging
import json
from aiohttp import ClientSession, ClientError, ClientResponseError
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from typing import Any

from .const import DOMAIN, HAYWARD_REST_API, BRAND, MODEL
from .application_credentials import IdentityToolkitAuth

_LOGGER = logging.getLogger(__name__)

class Aquarite:
    """Aquarite API client."""

    def __init__(self, auth: IdentityToolkitAuth, hass: HomeAssistant, aiohttp_session: ClientSession) -> None:
        """Initialize the API client."""
        self.auth = auth
        self.hass = hass
        self.aiohttp_session = aiohttp_session

    def get_pool_data_as_json(self, pool_id: str) -> dict:
        """Get the pool data."""
        coordinator = self.hass.data[DOMAIN].get("coordinator")
        pool_data = coordinator.data
        data = {
            "gateway": pool_data.get("wifi"),
            "operation": "WRP",
            "operationId": None,
            "poolId": pool_id,
            "source": "web"
        }
        return data

    async def send_command(self, data) -> None:
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        try:
            async with self.aiohttp_session.post(
                f"{HAYWARD_REST_API}/sendPoolCommand",
                json=data,
                headers=headers
            ) as response:
                _LOGGER.debug(f"Command sent with response status: {response.status}")
                response.raise_for_status()
        except ClientResponseError as e:
            _LOGGER.error(f"Server returned a response error: {e.status} - {e.message}")
            raise
        except ClientError as e:
            _LOGGER.error(f"Aiohttp client encountered an error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred when sending command: {e}")
            raise

    async def turn_on_switch(self, pool_id: str, value_path: str) -> None:
        try:
            # Get the initial pool data
            pool_data = self.get_pool_data_as_json(pool_id)

            # Split the value path into keys
            path_keys = value_path.split('.')

            # Update the value in the pool data to turn on the switch
            self.set_in_dict(pool_data, path_keys, 1)

            # Prepare the changes for the API request
            pool_data['changes'] = json.dumps({
                "path": path_keys,
                "value": 1
            })

            # Send the command to the API
            await self.send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned ON for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn on switch for pool ID {pool_id}: {e}")
            raise

    async def turn_off_switch(self, pool_id: str, value_path: str) -> None:
        try:
            # Get the initial pool data
            pool_data = self.get_pool_data_as_json(pool_id)

            # Split the value path into keys
            path_keys = value_path.split('.')

            # Update the value in the pool data to turn off the switch
            self.set_in_dict(pool_data, path_keys, 0)

            # Prepare the changes for the API request
            pool_data['changes'] = json.dumps({
                "path": path_keys,
                "value": 0
            })

            # Send the command to the API
            await self.send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned OFF for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn off switch for pool ID {pool_id}: {e}")
            raise

    async def set_path_value(self, pool_id, value_path, value):
        try:
            # Get the initial pool data
            pool_data = self.get_pool_data_as_json(pool_id)
            if not pool_data:
                _LOGGER.error(f"No valid pool data found for pool ID {pool_id}.")
                raise ValueError(f"Pool data not found for the given pool ID {pool_id}.")

            # Split the value path into keys
            path_keys = value_path.split('.')
            current_value = self.get_from_dict(pool_data, path_keys)

            if current_value is None:
                _LOGGER.warning(f"Current value for {value_path} not found in pool data for pool ID {pool_id}. Assuming default.")
                current_value = 0

            # Update the value in the pool data
            self.set_in_dict(pool_data, path_keys, value)
            _LOGGER.info(f"Changing {value_path} from {current_value} to {value} for pool ID {pool_id}.")

            # Prepare the changes for the API request
            pool_data['changes'] = json.dumps({
                "path": path_keys,
                "value": value
            })

            # Send the command to the API
            await self.send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set {value_path} for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set {value_path}: {e}") from e

    def get_from_dict(self, data_dict, map_list):
        """Get a value from a nested dictionary using a list of keys."""
        for key in map_list:
            data_dict = data_dict.get(key)
            if data_dict is None:
                return None
        return data_dict

    def set_in_dict(self, data_dict, map_list, value):
        """Set a value in a nested dictionary using a list of keys."""
        for key in map_list[:-1]:
            data_dict = data_dict.setdefault(key, {})
        data_dict[map_list[-1]] = value