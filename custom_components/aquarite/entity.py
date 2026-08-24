"""Shared base entity helpers for Aquarite."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN, MODEL, SIGNAL_NEW_POOL
from .coordinator import AquariteDataUpdateCoordinator

if TYPE_CHECKING:
    from . import AquariteConfigEntry


@callback
def async_setup_pool_platform(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build_entities: Callable[[AquariteDataUpdateCoordinator], Iterable[Entity]],
) -> None:
    """Set up a platform's entities for every pool, now and as pools appear.

    Builds entities for each pool coordinator on the account and hooks the
    SIGNAL_NEW_POOL dispatcher so pools added to the Hayward account at
    runtime get their entities without a reload.
    """
    entities: list[Entity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(build_entities(coordinator))
    async_add_entities(entities)

    @callback
    def _async_add_pool(coordinator: AquariteDataUpdateCoordinator) -> None:
        async_add_entities(build_entities(coordinator))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", _async_add_pool
        )
    )


class AquariteEntity(CoordinatorEntity[AquariteDataUpdateCoordinator]):
    """Base entity class for Aquarite platforms."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        sw_version = coordinator.get_value("main.version")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_id)},
            name=pool_name,
            manufacturer=BRAND,
            model=MODEL,
            sw_version=str(sw_version) if sw_version is not None else None,
        )

    @property
    def pool_id(self) -> str:
        """Return the pool ID for the entity."""
        return self._pool_id

    @property
    def pool_name(self) -> str:
        """Return the friendly pool name for the entity."""
        return self._pool_name

    def build_unique_id(self, suffix: str) -> str:
        """Return a consistent unique ID for the entity."""
        return f"{self._pool_id}-{suffix}"
