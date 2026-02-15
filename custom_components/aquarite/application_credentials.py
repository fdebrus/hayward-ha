import datetime
import logging
import asyncio
from urllib.parse import urlparse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from google.oauth2.credentials import Credentials
from google.cloud.firestore_v1 import Client as FirestoreClient

from .const import API_KEY, API_REFERRER, IDENTITY_TOOLKIT_BASE, SECURETOKEN_URL

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
    ):
        self.api_key = API_KEY
        self.hass = hass
        self.email = email
        self.password = password
        self.base_url = IDENTITY_TOOLKIT_BASE
        self.token_url = SECURETOKEN_URL
        self.tokens = None
        self.expiry = None
        self.credentials = None
        self.client = None
        self.session = async_get_clientsession(hass)
        self.coordinator = None
        self._lock = asyncio.Lock()  # Prevent simultaneous refresh calls

    def set_coordinator(self, coordinator) -> None:
        """Attach the coordinator to allow token refresh callbacks."""
        self.coordinator = coordinator

    async def authenticate(self):
        """Initial sign-in to get tokens."""
        await self.signin()
        return {
            "idToken": self.tokens["idToken"],
            "refreshToken": self.tokens["refreshToken"],
            "expiresIn": self.tokens["expiresIn"],
        }

    def _build_headers(self, content_type: str) -> dict[str, str]:
        headers = {"Content-Type": content_type}
        if API_REFERRER:
            headers["Referer"] = API_REFERRER
            origin = self._derive_origin(API_REFERRER)
            if origin:
                headers["Origin"] = origin
        return headers

    @staticmethod
    def _derive_origin(referrer: str) -> str | None:
        parsed = urlparse(referrer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return referrer or None

    @staticmethod
    async def _safe_json(resp) -> dict:
        try:
            data = await resp.json(content_type=None)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _format_auth_error(payload: dict, status: int) -> str:
        error = payload.get("error", {})
        code = error.get("code", status)
        message = error.get("message", "Unknown error")
        status_text = error.get("status")
        if status_text:
            return f"Authentication failed (code={code}, status={status_text}, message={message})."
        return f"Authentication failed (code={code}, message={message})."

    @staticmethod
    def _normalize_tokens(tokens: dict) -> dict:
        normalized = dict(tokens)
        mapping = {
            "expiresIn": ["expires_in"],
            "idToken": ["id_token", "access_token"],
            "refreshToken": ["refresh_token"],
            "localId": ["local_id", "user_id"]
        }
        for target, aliases in mapping.items():
            if target not in normalized:
                for alias in aliases:
                    if alias in normalized:
                        normalized[target] = normalized[alias]
                        break
        return normalized

    async def signin(self):
        """Sign in and set the tokens and expiry."""
        url = f"{self.base_url}:signInWithPassword?key={self.api_key}"
        headers = self._build_headers("application/json; charset=UTF-8")
        data = {
            "email": self.email,
            "password": self.password,
            "returnSecureToken": True,
        }
        async with self.session.post(url, headers=headers, json=data) as resp:
            payload = await self._safe_json(resp)
            if resp.status != 200:
                raise UnauthorizedException(self._format_auth_error(payload, resp.status))
            
            self.tokens = self._normalize_tokens(payload)
            if not all(k in self.tokens for k in ("idToken", "refreshToken", "expiresIn")):
                raise UnauthorizedException("Unexpected token response (missing keys).")

            try:
                expires_in = int(self.tokens["expiresIn"])
            except (TypeError, ValueError):
                raise UnauthorizedException("Unexpected token response (invalid expiry).")

            self.expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expires_in)
            self._update_firestore_client()
            _LOGGER.debug("Authenticated successfully; token expiry set.")

    async def refresh_token(self):
        """Refresh the access token using the refresh token."""
        url = f"{self.token_url}?key={self.api_key}"
        headers = self._build_headers("application/x-www-form-urlencoded; charset=UTF-8")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refreshToken"],
        }
        async with self.session.post(url, headers=headers, data=data) as resp:
            payload = await self._safe_json(resp)
            if resp.status != 200:
                raise UnauthorizedException(self._format_auth_error(payload, resp.status))
            
            new_tokens = self._normalize_tokens(payload)
            self.tokens["idToken"] = new_tokens.get("idToken", self.tokens.get("idToken"))
            if "refreshToken" in new_tokens:
                self.tokens["refreshToken"] = new_tokens["refreshToken"]

            expires_in = new_tokens.get("expiresIn")
            try:
                expires_in_int = int(expires_in)
            except (TypeError, ValueError):
                raise UnauthorizedException("Unexpected refresh response (invalid expiry).")

            self.expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expires_in_int)
            self._update_firestore_client()
            _LOGGER.debug("Token refreshed successfully.")

    def _update_firestore_client(self):
        """Helper to sync credentials to the Firestore client."""
        self.credentials = Credentials(
            token=self.tokens['idToken'],
            refresh_token=self.tokens['refreshToken'],
            token_uri=self.token_url,
            client_id=None,
            client_secret=None
        )
        self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def get_client(self):
        """Get the current client, refreshing if necessary."""
        async with self._lock:
            if self.client is None:
                _LOGGER.debug("Firestore client not initialized, performing authentication.")
                await self.authenticate()

            if self._is_token_expiring():
                await self.refresh_token()
                if self.coordinator:
                    await self.coordinator.refresh_subscription()
            return self.client

    def _is_token_expiring(self) -> bool:
        """Check if token is within 5 minutes of expiring."""
        if not self.expiry:
            return True
        return datetime.datetime.now(datetime.UTC) >= (self.expiry - datetime.timedelta(minutes=5))

    async def start_token_refresh_routine(self, coordinator):
        """Loop to maintain token validity with exponential backoff on error."""
        retry_delay = 10
        while not self.hass.is_stopping:
            try:
                await self.ensure_active_token()
                retry_delay = 10  # Reset delay on success
                sleep_time = self.calculate_sleep_duration()
                await asyncio.sleep(sleep_time)
            except Exception as e:
                _LOGGER.error("Error maintaining token: %s. Retrying in %ss", e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 600)  # Max 10 minute backoff

    def calculate_sleep_duration(self):
        """Determine time until next refresh (5 mins before expiry)."""
        time_to_expiry = (self.expiry - datetime.datetime.now(datetime.UTC)).total_seconds()
        return max(time_to_expiry - 300, 30) 

    async def ensure_active_token(self):
        """Check and refresh token if near expiry."""
        if self._is_token_expiring():
            _LOGGER.debug("Token expiring soon, refreshing...")
            await self.get_client()