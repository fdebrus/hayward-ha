"""Config Flow for the Aquarite integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from aioaquarite import AquariteAuth, AquariteClient, AquariteError, AuthenticationError

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

PASSWORD_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): cv.string})


class AquariteOptionsFlow(OptionsFlow):
    """Options flow for Aquarite."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HEALTH_CHECK_INTERVAL, default=current
                ): vol.All(int, vol.Range(min=60, max=3600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class AquariteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Aquarite config flow (one entry per Hayward account)."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AquariteOptionsFlow:
        """Return the options flow handler."""
        return AquariteOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            auth = AquariteAuth(session, username, password)
            try:
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "auth_error"
            except AquariteError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown_error"
            else:
                await self.async_set_unique_id(username.lower())
                self._abort_if_unique_id_configured()

                api = AquariteClient(auth)
                try:
                    pools = await api.get_pools()
                except AquariteError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error fetching pools")
                    errors["base"] = "unknown_error"
                else:
                    if not pools:
                        errors["base"] = "no_pools_found"
                    else:
                        return self.async_create_entry(
                            title=username,
                            data={
                                CONF_USERNAME: username,
                                CONF_PASSWORD: password,
                            },
                        )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth flow when stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password and validate against the same account."""
        return await self._async_update_password(
            self._get_reauth_entry(), "reauth_confirm", user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user proactively update the stored password."""
        return await self._async_update_password(
            self._get_reconfigure_entry(), "reconfigure", user_input
        )

    async def _async_update_password(
        self,
        entry: ConfigEntry,
        step_id: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Shared password-update handler for reauth and reconfigure.

        The username identifies the account (it is the entry's unique_id),
        so only the password can change here; switching accounts means
        removing the entry and adding a new one.
        """
        errors: dict[str, str] = {}
        username = entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            session = async_get_clientsession(self.hass)
            auth = AquariteAuth(session, username, password)
            try:
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "auth_error"
            except AquariteError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during credential update")
                errors["base"] = "unknown_error"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=PASSWORD_SCHEMA,
            description_placeholders={"username": username},
            errors=errors,
        )
