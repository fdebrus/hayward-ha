import asyncio
import logging
from aiohttp import ClientSession, ClientError
from google.cloud.firestore_v1 import DocumentSnapshot

from .const import HAYWARD_REST_API

_LOGGER = logging.getLogger(__name__)

class Aquarite:
    """Aquarite API client."""

    def __init__(self, auth, aiohttp_session) -> None:
        """Initialize the API client."""
        self.auth = auth
        self.aiohttp_session = aiohttp_session

    async def fetch_pool_data(self, pool_id) -> dict:
        client = await self.auth.get_client()
        pool_data = await asyncio.to_thread(client.collection("pools").document(pool_id).get)
        return pool_data.to_dict()

    async def __get_pool_as_json(self, pool_id):
        pool = await self.fetch_pool_data(pool_id)
        data = {"gateway": pool.get("wifi"),
                "operation": "WRP",
                "operationId": None,
                "pool": {"backwash": pool.get("backwash"),
                        "filtration": pool.get("filtration"),
                        "hidro": pool.get("hidro"),
                        "light": pool.get("light"),
                        "main": pool.get("main"),
                        "relays": pool.get("relays"),
                        "modules": pool.get("modules")
                        },
                "poolId": pool_id,
                "source": "web"}
        _LOGGER.debug(f"{data}")
        return data

    def __update_pool_data(self, pool_data, value_path, value):
        nested_dict = pool_data["pool"]
        keys = value_path.split('.')
        for key in keys[:-1]:
            if key in nested_dict:
                nested_dict = nested_dict[key]
            else:
                nested_dict[key] = {}
                nested_dict = nested_dict[key]
        nested_dict[keys[-1]] = value

    async def send_command(self, data) -> None:
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        try:
            async with self.aiohttp_session.post(
                f"{HAYWARD_REST_API}/sendCommand",
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
            pool_data = await self.__get_pool_as_json(pool_id)
            self.__update_pool_data(pool_data, value_path, 1)
            pool_data['changes'] = [{"kind": "E", "path": value_path.split('.'), "lhs": 0, "rhs": 1}]
            await self.send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned ON for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn on switch for pool ID {pool_id}: {e}")
            raise

    async def turn_off_switch(self, pool_id: str, value_path: str) -> None:
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            self.__update_pool_data(pool_data, value_path, 0)
            pool_data['changes'] = [{"kind": "E", "path": value_path.split('.'), "lhs": 1, "rhs": 0}]
            await self.send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned OFF for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn off switch for pool ID {pool_id}: {e}")
            raise

    async def set_pump_mode(self, pool_id: str, pump_mode: str) -> None:
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            if not pool_data or 'pool' not in pool_data:
                _LOGGER.error(f"No valid pool data found for pool ID {pool_id}.")
                raise ValueError(f"Pool data not found for the given pool ID {pool_id}.")

            current_mode = pool_data['pool']['filtration'].get('mode')
            if current_mode is None:
                _LOGGER.warning(f"Current mode not found in pool data for pool ID {pool_id}. Assuming default.")
                current_mode = 'Manual'

            pool_data['pool']['filtration']['mode'] = pump_mode
            _LOGGER.info(f"Changing pump mode from {current_mode} to {pump_mode} for pool ID {pool_id}.")

            pool_data['changes'] = [
                {"kind": "E", "path": ["filtration", "mode"], "lhs": current_mode, "rhs": pump_mode}
            ]

            await self.send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set pump mode for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set pump mode: {e}") from e

    async def set_pump_speed(self, pool_id: str, pump_speed: int) -> None:
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            if not pool_data or 'pool' not in pool_data:
                _LOGGER.error(f"No valid pool data found for pool ID {pool_id}.")
                raise ValueError(f"Pool data not found for the given pool ID {pool_id}.")

            current_speed = pool_data['pool']['filtration'].get('manVel')
            if current_speed is None:
                _LOGGER.warning(f"Current speed not found in pool data for pool ID {pool_id}. Assuming default speed.")
                current_speed = 0

            pool_data['pool']['filtration']['manVel'] = pump_speed

            _LOGGER.info(f"Changing pump speed from {current_speed} to {pump_speed} for pool ID {pool_id}.")

            pool_data['changes'] = [
                {"kind": "E", "path": ["filtration", "manVel"], "lhs": current_speed, "rhs": pump_speed}
            ]

            await self.send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set pump speed for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set pump speed: {e}") from e

    async def set_path_value(self, pool_id, value_path, value):
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            if not pool_data or 'pool' not in pool_data:
                _LOGGER.error(f"No valid pool data found for pool ID {pool_id}.")
                raise ValueError(f"Pool data not found for the given pool ID {pool_id}.")

            path_keys = value_path.split('.')
            current_value = self.get_from_dict(pool_data['pool'], path_keys)

            if current_value is None:
                _LOGGER.warning(f"Current value for {value_path} not found in pool data for pool ID {pool_id}. Assuming default.")
                current_value = 0

            self.set_in_dict(pool_data['pool'], path_keys, value)
            _LOGGER.info(f"Changing {value_path} from {current_value} to {value} for pool ID {pool_id}.")

            pool_data['changes'] = [
                {"kind": "E", "path": path_keys, "lhs": current_value, "rhs": value}
            ]

            await self.send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set {value_path} for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set {value_path}: {e}") from e

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
