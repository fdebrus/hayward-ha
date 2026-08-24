"""The Aquarite integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from aioaquarite import (
    AquariteAuth,
    AquariteClient,
    AquariteError,
    AuthenticationError,
    ResilientUserPoolsSubscription,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_PERIOD,
    ATTR_POOL_ID,
    ATTR_TYPE,
    DEFAULT_STATS_PERIOD,
    DOMAIN,
    SIGNAL_NEW_POOL,
)
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

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
    """Runtime data for an Aquarite account (one coordinator per pool)."""

    auth: AquariteAuth
    api: AquariteClient
    coordinators: dict[str, AquariteDataUpdateCoordinator] = field(
        default_factory=dict
    )
    sync_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


AquariteConfigEntry = ConfigEntry[AquariteRuntimeData]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a v1 (one entry per pool) entry to v2 (one entry per account).

    v1 entries carried a pool_id and used it as the unique_id; v2 entries
    hold only the account credentials, discover every pool at setup, and
    use the lowercased username as the unique_id. Several v1 entries for
    the same account all migrate to identical v2 entries; setup then keeps
    one and removes the duplicates (entity unique_ids are pool_id-based
    and unchanged, so the registry restores entity IDs and customizations
    under the surviving entry).
    """
    if entry.version > 2:
        # Downgrade from a future version: give up rather than guess.
        return False

    if entry.version == 1:
        username: str = entry.data[CONF_USERNAME]
        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        }
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=2,
            unique_id=username.lower(),
            title=username,
        )
        _LOGGER.info(
            "Migrated Aquarite entry %s to the account-level format", entry.entry_id
        )

    return True


def _find_duplicate_winner(
    hass: HomeAssistant, entry: AquariteConfigEntry
) -> AquariteConfigEntry | None:
    """Return the surviving entry if this one duplicates another account entry.

    Among entries sharing a unique_id (several migrated v1 entries of one
    account), the one with the lowest entry_id deterministically wins.
    """
    if entry.unique_id is None:
        return None
    return next(
        (
            other
            for other in hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
            and other.unique_id == entry.unique_id
            and other.entry_id < entry.entry_id
        ),
        None,
    )


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up an Aquarite account from a config entry.

    One config entry represents a Hayward account; every pool on the
    account is exposed as a device with its own coordinator.
    """
    if (winner := _find_duplicate_winner(hass, entry)) is not None:
        _LOGGER.info(
            "Removing duplicate Aquarite entry %s for account %s (kept by %s)",
            entry.entry_id,
            entry.unique_id,
            winner.entry_id,
        )
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="duplicate_account",
        )

    session = async_get_clientsession(hass)
    auth = AquariteAuth(
        session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
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
    try:
        pools = await api.get_pools()
    except AquariteError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(exc)},
        ) from exc

    if not pools:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_pools",
        )

    data = AquariteRuntimeData(auth=auth, api=api)
    entry.runtime_data = data

    try:
        for pool_id, pool_name in pools.items():
            await _async_add_coordinator(hass, entry, pool_id, pool_name, first=True)
    except Exception:
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()
        raise

    # Catch pools removed from the account while Home Assistant was offline;
    # the first live snapshot is a no-op so it wouldn't clean these up.
    _async_remove_stale_devices(hass, entry, set(pools))

    def _on_user_pools_snapshot(pool_ids: list[str]) -> None:
        """Bridge the Firestore snapshot from the watch thread to the HA loop."""
        hass.loop.call_soon_threadsafe(_schedule_reconcile, pool_ids)

    @callback
    def _schedule_reconcile(pool_ids: list[str]) -> None:
        entry.async_create_background_task(
            hass,
            _async_reconcile_pools(hass, entry, pool_ids),
            name=f"aquarite_reconcile_{entry.entry_id}",
        )

    # Subscribe before forwarding platforms so a failed subscribe doesn't
    # leave platforms set up; on retry they would re-forward and raise
    # "already setup".
    try:
        subscription: ResilientUserPoolsSubscription = (
            await api.subscribe_user_pools_resilient(_on_user_pools_snapshot)
        )
    except AquariteError as exc:
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(exc)},
        ) from exc
    entry.async_on_unload(subscription.aclose)

    # The health-check interval option is read when subscriptions start,
    # so an options change needs a reload to take effect.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_sync_time(call: ServiceCall) -> None:
        """Service call to sync pool time for all pools of all loaded entries."""
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if config_entry.state is ConfigEntryState.LOADED:
                for coordinator in config_entry.runtime_data.coordinators.values():
                    await coordinator.set_pool_time_to_now()

    if not hass.services.has_service(DOMAIN, "sync_pool_time"):
        hass.services.async_register(DOMAIN, "sync_pool_time", handle_sync_time)

    async def handle_get_pool_stats(call: ServiceCall) -> ServiceResponse:
        """Service call to fetch a historical sample series for a pool."""
        requested_pool_id = call.data[ATTR_POOL_ID]
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if config_entry.state is not ConfigEntryState.LOADED:
                continue
            coordinator = config_entry.runtime_data.coordinators.get(
                requested_pool_id
            )
            if coordinator is None:
                continue
            try:
                series = await coordinator.api.get_pool_stats(
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
        # Hold sync_lock so a reconcile background task can't mutate the
        # coordinators dict while we shut it down.
        async with entry.runtime_data.sync_lock:
            for coordinator in entry.runtime_data.coordinators.values():
                await coordinator.async_shutdown()

    return unloaded


@callback
def _async_remove_stale_devices(
    hass: HomeAssistant, entry: AquariteConfigEntry, valid_pool_ids: set[str]
) -> None:
    """Remove registry devices for pools no longer present on the account."""
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        pool_id = next((i[1] for i in device.identifiers if i[0] == DOMAIN), None)
        if pool_id is not None and pool_id not in valid_pool_ids:
            device_registry.async_remove_device(device.id)


async def _async_add_coordinator(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    pool_id: str,
    pool_name: str,
    *,
    first: bool,
) -> AquariteDataUpdateCoordinator:
    """Create, refresh and subscribe a coordinator for a single pool."""
    coordinator = AquariteDataUpdateCoordinator(
        hass, entry, entry.runtime_data.auth, entry.runtime_data.api, pool_id, pool_name
    )
    try:
        if first:
            await coordinator.async_config_entry_first_refresh()
        else:
            await coordinator.async_refresh()
            if not coordinator.last_update_success:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                )
        try:
            await coordinator.subscribe()
        except AquariteError as exc:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(exc)},
            ) from exc
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise
    entry.runtime_data.coordinators[pool_id] = coordinator
    return coordinator


async def _async_reconcile_pools(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    pool_ids: list[str],
) -> None:
    """Reconcile the runtime coordinator set against a fresh pool ID list."""
    async with entry.runtime_data.sync_lock:
        current = set(entry.runtime_data.coordinators)
        fetched = set(pool_ids)
        if current == fetched:
            return

        new_ids = fetched - current
        names: dict[str, str] = {}
        if new_ids:
            try:
                names = await entry.runtime_data.api.get_pools()
            except AquariteError as err:
                _LOGGER.debug("Pool name lookup failed during reconcile: %s", err)
                new_ids = set()

        for pool_id in new_ids:
            if pool_id not in names:
                continue
            try:
                coordinator = await _async_add_coordinator(
                    hass, entry, pool_id, names[pool_id], first=False
                )
            except ConfigEntryNotReady as err:
                _LOGGER.warning("Failed to add new pool %s: %s", pool_id, err)
                continue
            async_dispatcher_send(
                hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", coordinator
            )

        if stale := current - fetched:
            for pool_id in stale:
                await entry.runtime_data.coordinators.pop(pool_id).async_shutdown()
            _async_remove_stale_devices(hass, entry, fetched)
