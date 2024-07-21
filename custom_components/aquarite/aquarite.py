import asyncio
import datetime
import json
import logging
from aiohttp import ClientSession, ClientError
from google.oauth2.credentials import Credentials
from google.cloud.firestore_v1 import Client, DocumentSnapshot
from google.auth.transport.requests import Request

API_KEY = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"
GOOGLE_IDENTITY_REST_API = "https://identitytoolkit.googleapis.com/v1/accounts"
HAYWARD_REST_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

_LOGGER = logging.getLogger(__name__)

__title__ = "Aquarite"
__version__ = "0.1.2"
__author__ = "Frederic Debrus"
__license__ = "MIT"

# suppress warning message from google.api_core.bidi
logger = logging.getLogger('google.api_core.bidi')
logger.setLevel(logging.ERROR)

class Aquarite:
    """Aquarite API."""

    def __init__(self, aiohttp_session: ClientSession, username: str, password: str, coordinator=None) -> None:
        """Initialize Aquarite API."""
        self.aiohttp_session = aiohttp_session
        self.username = username
        self.password = password
        self.tokens = None
        self.expiry = None
        self.coordinator = coordinator
        self.watch = None

    def set_coordinator(self, coordinator):
        """Set the coordinator after initialization."""
        self.coordinator = coordinator

    @classmethod
    async def create(cls, aiohttp_session, username, password):
        instance = cls(aiohttp_session, username, password)
        await instance.signin_with_retries()
        asyncio.create_task(instance.start_token_refresh_routine())
        asyncio.create_task(instance.check_connectivity())
        return instance

    async def signin_with_retries(self, retries=5, delay=5):
        """Sign in with retry logic."""
        for attempt in range(retries):
            try:
                await self.signin()
                return
            except Exception as e:
                _LOGGER.error(f"Sign-in failed on attempt {attempt + 1}/{retries}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise

    async def signin(self):
        """Sign in and set the tokens and expiry."""
        url = f"{GOOGLE_IDENTITY_REST_API}:signInWithPassword?key={API_KEY}"
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        data = json.dumps({
            "email": self.username,
            "password": self.password,
            "returnSecureToken": True
        })
        async with self.aiohttp_session.post(url, headers=headers, data=data) as resp:
            if resp.status == 400:
                raise Exception("Failed to authenticate.")
            self.tokens = await resp.json()
            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(self.tokens["expiresIn"]))
            self.credentials = Credentials(token=self.tokens['idToken'])
            self.client = Client(project="hayward-europe", credentials=self.credentials)

    async def start_token_refresh_routine(self):
        while True:
            try:
                await self.ensure_active_token_with_retries()
                await asyncio.sleep(self.calculate_sleep_duration())
            except Exception as e:
                _LOGGER.error(f"Error maintaining token: {str(e)}")
                break

    async def ensure_active_token_with_retries(self, retries=5, delay=5):
        """Ensure that the token is still valid, and refresh it if necessary, with retries."""
        for attempt in range(retries):
            try:
                await self.ensure_active_token()
                return
            except Exception as e:
                _LOGGER.error(f"Token refresh failed on attempt {attempt + 1}/{retries}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise

    def calculate_sleep_duration(self):
        time_to_expiry = (self.expiry - datetime.datetime.now()).total_seconds()
        return max(time_to_expiry - 300, 10)  # Refresh 5 minutes before expiry

    async def ensure_active_token(self):
        """Ensure that the token is still valid, and refresh it if necessary."""
        if datetime.datetime.now() >= (self.expiry - datetime.timedelta(minutes=3)):
            _LOGGER.debug("Token expired, refreshing...")
            self.tokens = None
            await self.signin()
            await self.refresh_listener()

    async def subscribe(self) -> None:
        """Subscribe to the pool's updates."""
        pool_id = self.coordinator.pool_id
        handler = self.coordinator.set_updated_data

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

        self.watch = doc_ref.on_snapshot(on_snapshot)
        _LOGGER.debug(f"Subscribed with new listener for pool_id {pool_id}")

    async def refresh_listener(self):
        """Refresh the Firestore listener if token was refreshed."""
        if self.watch:
            _LOGGER.debug(f"Unsubscribing old listener: {self.watch}")
            self.watch.unsubscribe()

        _LOGGER.debug("Re-subscribing with new token")
        await self.subscribe()

    async def check_connectivity(self, interval=60):
        """Periodically check internet connectivity and attempt reconnection if disconnected."""
        while True:
            try:
                async with self.aiohttp_session.get("https://www.google.com") as response:
                    if response.status == 200:
                        if not self.tokens:
                            _LOGGER.info("Internet connection restored, attempting to reauthenticate.")
                            await self.signin_with_retries()
                        else:
                            _LOGGER.debug("Internet connection is active.")
            except ClientError:
                _LOGGER.warning("Internet connection lost. Will retry...")
            await asyncio.sleep(interval)
#################################
    async def get_pools(self):
        """Get all pools for current user."""
        data = {}
        _LOGGER.debug(f"Tokens: {self.tokens}")
        _LOGGER.debug(f"Fetching user document for localId: {self.tokens.get('localId')}")
        user_dict = await asyncio.to_thread(self.client.collection("users").document(self.tokens["localId"]).get)
        user_dict = user_dict.to_dict()
        for poolId in user_dict.get("pools", []):
            pooldict = await asyncio.to_thread(self.client.collection("pools").document(poolId).get)
            pooldict = pooldict.to_dict()
            if pooldict is not None:
                try:
                    name = pooldict["form"]["names"][0]["name"]
                except (KeyError, IndexError):
                    name = pooldict.get("form", {}).get("name", "Unknown")
                data[poolId] = name
        return data

    async def fetch_pool_data(self, pool_id) -> DocumentSnapshot:
        self._pool_data = await asyncio.to_thread(self.client.collection("pools").document(pool_id).get)
        return self._pool_data

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
            await self.send_command(pool_data)
            _LOGGER.info(f"Switch at {value_path} turned on for pool ID {pool_id}.")
        except Exception as e:
            _LOGGER.error(f"Failed to turn on switch for pool ID {pool_id}: {e}")
            raise

    async def turn_off_switch(self, pool_id: str, value_path: str) -> None:
        try:
            pool_data = await self.__get_pool_as_json(pool_id)
            self.__update_pool_data(pool_data, value_path, 0)
            pool_data['changes'] = [{"kind": "E", "path": value_path.split('.'), "lhs": 1, "rhs": 0}]
            await self.send_command(pool_data)
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

            await self.send_command(pool_data)
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

            await self.send_command(pool_data)
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

            await self.send_command(pool_data)
        except ValueError as e:
            _LOGGER.error(f"Value error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to set {value_path} for pool ID {pool_id}: {e}")
            raise Exception(f"Failed to set {value_path}: {e}") from e

### SEND COMMAND
    async def send_command(self, data) -> None:
        headers = {"Authorization": f"Bearer {self.tokens['idToken']}"}
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

class UnauthorizedException(Exception):
    """Unauthorized user exception."""
