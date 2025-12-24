"""Aquarite Select entities."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import AquariteEntity

PUMP_MODE_OPTIONS: tuple[str, ...] = ("Manual", "Auto", "Heat", "Smart", "Intel")
PUMP_SPEED_OPTIONS: tuple[str, ...] = ("Slow", "Medium", "High")


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquaritePumpModeEntity(dataservice, pool_id, pool_name, "Pump Mode", "filtration.mode"),
        AquaritePumpSpeedEntity(dataservice, pool_id, pool_name, "Pump Speed", "filtration.manVel"),
    ]

    async_add_entities(entities)

    return True


class AquariteSelectEntity(AquariteEntity, SelectEntity):
    """Shared functionality for Aquarite select entities."""

    def __init__(
        self,
        dataservice,
        pool_id,
        pool_name,
        name: str,
        value_path: str,
        allowed_values: Sequence[str],
    ) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._allowed_values: tuple[str, ...] = tuple(allowed_values)
        self._attr_unique_id = self.build_unique_id(name, delimiter="")
        self._attr_options = list(self._allowed_values)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option, if available."""

        raw_value = self._dataservice.get_value(self._value_path)

        try:
            return self._allowed_values[int(raw_value)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""

        if option not in self._allowed_values:
            raise ValueError(f"Invalid option {option!r} for {self.name}")

        await self._dataservice.api.set_value(
            self._pool_id, self._value_path, self._allowed_values.index(option)
        )


class AquaritePumpModeEntity(AquariteSelectEntity):
    """Select entity representing the pump mode."""

    def __init__(self, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name, value_path, PUMP_MODE_OPTIONS)


class AquaritePumpSpeedEntity(AquariteSelectEntity):
    """Select entity representing the pump speed."""

    def __init__(self, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name, value_path, PUMP_SPEED_OPTIONS)

