import aiohttp
import json
import datetime
import logging

from homeassistant.core import HomeAssistant
from google.oauth2.credentials import Credentials
from google.cloud.firestore_v1 import Client as FirestoreClient
from .const import API_KEY

_LOGGER = logging.getLogger(__name__)

class UnauthorizedException(Exception):
    """Exception raised for unauthorized access."""
    pass

class IdentityToolkitAuth:
    def __init__(self, hass: HomeAssistant, email: str, password: str):
        self.hass = hass
        self.api_key = API_KEY
        self.email = email
        self.password = password
        self.base_url = "https://identitytoolkit.googleapis.com/v1/accounts"
        self.token_url = "https://securetoken.googleapis.com/v1/token"
        self.tokens = None
        self.expiry = None
        self.credentials = None
        self.client = None

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
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as resp:
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
                self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def refresh_token(self):
        """Refresh the access token using the refresh token."""
        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        data = json.dumps({
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refreshToken"]
        })
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as resp:
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
                self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def get_credentials(self):
        """Get the current credentials, refreshing them if necessary."""
        if self.expiry and datetime.datetime.now() >= self.expiry:
            await self.refresh_token()
        return self.credentials

