"""Shared base entity helpers for Aquarite."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN, MODEL
from .coordinator import AquariteDataUpdateCoordinator


class AquariteEntity(CoordinatorEntity[AquariteDataUpdateCoordinator]):
    """Base entity class for Aquarite platforms."""

    _attr_has_entity_name = True

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        *,
        name_suffix: str | None = None,
        full_name: str | None = None,
    ) -> None:
        super().__init__(dataservice)
        self._dataservice: AquariteDataUpdateCoordinator = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, pool_id)},
            "name": pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

        if full_name:
            self._attr_name = full_name
        elif name_suffix:
            # When ``_attr_has_entity_name`` is True, Home Assistant automatically
            # prefixes the device name to the entity name. Provide only the suffix
            # here to avoid duplicating the pool name in the generated entity ID.
            self._attr_name = name_suffix

    @property
    def pool_id(self) -> str:
        """Return the pool ID for the entity."""

        return self._pool_id

    @property
    def pool_name(self) -> str:
        """Return the friendly pool name for the entity."""

        return self._pool_name

    def build_unique_id(self, suffix: str, *, delimiter: str = "-") -> str:
        """Return a consistent unique ID for the entity."""

        return f"{self._pool_id}{delimiter}{suffix}"
