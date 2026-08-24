"""The Aquarite integration."""

from __future__ import annotations

from dataclasses import dataclass

from aioaquarite import AquariteAuth, AquariteClient, AquariteError, AuthenticationError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_PERIOD, ATTR_POOL_ID, ATTR_TYPE, DEFAULT_STATS_PERIOD, DOMAIN
from .coordinator import AquariteDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


@dataclass
class AquariteRuntimeData:
    """Runtime data for the Aquarite integration."""

    coordinator: AquariteDataUpdateCoordinator
    auth: AquariteAuth


AquariteConfigEntry = ConfigEntry[AquariteRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up Aquarite from a config entry."""
    user_config = entry.data
    session = async_get_clientsession(hass)
    pool_id: str = user_config["pool_id"]

    auth = AquariteAuth(
        session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD]
    )
    try:
        await auth.authenticate()
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from exc
    except AquariteError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(exc)},
        ) from exc

    api = AquariteClient(auth)

    coordinator = AquariteDataUpdateCoordinator(hass, entry, auth, api, pool_id)

    # Initial data fetch (raises ConfigEntryNotReady itself on failure)
    # and the self-supervising Firestore subscription.
    await coordinator.async_config_entry_first_refresh()
    try:
        await coordinator.subscribe()
    except AquariteError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(exc)},
        ) from exc

    entry.runtime_data = AquariteRuntimeData(
        coordinator=coordinator,
        auth=auth,
    )

    # The health-check interval option is read when the subscription starts,
    # so an options change needs a reload to take effect.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_sync_time(call: ServiceCall) -> None:
        """Service call to sync pool time for all loaded entries."""
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if config_entry.state is ConfigEntryState.LOADED:
                await config_entry.runtime_data.coordinator.set_pool_time_to_now()

    if not hass.services.has_service(DOMAIN, "sync_pool_time"):
        hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

    async def handle_get_pool_stats(call: ServiceCall) -> ServiceResponse:
        """Service call to fetch a historical sample series for a pool."""
        requested_pool_id = call.data[ATTR_POOL_ID]
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if (
                config_entry.state is ConfigEntryState.LOADED
                and config_entry.runtime_data.coordinator.pool_id
                == requested_pool_id
            ):
                api = config_entry.runtime_data.coordinator.api
                try:
                    series = await api.get_pool_stats(
                        requested_pool_id,
                        call.data[ATTR_TYPE],
                        call.data.get(ATTR_PERIOD, DEFAULT_STATS_PERIOD),
                    )
                except AquariteError as exc:
                    raise HomeAssistantError(
                        f"Failed to fetch pool stats: {exc}"
                    ) from exc
                return {"series": series}
        raise ServiceValidationError(
            f"No loaded Aquarite entry found for pool_id '{requested_pool_id}'"
        )

    if not hass.services.has_service(DOMAIN, "get_pool_stats"):
        hass.services.async_register(
            DOMAIN,
            "get_pool_stats",
            handle_get_pool_stats,
            supports_response=SupportsResponse.ONLY,
        )

    def _maybe_remove_services() -> None:
        """Remove integration-wide services if this is the last loaded entry."""
        remaining = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
            and e.state is ConfigEntryState.LOADED
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, "sync_pool_time")
            hass.services.async_remove(DOMAIN, "get_pool_stats")

    entry.async_on_unload(_maybe_remove_services)

    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: AquariteConfigEntry
) -> None:
    """Reload the entry so a changed health-check interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: AquariteConfigEntry
) -> bool:
    """Unload Aquarite config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        await entry.runtime_data.coordinator.async_shutdown()

    return unloaded
