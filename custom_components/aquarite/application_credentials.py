from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Awaitable, Callable, Optional

from google.auth.credentials import Credentials
from google.cloud.firestore_v1 import Client as FirestoreClient

from homeassistant.components.application_credentials import (
    ApplicationCredentials,
    ClientCredential,
    async_get_client_credential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.async_ import run_callback_threadsafe

from .const import API_KEY, BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class UnauthorizedException(Exception):
    """Exception raised for unauthorized access."""


class AquariteApplicationCredentials(ApplicationCredentials):
    """Application credentials registration for Aquarite."""

    def __init__(self) -> None:
        super().__init__(DOMAIN)

    async def async_get_default_client_credential(self) -> ClientCredential | None:
        """Provide the built-in API key as a default credential."""

        return ClientCredential(API_KEY, "")

    async def async_get_description(self) -> str:
        """Explain how to provision credentials for Aquarite."""

        return (
            "Use your Hayward Identity Toolkit API key. Home Assistant will store "
            "it securely and reuse it for token refreshes."
        )


async def async_get_api_key(hass: HomeAssistant) -> str:
    """Return the stored API key or register the built-in default."""

    client_credential = await async_get_client_credential(hass, DOMAIN)
    if client_credential:
        return client_credential.client_id

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(API_KEY, "")
    )
    return API_KEY


class RefreshHandlerCredentials(Credentials):
    """Credentials wrapper that refreshes via a supplied coroutine."""

    def __init__(
        self,
        hass: HomeAssistant,
        token: str,
        expiry: datetime.datetime,
        refresh_coroutine: Callable[[], Awaitable[tuple[str, datetime.datetime]]],
    ) -> None:
        super().__init__()
        self.hass = hass
        self.token = token
        self.expiry = expiry
        self._refresh_coroutine = refresh_coroutine

    @property
    def valid(self) -> bool:
        """Return True if the credential has a non-expired token."""

        return self.token is not None and not self.expired

    @property
    def expired(self) -> bool:
        """Return True if the credential is expired."""

        return self.expiry is None or datetime.datetime.now() >= self.expiry

    @property
    def requires_scopes(self) -> bool:
        """Identity Toolkit tokens do not require scopes."""

        return False

    def with_quota_project(self, quota_project_id: str) -> Credentials:
        """Return credentials unchanged as quota projects are unused."""

        return self

    def refresh(self, request) -> None:
        """Refresh the token using the provided async coroutine on HA's loop."""

        future = run_callback_threadsafe(
            self.hass.loop, self._refresh_coroutine()
        )
        try:
            token, expiry = future.result()
        except Exception as err:  # pragma: no cover - invoked by google-auth
            _LOGGER.error("Failed to refresh token: %s", err)
            raise

        self.token = token
        self.expiry = expiry


class IdentityToolkitAuth:
    """Handle Identity Toolkit authentication with HA-managed refresh."""

    def __init__(self, hass: HomeAssistant, email: str, password: str, api_key: str):
        self.api_key = api_key
        self.hass = hass
        self.email = email
        self.password = password
        self.base_url = BASE_URL
        self.tokens: Optional[dict[str, Any]] = None
        self.expiry: Optional[datetime.datetime] = None
        self.credentials: Optional[Credentials] = None
        self.client: Optional[FirestoreClient] = None
        self.session = async_get_clientsession(hass)
        self.coordinator = None

    def set_coordinator(self, coordinator) -> None:
        """Attach the coordinator to allow token refresh callbacks."""

        self.coordinator = coordinator

    async def authenticate(self) -> dict[str, Any]:
        await self.signin()
        assert self.tokens
        return {
            "idToken": self.tokens["idToken"],
            "refreshToken": self.tokens["refreshToken"],
            "expiresIn": self.tokens["expiresIn"],
        }

    async def signin(self) -> None:
        """Sign in and set the tokens and expiry."""

        payload = await self._post_auth_request()
        self._set_tokens_and_credentials(payload)

    def _calculate_expiry(self, expires_in: str) -> datetime.datetime:
        """Convert expiresIn value to an absolute expiry datetime."""

        return datetime.datetime.now() + datetime.timedelta(seconds=int(expires_in))

    def _initialize_credentials(self) -> None:
        """Create credentials and a Firestore client with refresh support."""

        assert self.tokens
        assert self.expiry
        self.credentials = RefreshHandlerCredentials(
            hass=self.hass,
            token=self.tokens["idToken"],
            expiry=self.expiry,
            refresh_coroutine=self._async_fetch_tokens,
        )
        _LOGGER.debug("Initialized credentials with expiry %s", self.expiry)
        self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def _post_auth_request(self) -> dict[str, Any]:
        """Post credentials to the Identity Toolkit endpoint and return payload."""

        url = f"{self.base_url}:signInWithPassword?key={self.api_key}"
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps(
            {
                "email": self.email,
                "password": self.password,
                "returnSecureToken": True,
            }
        )

        async with self.session.post(url, headers=headers, data=data) as resp:
            if resp.status == 400:
                raise UnauthorizedException("Failed to authenticate.")
            if resp.status >= 500:
                raise UnauthorizedException("Identity Toolkit service unavailable.")
            return await resp.json()

    def _set_tokens_and_credentials(self, payload: dict[str, Any]) -> None:
        """Update tokens, expiry, and derived credentials."""

        self.tokens = payload
        self.expiry = self._calculate_expiry(self.tokens["expiresIn"])
        self._initialize_credentials()

    async def _async_fetch_tokens(self) -> tuple[str, datetime.datetime]:
        """Fetch a fresh token pair using the HA-managed HTTP session."""

        payload = await self._post_auth_request()
        self.tokens = payload
        self.expiry = self._calculate_expiry(self.tokens["expiresIn"])
        return self.tokens["idToken"], self.expiry

    async def refresh_token(self) -> None:
        """Refresh the access token by re-authenticating."""

        await self._async_fetch_tokens()
        self._initialize_credentials()

    async def get_client(self) -> FirestoreClient:
        """Get the current client, refreshing if necessary."""

        if self.client is None:
            _LOGGER.debug("Firestore client not initialized, performing authentication.")
            await self.authenticate()

        if self.expiry is None:
            _LOGGER.debug("No expiry set, refreshing token.")
            await self.refresh_token()
        elif datetime.datetime.now() >= (self.expiry - datetime.timedelta(minutes=5)):
            await self.refresh_token()
            if self.coordinator:
                await self.coordinator.refresh_subscription()

        assert self.client
        return self.client

    async def start_token_refresh_routine(self, coordinator) -> None:
        """Periodically refresh the token ahead of expiry."""

        self.set_coordinator(coordinator)
        await self.get_client()

        while not self.hass.is_stopping:
            try:
                await self.ensure_active_token()
                await asyncio.sleep(self.calculate_sleep_duration())
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.error("Error maintaining token: %s", err)
                break

    def calculate_sleep_duration(self) -> int:
        """Determine how long to wait before the next refresh check."""

        if not self.expiry:
            return 10
        time_to_expiry = (self.expiry - datetime.datetime.now()).total_seconds()
        return max(int(time_to_expiry) - 300, 10)  # Refresh 5 minutes before expiry

    async def ensure_active_token(self) -> None:
        """Ensure that the token is still valid, and refresh it if necessary."""

        if not self.expiry or datetime.datetime.now() >= (self.expiry - datetime.timedelta(minutes=5)):
            _LOGGER.debug("Token expired or missing, refreshing...")
            await self.get_client()
