"""Async API client for the Hayward Aquarite pool system."""

import asyncio
import json
import logging
from copy import deepcopy
from typing import Any, Callable, MutableMapping

import aiohttp

from .auth import AquariteAuth
from .const import HAYWARD_REST_API
from .exceptions import CommandError

_LOGGER = logging.getLogger(__name__)


class AquariteClient:
    """Aquarite API client for interacting with the Hayward cloud."""

    def __init__(self, auth: AquariteAuth) -> None:
        self._auth = auth
        self._pool_data: dict[str, dict] = {}

    @property
    def auth(self) -> AquariteAuth:
        """Return the auth handler."""
        return self._auth

    def set_pool_data(self, pool_id: str, data: dict) -> None:
        """Store current pool data (used for building command payloads)."""
        self._pool_data[pool_id] = data

    def get_pool_data(self, pool_id: str) -> dict | None:
        """Return stored pool data."""
        return self._pool_data.get(pool_id)

    async def get_pools(self) -> dict[str, str]:
        """Fetch all pools for the authenticated user.

        Returns a mapping of pool_id -> pool_name.
        """
        client, _ = await self._auth.get_client()
        user_doc = await asyncio.to_thread(
            client.collection("users")
            .document(self._auth.tokens["localId"])
            .get
        )
        user_dict = user_doc.to_dict() or {}

        pools: dict[str, str] = {}
        for pool_id in user_dict.get("pools", []):
            pool_doc = await asyncio.to_thread(
                client.collection("pools").document(pool_id).get
            )
            pool_dict = pool_doc.to_dict()
            if pool_dict:
                name = pool_dict.get("form", {}).get("name", "Unknown")
                if "names" in pool_dict.get("form", {}) and pool_dict["form"]["names"]:
                    name = pool_dict["form"]["names"][0].get("name", name)
                pools[pool_id] = name
        return pools

    async def fetch_pool_data(self, pool_id: str) -> dict:
        """Fetch the full pool document from Firestore."""
        client, _ = await self._auth.get_client()
        pool_doc = await asyncio.to_thread(
            client.collection("pools").document(pool_id).get
        )
        data = pool_doc.to_dict() or {}
        self._pool_data[pool_id] = data
        return data

    async def subscribe_pool(
        self, pool_id: str, callback: Callable[[dict], None]
    ) -> Any:
        """Subscribe to real-time Firestore updates for a pool.

        Args:
            pool_id: The pool document ID.
            callback: Called with the pool data dict on each snapshot.

        Returns:
            A watch object; call ``unsubscribe()`` on it to stop listening.
        """
        client, _ = await self._auth.get_client()
        doc_ref = client.collection("pools").document(pool_id)

        def on_snapshot(doc_snapshot, changes, read_time):
            for doc in doc_snapshot:
                data = doc.to_dict()
                self._pool_data[pool_id] = data
                callback(data)

        watch = await asyncio.to_thread(doc_ref.on_snapshot, on_snapshot)
        _LOGGER.debug("Firestore subscription active for %s", pool_id)
        return watch

    async def send_command(self, data: dict[str, Any]) -> None:
        """Send a command to the Hayward cloud REST API."""
        client, _ = await self._auth.get_client()
        headers = {"Authorization": f"Bearer {self._auth.tokens['idToken']}"}

        async with self._auth._session.post(
            f"{HAYWARD_REST_API}/sendPoolCommand",
            json=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            _LOGGER.debug("Command sent. Status: %s", response.status)
            if response.status >= 400:
                raise CommandError(
                    f"Command failed with status {response.status}"
                )

    async def set_value(
        self, pool_id: str, value_path: str, value: Any
    ) -> None:
        """Set a value on the pool device via REST API.

        Uses stored pool data to build the minimal change payload.
        """
        pool_data = self._pool_data.get(pool_id)
        if not pool_data:
            raise RuntimeError("Pool data not available; fetch data first.")

        current_config = self._extract_branch(pool_data, value_path)
        _LOGGER.debug(
            "set_value BEFORE: path=%s current_data=%s",
            value_path,
            json.dumps(current_config, indent=2, default=str),
        )
        self._set_in_dict(current_config, value_path, value)

        if value_path == "hidro.cloration_enabled":
            hidro = current_config.get("hidro", {})
            hidro.update(
                {
                    "cloration_enabled": 1 if value else 0,
                    "reduction": 1 if value else 0,
                    "disable": 1,
                }
            )

        payload = {
            "gateway": pool_data.get("wifi"),
            "poolId": pool_id,
            "operation": "WRP",
            "changes": json.dumps(current_config),
            "source": "web",
        }
        _LOGGER.debug(
            "set_value path=%s value=%s changes=%s",
            value_path,
            value,
            json.dumps(current_config, indent=2),
        )
        await self.send_command(payload)

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _set_in_dict(
        data_dict: MutableMapping[str, Any], path: str, value: Any
    ) -> None:
        """Set a value in a nested dict using dot-notation path."""
        keys = path.split(".")
        for key in keys[:-1]:
            data_dict = data_dict.setdefault(key, {})
        data_dict[keys[-1]] = value

    @staticmethod
    def _extract_branch(
        data: MutableMapping[str, Any], path: str
    ) -> dict[str, Any]:
        """Deep-clone the relevant branch of the data structure.

        For deep paths (4+ segments, e.g. relays.relay1.info.onoff),
        extract only 2 levels deep to send just the target branch.
        """
        keys = path.split(".")
        root_key = keys[0]
        if len(keys) >= 4:
            second_key = keys[1]
            root_data = data.get(root_key, {})
            return {root_key: {second_key: deepcopy(root_data.get(second_key, {}))}}
        return {root_key: deepcopy(data.get(root_key, {}))}

    @staticmethod
    def get_value(data: dict, path: str, default: Any = None) -> Any:
        """Get a nested value from pool data using dot-notation path."""
        if not data:
            return default
        keys = path.split(".")
        val = data
        try:
            for key in keys:
                val = val[key]
            return val if val is not None else default
        except (KeyError, TypeError):
            return default
