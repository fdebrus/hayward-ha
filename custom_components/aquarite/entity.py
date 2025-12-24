"""Shared base entity helpers for Aquarite."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN, MODEL


class AquariteEntity(CoordinatorEntity):
    """Base entity class for Aquarite platforms."""

    def __init__(self, dataservice, pool_id: str, pool_name: str, *, name_suffix: str | None = None, full_name: str | None = None) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
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
            self._attr_name = f"{pool_name}_{name_suffix}"

    def build_unique_id(self, suffix: str, *, delimiter: str = "-") -> str:
        """Return a consistent unique ID for the entity."""

        return f"{self._pool_id}{delimiter}{suffix}"
