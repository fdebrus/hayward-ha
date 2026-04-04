"""Aquarite Switch entities."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

SWITCH_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("electrolysis_cover", "hidro.cover_enabled"),
    ("electrolysis_boost", "hidro.cloration_enabled"),
    ("relay_1", "relays.relay1.info.onoff"),
    ("relay_2", "relays.relay2.info.onoff"),
    ("relay_3", "relays.relay3.info.onoff"),
    ("relay_4", "relays.relay4.info.onoff"),
    ("filtration", "filtration.status"),
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite switch platform."""
    dataservice = entry.runtime_data.coordinator
    pool_id, pool_name = dataservice.pool_id, entry.title

    async_add_entities([
        AquariteSwitchEntity(dataservice, pool_id, pool_name, translation_key, path)
        for translation_key, path in SWITCH_DEFINITIONS
    ])


class AquariteSwitchEntity(AquariteEntity, SwitchEntity):
    """Representation of an Aquarite switch."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        onoff = bool(self._dataservice.get_value(self._value_path))
        if "relay" in self._value_path:
            status_path = self._value_path.replace("onoff", "status")
            status = bool(self._dataservice.get_value(status_path))
            return onoff or status
        return onoff

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the switch on."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 1)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the switch off."""
        await self._dataservice.api.set_value(self._pool_id, self._value_path, 0)
