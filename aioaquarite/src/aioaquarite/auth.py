"""Authentication for the Hayward Aquarite API via Google Identity Toolkit."""

import asyncio
import datetime
import logging
from urllib.parse import urlparse

import aiohttp
from google.cloud.firestore_v1 import Client as FirestoreClient
from google.oauth2.credentials import Credentials

from .const import (
    API_KEY,
    API_REFERRER,
    FIRESTORE_PROJECT,
    IDENTITY_TOOLKIT_BASE,
    SECURETOKEN_URL,
    TOKEN_REFRESH_BUFFER,
)
from .exceptions import AuthenticationError

_LOGGER = logging.getLogger(__name__)


class AquariteAuth:
    """Handle authentication with the Hayward Aquarite cloud service."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._api_key = API_KEY
        self._base_url = IDENTITY_TOOLKIT_BASE
        self._token_url = SECURETOKEN_URL
        self.tokens: dict | None = None
        self.expiry: datetime.datetime | None = None
        self._credentials: Credentials | None = None
        self._client: FirestoreClient | None = None
        self._lock = asyncio.Lock()

    async def authenticate(self) -> dict:
        """Sign in and return token information."""
        await self._signin()
        return {
            "idToken": self.tokens["idToken"],
            "refreshToken": self.tokens["refreshToken"],
            "expiresIn": self.tokens["expiresIn"],
        }

    async def _signin(self) -> None:
        """Sign in with email/password via Identity Toolkit."""
        url = f"{self._base_url}:signInWithPassword?key={self._api_key}"
        headers = self._build_headers("application/json; charset=UTF-8")
        data = {
            "email": self._email,
            "password": self._password,
            "returnSecureToken": True,
        }
        async with self._session.post(url, headers=headers, json=data) as resp:
            payload = await self._safe_json(resp)
            if resp.status != 200:
                raise AuthenticationError(self._format_auth_error(payload, resp.status))

            self.tokens = self._normalize_tokens(payload)
            if not all(k in self.tokens for k in ("idToken", "refreshToken", "expiresIn")):
                raise AuthenticationError("Unexpected token response (missing keys).")

            try:
                expires_in = int(self.tokens["expiresIn"])
            except (TypeError, ValueError) as exc:
                raise AuthenticationError(
                    "Unexpected token response (invalid expiry)."
                ) from exc

            self.expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                seconds=expires_in
            )
            self._update_firestore_client()
            _LOGGER.debug("Authenticated successfully; token expiry set.")

    async def refresh_token(self) -> None:
        """Refresh the access token using the refresh token."""
        url = f"{self._token_url}?key={self._api_key}"
        headers = self._build_headers(
            "application/x-www-form-urlencoded; charset=UTF-8"
        )
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refreshToken"],
        }
        async with self._session.post(url, headers=headers, data=data) as resp:
            payload = await self._safe_json(resp)
            if resp.status != 200:
                raise AuthenticationError(self._format_auth_error(payload, resp.status))

            new_tokens = self._normalize_tokens(payload)
            self.tokens["idToken"] = new_tokens.get(
                "idToken", self.tokens.get("idToken")
            )
            if "refreshToken" in new_tokens:
                self.tokens["refreshToken"] = new_tokens["refreshToken"]

            expires_in = new_tokens.get("expiresIn")
            try:
                expires_in_int = int(expires_in)
            except (TypeError, ValueError) as exc:
                raise AuthenticationError(
                    "Unexpected refresh response (invalid expiry)."
                ) from exc

            self.expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                seconds=expires_in_int
            )
            self._update_firestore_client()
            _LOGGER.debug("Token refreshed successfully.")

    def _update_firestore_client(self) -> None:
        """Sync credentials to the Firestore client."""
        if self._client is not None:
            self._client.close()
        self._credentials = Credentials(
            token=self.tokens["idToken"],
            refresh_token=self.tokens["refreshToken"],
            token_uri=self._token_url,
            client_id=None,
            client_secret=None,
        )
        self._client = FirestoreClient(
            project=FIRESTORE_PROJECT, credentials=self._credentials
        )

    async def get_client(self) -> FirestoreClient:
        """Get the Firestore client, refreshing the token if needed.

        Returns the Firestore client and a boolean indicating whether
        a token refresh occurred (so the caller can resubscribe).
        """
        token_refreshed = False

        async with self._lock:
            if self._client is None:
                _LOGGER.debug(
                    "Firestore client not initialized, performing authentication."
                )
                await self.authenticate()

            if self.is_token_expiring():
                await self.refresh_token()
                token_refreshed = True

        return self._client, token_refreshed

    def is_token_expiring(self) -> bool:
        """Check if the token is within the refresh buffer of expiring."""
        if not self.expiry:
            return True
        return datetime.datetime.now(datetime.UTC) >= (
            self.expiry - datetime.timedelta(seconds=TOKEN_REFRESH_BUFFER)
        )

    def calculate_sleep_duration(self) -> float:
        """Determine seconds until next refresh check."""
        time_to_expiry = (
            self.expiry - datetime.datetime.now(datetime.UTC)
        ).total_seconds()
        return max(time_to_expiry - TOKEN_REFRESH_BUFFER, 30)

    # ── helpers ──────────────────────────────────────────────

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
    async def _safe_json(resp: aiohttp.ClientResponse) -> dict:
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
            "localId": ["local_id", "user_id"],
        }
        for target, aliases in mapping.items():
            if target not in normalized:
                for alias in aliases:
                    if alias in normalized:
                        normalized[target] = normalized[alias]
                        break
        return normalized
