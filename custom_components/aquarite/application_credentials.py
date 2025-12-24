import json
import datetime
import logging
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from google.oauth2.credentials import Credentials
from google.cloud.firestore_v1 import Client as FirestoreClient

from .const import API_KEY, BASE_URL, TOKEN_URL

_LOGGER = logging.getLogger(__name__)

class UnauthorizedException(Exception):
    """Exception raised for unauthorized access."""
    pass

class IdentityToolkitAuth:
    def __init__(self, hass: HomeAssistant, email: str, password: str):
        self.api_key = API_KEY
        self.hass = hass
        self.email = email
        self.password = password
        self.base_url = BASE_URL
        self.token_url = TOKEN_URL
        self.tokens = None
        self.expiry = None
        self.credentials = None
        self.client = None
        self.session = async_get_clientsession(hass)
        self.coordinator = None

    def set_coordinator(self, coordinator) -> None:
        """Attach the coordinator to allow token refresh callbacks."""

        self.coordinator = coordinator

    async def authenticate(self):
        await self.signin()
        return {
            "idToken": self.tokens["idToken"],
            "refreshToken": self.tokens["refreshToken"],
            "expiresIn": self.tokens["expiresIn"],
        }

    async def signin(self):
        """Sign in and set the tokens and expiry."""
        url = f"{self.base_url}:signInWithPassword?key={self.api_key}"
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        data = json.dumps({
            "email": self.email,
            "password": self.password,
            "returnSecureToken": True
        })
        async with self.session.post(url, headers=headers, data=data) as resp:
            if resp.status == 400:
                raise UnauthorizedException("Failed to authenticate.")
            self.tokens = await resp.json()
            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(self.tokens["expiresIn"]))
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.token_url,
                client_id=None,
                client_secret=None
            )
            _LOGGER.debug(f'{self.credentials}')
            self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def refresh_token(self):
        """Refresh the access token using the refresh token."""
        url = f"{self.token_url}?key={self.api_key}"
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        data = json.dumps({
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refreshToken"]
        })
        async with self.session.post(url, headers=headers, data=data) as resp:
            if resp.status != 200:
                raise UnauthorizedException("Failed to refresh token.")
            new_tokens = await resp.json()
            self.tokens["idToken"] = new_tokens["id_token"]
            self.tokens["refreshToken"] = new_tokens["refresh_token"]
            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(new_tokens["expires_in"]))
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.token_url,
                client_id=None,
                client_secret=None
            )
            _LOGGER.debug(f'{self.credentials}')
            self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def get_client(self):
        """Get the current client, refreshing if necessary."""
        if self.client is None:
            _LOGGER.debug("Firestore client not initialized, performing authentication.")
            await self.authenticate()

        if self.expiry and datetime.datetime.now() >= (self.expiry - datetime.timedelta(minutes=5)):
            await self.refresh_token()
            if self.coordinator:
                await self.coordinator.refresh_subscription()
        return self.client

    async def start_token_refresh_routine(self, coordinator):
        while not self.hass.is_stopping:
            try:
                await self.ensure_active_token()
                await asyncio.sleep(self.calculate_sleep_duration())
            except Exception as e:
                _LOGGER.error(f"Error maintaining token: {str(e)}")
                break

    def calculate_sleep_duration(self):
        time_to_expiry = (self.expiry - datetime.datetime.now()).total_seconds()
        return max(time_to_expiry - 300, 10)  # Refresh 5 minutes before expiry

    async def ensure_active_token(self):
        """Ensure that the token is still valid, and refresh it if necessary."""
        if datetime.datetime.now() >= (self.expiry - datetime.timedelta(minutes=5)):
            _LOGGER.debug("Token expired, refreshing...")
            await self.get_client()
