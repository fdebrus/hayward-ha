"""Config Flow."""

from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .application_credentials import IdentityToolkitAuth, UnauthorizedException
from .aquarite import Aquarite

AUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

class AquariteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Aquarite config flow."""

    data: Optional[dict[str, Any]]

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self.data = user_input
            return await self.async_step_pool()

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_pool(self, user_input: Optional[dict[str, Any]] = None):
        """Handle the pool selection step."""
        errors = {}
        if user_input is not None:
            self.data["pool_id"] = user_input["pool_id"]
            # Store the pool name in config entry data
            pool_name = self.data['pools'][self.data["pool_id"]]
            await self.async_set_unique_id(f"{self.data[CONF_USERNAME]}_{self.data['pool_id']}")
            return self.async_create_entry(
                title=pool_name,
                data={
                    **self.data,
                    "pool_name": pool_name,
                }
            )

        try:
            auth = IdentityToolkitAuth(self.hass, self.data[CONF_USERNAME], self.data[CONF_PASSWORD])
            await auth.authenticate()
            api = Aquarite(auth, self.hass, async_get_clientsession(self.hass))
            self.data['pools'] = await api.get_pools()
            if not self.data['pools']:
                errors["base"] = "no_pools_found"
        except UnauthorizedException:
            errors["base"] = "auth_error"
        except Exception:
            errors["base"] = "unknown_error"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=AUTH_SCHEMA, errors=errors
            )

        POOL_SCHEMA = vol.Schema({
            vol.Required("pool_id"): vol.In(self.data['pools'])
        })

        return self.async_show_form(
            step_id="pool", data_schema=POOL_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Reauthenticate the user."""
        self.data = None  # reset for fresh auth
        return await self.async_step_user()
