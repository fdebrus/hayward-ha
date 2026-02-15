import asyncio
import json
import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, MutableMapping, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from .const import HAYWARD_REST_API

if TYPE_CHECKING:
    from .coordinator import AquariteDataUpdateCoordinator
    from .application_credentials import IdentityToolkitAuth

_LOGGER = logging.getLogger(__name__)

class Aquarite:
    """Aquarite API client."""

    def __init__(self, auth: "IdentityToolkitAuth", hass: HomeAssistant, aiohttp_session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self.auth = auth
        self.hass = hass
        self.aiohttp_session = aiohttp_session
        self.coordinator: Optional["AquariteDataUpdateCoordinator"] = None

    def set_coordinator(self, coordinator: "AquariteDataUpdateCoordinator") -> None:
        """Attach the coordinator for data lookups."""
        self.coordinator = coordinator

    async def get_pools(self) -> Dict[str, str]:
        """Fetch list of pools with optimized thread handling."""
        data: Dict[str, str] = {}
        client = await self.auth.get_client()
        
        user_doc = await asyncio.to_thread(client.collection("users").document(self.auth.tokens["localId"]).get)
        user_dict = user_doc.to_dict() or {}
        
        for pool_id in user_dict.get("pools", []):
            pool_doc = await asyncio.to_thread(client.collection("pools").document(pool_id).get)
            pool_dict = pool_doc.to_dict()
            if pool_dict:
                name = pool_dict.get("form", {}).get("name", "Unknown")
                if "names" in pool_dict.get("form", {}) and pool_dict["form"]["names"]:
                    name = pool_dict["form"]["names"][0].get("name", name)
                data[pool_id] = name
        return data

    async def fetch_pool_data(self, pool_id: str) -> dict:
        """Fetch document directly from Firestore."""
        client = await self.auth.get_client()
        pool_doc = await asyncio.to_thread(client.collection("pools").document(pool_id).get)
        return pool_doc.to_dict() or {}

    async def send_command(self, data: Dict[str, Any]) -> None:
        """Sends command using current idToken."""
        await self.auth.get_client()
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        
        async with self.aiohttp_session.post(
            f"{HAYWARD_REST_API}/sendPoolCommand",
            json=data,
            headers=headers,
            timeout=10
        ) as response:
            _LOGGER.debug("Command sent. Status: %s", response.status)
            response.raise_for_status()

    async def set_value(self, pool_id: str, value_path: str, value: Any) -> None:
        """Set value in Firestore via REST API."""
        if not self.coordinator or not self.coordinator.data:
            raise RuntimeError("Coordinator data not available")

        current_config = self.extract_complete_info(self.coordinator.data, value_path)
        self.set_in_dict(current_config, value_path, value)

        if value_path == "hidro.cloration_enabled":
            hidro = current_config.get("hidro", {})
            hidro.update({
                "cloration_enabled": 1 if value else 0,
                "reduction": 1 if value else 0,
                "disable": 1
            })

        payload = {
            "gateway": self.coordinator.data.get("wifi"),
            "poolId": pool_id,
            "operation": "WRP",
            "changes": json.dumps(current_config),
            "source": "web"
        }
        await self.send_command(payload)

    def set_in_dict(self, data_dict: MutableMapping[str, Any], path: str, value: Any) -> None:
        """Utility to set nested dictionary value."""
        keys = path.split(".")
        for key in keys[:-1]:
            data_dict = data_dict.setdefault(key, {})
        data_dict[keys[-1]] = value

    def extract_complete_info(self, data: MutableMapping[str, Any], path: str) -> Dict[str, Any]:
        """Deeply clones a branch of the data structure."""
        keys = path.split(".")
        root_key = keys[0]
        return {root_key: deepcopy(data.get(root_key, {}))}