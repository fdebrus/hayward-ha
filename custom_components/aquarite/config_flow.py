"""Config Flow for Aquarite integration."""

from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

from pyaquarite import AquariteAuth, AquariteAPI

AUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


class AquariteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Aquarite config flow."""

    data: Optional[dict[str, Any]]

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        errors = {}
        if user_input is not None:
            self.data = user_input
            return await self.async_step_pool()
        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_pool(self, user_input: Optional[dict[str, Any]] = None):
        errors = {}
        if user_input is not None:
            self.data["pool_id"] = user_input["pool_id"]
            return await self.async_create_entry(
                title=self.data["pools"][self.data["pool_id"]], data=self.data
            )

        try:
            api_key = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"
            auth = AquariteAuth(
                self.data[CONF_USERNAME],
                self.data[CONF_PASSWORD],
                api_key=api_key,
            )
            await auth.authenticate()
            api = AquariteAPI(auth)
            pools = await api.get_pools()
            self.data["pools"] = pools
        except Exception:
            errors["base"] = "auth_error"
            return self.async_show_form(
                step_id="user", data_schema=AUTH_SCHEMA, errors=errors
            )

        POOL_SCHEMA = vol.Schema({vol.Required("pool_id"): vol.In(self.data["pools"])})

        return self.async_show_form(
            step_id="pool", data_schema=POOL_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        return await self.async_step_user()

    async def async_create_entry(self, title: str, data: dict) -> dict:
        return super().async_create_entry(title=title, data=data)
