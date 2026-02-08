"""Config Flow."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .application_credentials import IdentityToolkitAuth, UnauthorizedException
from .aquarite import Aquarite
from .const import CONF_ORIGIN, CONF_REFERER, DOMAIN

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_REFERER): cv.string,
        vol.Optional(CONF_ORIGIN): cv.string,
    }
)


class AquariteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Aquarite config flow."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._available_pools: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            if user_input.get(CONF_REFERER):
                self.data[CONF_REFERER] = user_input[CONF_REFERER]
            if user_input.get(CONF_ORIGIN):
                self.data[CONF_ORIGIN] = user_input[CONF_ORIGIN]
            return await self.async_step_pool()

        schema = AUTH_SCHEMA
        if self._reauth_entry:
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=self._reauth_entry.data.get(CONF_USERNAME, ""),
                    ): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_pool(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the pool selection step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            pool_id: str = user_input["pool_id"]
            entry_data = {
                CONF_USERNAME: self.data[CONF_USERNAME],
                CONF_PASSWORD: self.data[CONF_PASSWORD],
                "pool_id": pool_id,
            }
            if self.data.get(CONF_REFERER):
                entry_data[CONF_REFERER] = self.data[CONF_REFERER]
            if self.data.get(CONF_ORIGIN):
                entry_data[CONF_ORIGIN] = self.data[CONF_ORIGIN]

            if self._reauth_entry:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=entry_data
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

            await self.async_set_unique_id(pool_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._available_pools.get(pool_id, pool_id),
                data=entry_data,
            )

        try:
            auth = IdentityToolkitAuth(
                self.hass,
                self.data[CONF_USERNAME],
                self.data[CONF_PASSWORD],
                self.data.get(CONF_REFERER),
                self.data.get(CONF_ORIGIN),
            )
            await auth.authenticate()

            api = Aquarite(auth, self.hass, async_get_clientsession(self.hass))

        except UnauthorizedException:
            errors["base"] = "auth_error"
            return self.async_show_form(
                step_id="user", data_schema=AUTH_SCHEMA, errors=errors
            )

        self._available_pools = await api.get_pools()
        pool_schema = vol.Schema(
            {vol.Required("pool_id"): vol.In(self._available_pools)}
        )

        return self.async_show_form(
            step_id="pool", data_schema=pool_schema, errors=errors
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reauthenticate the user."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        return await self.async_step_user(user_input)
