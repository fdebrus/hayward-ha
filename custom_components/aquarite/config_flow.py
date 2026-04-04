"""Config Flow for the Aquarite integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from aioaquarite import AquariteAuth, AquariteClient, AuthenticationError

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class AquariteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Aquarite config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_data: dict[str, Any] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._available_pools: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._user_data = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
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

    async def async_step_pool(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the pool selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            pool_id: str = user_input["pool_id"]

            await self.async_set_unique_id(pool_id)
            self._abort_if_unique_id_configured()

            entry_data = {
                CONF_USERNAME: self._user_data[CONF_USERNAME],
                CONF_PASSWORD: self._user_data[CONF_PASSWORD],
                "pool_id": pool_id,
            }
            if self._reauth_entry:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=entry_data
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(
                title=self._available_pools.get(pool_id, pool_id),
                data=entry_data,
            )

        try:
            session = async_get_clientsession(self.hass)
            auth = AquariteAuth(
                session,
                self._user_data[CONF_USERNAME],
                self._user_data[CONF_PASSWORD],
            )
            await auth.authenticate()

            api = AquariteClient(auth)

        except AuthenticationError:
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
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Reauthenticate the user."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of credentials."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                auth = AquariteAuth(
                    session,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "auth_error"
            else:
                new_data = {
                    **reconfigure_entry.data,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                self.hass.config_entries.async_update_entry(
                    reconfigure_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(
                    reconfigure_entry.entry_id
                )
                return self.async_abort(reason="reconfigure_successful")

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=reconfigure_entry.data.get(CONF_USERNAME, ""),
                ): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
