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
    def __init__(
        self,
        hass: HomeAssistant,
        email: str,
        password: str,
        referer: str | None = None,
        origin: str | None = None,
    ):
        self.api_key = API_KEY
        self.hass = hass
        self.email = email
        self.password = password
        self.referer = referer
        self.origin = origin
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

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        if self.referer:
            headers["Referer"] = self.referer
        if self.origin:
            headers["Origin"] = self.origin
        return headers

    @staticmethod
    def _format_auth_error(payload: dict, status: int) -> str:
        error = payload.get("error", {})
        code = error.get("code", status)
        message = error.get("message", "Unknown error")
        status_text = error.get("status")
        if status_text:
            return (
                "Authentication failed "
                f"(code={code}, status={status_text}, message={message})."
            )
        return f"Authentication failed (code={code}, message={message})."

    @staticmethod
    def _normalize_tokens(tokens: dict) -> dict:
        normalized = dict(tokens)
        if "expiresIn" not in normalized and "expires_in" in normalized:
            normalized["expiresIn"] = normalized["expires_in"]
        if "idToken" not in normalized and "id_token" in normalized:
            normalized["idToken"] = normalized["id_token"]
        if "refreshToken" not in normalized and "refresh_token" in normalized:
            normalized["refreshToken"] = normalized["refresh_token"]
        return normalized

    async def signin(self):
        """Sign in and set the tokens and expiry."""
        url = f"{self.base_url}:signInWithPassword?key={self.api_key}"
        headers = self._build_headers()
        data = json.dumps({
            "email": self.email,
            "password": self.password,
            "returnSecureToken": True
        })
        async with self.session.post(url, headers=headers, data=data) as resp:
            payload = await resp.json()
            if resp.status != 200:
                raise UnauthorizedException(self._format_auth_error(payload, resp.status))
            self.tokens = self._normalize_tokens(payload)
            # Normalize token response keys (camelCase vs snake_case)
            # fail fast if the response is not what we expect
            if "idToken" not in self.tokens or "refreshToken" not in self.tokens or "expiresIn" not in self.tokens:
                raise UnauthorizedException("Unexpected token response: missing required fields.")

            try:
                expires_in = int(self.tokens["expiresIn"])
            except (TypeError, ValueError):
                raise UnauthorizedException("Unexpected token response: invalid expiry.") from None

            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.token_url,
                client_id=None,
                client_secret=None
            )
            _LOGGER.debug("Authenticated successfully; token expiry set.")
            self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def refresh_token(self):
        """Refresh the access token using the refresh token."""
        url = f"{self.token_url}?key={self.api_key}"
        headers = self._build_headers()
        data = json.dumps({
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refreshToken"]
        })
        async with self.session.post(url, headers=headers, data=data) as resp:
            payload = await resp.json()
            if resp.status != 200:
                raise UnauthorizedException(self._format_auth_error(payload, resp.status))
            new_tokens = self._normalize_tokens(payload)
            self.tokens["idToken"] = new_tokens.get("idToken", self.tokens.get("idToken"))
            if "refreshToken" in new_tokens:
                self.tokens["refreshToken"] = new_tokens["refreshToken"]

            expires_in = new_tokens.get("expiresIn")
            if expires_in is None:
                raise UnauthorizedException("Unexpected refresh response: missing expiry.")
            try:
                expires_in_int = int(expires_in)
            except (TypeError, ValueError):
                raise UnauthorizedException("Unexpected refresh response: invalid expiry.") from None

            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in_int)
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.token_url,
                client_id=None,
                client_secret=None
            )
            _LOGGER.debug("Token refreshed successfully; token expiry updated.")
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
