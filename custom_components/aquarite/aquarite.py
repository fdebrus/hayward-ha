import datetime
import json

import asyncio
from aiohttp import ClientResponseError, ClientSession
from google.cloud.firestore import Client, DocumentSnapshot
from google.oauth2.credentials import Credentials

import logging

__title__ = "Aquarite"
__version__ = "0.0.7"
__author__ = "Frederic Debrus"
__license__ = "MIT"

API_KEY = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"
GOOGLE_IDENTITY_REST_API = "https://identitytoolkit.googleapis.com/v1/accounts"
HAYWARD_REST_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

_LOGGER = logging.getLogger(__name__)

class Aquarite:
    """Aquarite API."""

    def __init__(self, aiohttp_session: ClientSession, username: str, password: str) -> None:
        """Initialize Aquarite API."""
        self.aiohttp_session = aiohttp_session
        self.username = username
        self.password = password
        self.tokens = None
        self.expiry = None
        self.credentials = Credentials | None
        self.client = Client | None
        self.handlers = []

    @classmethod
    async def create(cls, aiohttp_session, username, password):
        instance = cls(aiohttp_session, username, password)
        await instance.signin()
        asyncio.create_task(instance.start_token_refresh_routine())
        return instance

    async def start_token_refresh_routine(self):
        while True:
            try:
                await self.ensure_active_token()
                await asyncio.sleep(self.calculate_sleep_duration())
            except Exception as e:
                _LOGGER.error(f"Error maintaining token: {str(e)}")
                break

    def calculate_sleep_duration(self):
        time_to_expiry = (self.expiry - datetime.datetime.now()).total_seconds()
        return max(time_to_expiry - 300, 10)

    async def get_token_and_expiry(self):
        """Fetch token and expiry using Google API."""
        url = f"{GOOGLE_IDENTITY_REST_API}:signInWithPassword?key={API_KEY}"
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        data = json.dumps({
            "email": self.username,
            "password": self.password,
            "returnSecureToken": True
        })
        resp = await self.aiohttp_session.post(url, headers=headers, data=data)
        if resp.status == 400:
            raise UnauthorizedException("Failed to authenticate.")
        self.tokens = await resp.json()
        self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(self.tokens["expiresIn"]))
        self.credentials = Credentials(token=self.tokens['idToken'])
        self.client = Client(project="hayward-europe", credentials=self.credentials)
        if hasattr(self, 'handlers') and self.handlers:
            for pool_id, handler in self.handlers:
                _LOGGER.debug(f"Resubscribing to pool {pool_id}")
                await self.subscribe(pool_id, handler)

    async def ensure_active_token(self):
        """Ensure that the token is still valid, and refresh it if necessary."""
        _LOGGER.debug(f"Token check, {datetime.datetime.now()} {self.expiry}...")
        if datetime.datetime.now() >= (self.expiry - datetime.timedelta(minutes=5)): 
            _LOGGER.info("Token expired, refreshing...")
            await self.get_token_and_expiry()

    async def signin(self):
        """Sign in and set the tokens and expiry."""
        await self.get_token_and_expiry()

    async def get_pools(self):
        """Get all pools for current user."""
        data = {}
        user_dict = self.client.collection("users").document(self.tokens["localId"]).get().to_dict()
        for poolId in user_dict.get("pools", []):
            pooldict = self.client.collection("pools").document(poolId).get().to_dict()
            if pooldict is not None:
                try:
                    name = pooldict["form"]["names"][0]["name"]
                except (KeyError, IndexError):
                    name = pooldict.get("form", {}).get("name", "Unknown")
                data[poolId] = name
        return data

    async def get_pool(self, pool_id) -> DocumentSnapshot:
        self._pool_id = self.client.collection("pools").document(pool_id).get()
        _LOGGER.debug(f"{self._pool_id.to_dict()}")
        return self._pool_id

    async def subscribe(self, pool_id, handler) -> None:
        doc_ref = self.client.collection("pools").document(pool_id)
        def on_snapshot(doc_snapshot, changes, read_time):
            """Handles document snapshots."""
            try:
                for change in changes:
                    _LOGGER.debug(f"Received change {change.type} in firestore")
                for doc in doc_snapshot:
                    try:
                        handler(doc)
                    except Exception as handler_error:
                        _LOGGER.error(f"Error executing handler: {handler_error}")
            except Exception as e:
                _LOGGER.error(f"Error in on_snapshot: {e}")
        doc_ref.on_snapshot(on_snapshot)
        self.handlers.append((pool_id, handler))
        max_size = 10
        self.handlers = self.handlers[-max_size:]

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

    async def __get_pool_as_json(self, pool_id):
        pool = await self.get_pool(pool_id)        
        data = {"gateway" : pool.get("wifi"),
                "operation" : "WRP",
                "operationId" : None,
                "pool": {"backwash": pool.get("backwash"),
                            "filtration": pool.get("filtration"),
                            "hidro" : pool.get("hidro"),
                            "light" : pool.get("light"),
                            "main" : pool.get("main"),
                            "relays" : pool.get("relays"),
                            "modules" : pool.get("modules")
                        },
                "poolId" : pool_id,
                "source" : "web"}
        _LOGGER.debug(f"{data}")
        return data

#### UTILS
    def get_from_dict(self, data_dict, map_list):
        """Retrieve a value from a nested dictionary using a list of keys."""
        for k in map_list:
            data_dict = data_dict[k]
        return data_dict

    def set_in_dict(self, data_dict, map_list, value):
        """Set a value in a nested dictionary using a list of keys."""
        for k in map_list[:-1]:
            data_dict = data_dict.setdefault(k, {})
        data_dict[map_list[-1]] = value

#### SWITCHES
    async def turn_on_switch(self, pool_id: str, value_path: str) -> None:
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            self.__update_pool_data(pool_data, value_path, 1)
            pool_data['changes'] = [{"kind": "E", "path": value_path.split('.'), "lhs": 0, "rhs": 1}]
            await self.__send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned on for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn on switch for pool ID {pool_id}: {e}")
            raise

    async def turn_off_switch(self, pool_id: str, value_path: str) -> None:
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            self.__update_pool_data(pool_data, value_path, 0)
            pool_data['changes'] = [{"kind": "E", "path": value_path.split('.'), "lhs": 1, "rhs": 0}]
            await self.__send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned off for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn off switch for pool ID {pool_id}: {e}")
            raise

#### PUMP MODE
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

            await self.__send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set pump mode for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set pump mode: {e}") from e

#### PUMP SPEED
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

            await self.__send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set pump speed for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set pump speed: {e}") from e

#### SET VALUE
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

            await self.__send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set {value_path} for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set {value_path}: {e}") from e

### SEND COMMAND
    async def __send_command(self, data) -> None:
        headers = {"Authorization": f"Bearer {self.tokens['idToken']}"}
        try:
            response = await self.aiohttp_session.post(
                f"{HAYWARD_REST_API}/sendCommand",
                json=data,
                headers=headers
            )
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

class UnauthorizedException(Exception):
    """Unauthorized user exception."""
