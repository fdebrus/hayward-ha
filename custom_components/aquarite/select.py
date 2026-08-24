"""Aquarite Select entities."""
from __future__ import annotations

from aioaquarite import AquariteError

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity, async_setup_pool_platform

PUMP_MODE_OPTIONS: tuple[str, ...] = ("manual", "auto", "heat", "smart", "intel")
PUMP_SPEED_OPTIONS: tuple[str, ...] = ("slow", "medium", "high")
TIMER_SPEED_OPTIONS: tuple[str, ...] = ("slow", "medium", "high")

LIGHT_FREQ_VALUES: dict[str, int] = {"daily": 86400, "weekly": 604800}

# off and on leave schedule mode; auto only re-arms it, letting the device
# schedule drive light.status (field pairs verified against the Hayward cloud)
LIGHT_MODE_UPDATES: dict[str, dict[str, int]] = {
    "off": {"light.mode": 0, "light.status": 0},
    "on": {"light.mode": 0, "light.status": 1},
    "auto": {"light.mode": 1},
}

PARALLEL_UPDATES = 1


def _build_entities(
    dataservice: AquariteDataUpdateCoordinator,
) -> list[SelectEntity]:
    """Build the select entities for one pool."""
    pool_id, pool_name = dataservice.pool_id, dataservice.pool_name

    entities: list[SelectEntity] = [
        AquariteSelectEntity(
            dataservice, pool_id, pool_name,
            "Pump Mode", "pump_mode", "filtration.mode", PUMP_MODE_OPTIONS,
        ),
        AquariteSelectEntity(
            dataservice, pool_id, pool_name,
            "Pump Speed", "pump_speed", "filtration.manVel", PUMP_SPEED_OPTIONS,
        ),
    ]

    for index in range(1, 4):
        entities.append(
            AquariteSelectEntity(
                dataservice, pool_id, pool_name,
                f"Filtration Timer Speed {index}",
                f"filtration_timer_speed_{index}",
                f"filtration.timerVel{index}",
                TIMER_SPEED_OPTIONS,
            )
        )

    # Light scheduling fields are not present on every controller
    if dataservice.get_value("light.mode") is not None:
        entities.append(
            AquariteLightModeSelectEntity(dataservice, pool_id, pool_name)
        )

    if dataservice.get_value("light.freq") is not None:
        entities.append(
            AquariteValueMapSelectEntity(
                dataservice, pool_id, pool_name,
                "Light Schedule Frequency", "light_schedule_frequency",
                "light.freq", LIGHT_FREQ_VALUES,
            )
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for every pool on the account."""
    async_setup_pool_platform(hass, entry, async_add_entities, _build_entities)


class AquariteSelectEntity(AquariteEntity, SelectEntity):
    """Aquarite select entity."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
        options: tuple[str, ...],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._options_map = options
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)
        self._attr_options = list(options)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        raw_value = self.coordinator.get_value(self._value_path)
        try:
            return self._options_map[int(raw_value)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        try:
            await self.coordinator.async_set_values(
                {self._value_path: self._options_map.index(option)}
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err


class AquariteValueMapSelectEntity(AquariteEntity, SelectEntity):
    """Select entity whose options map to raw API values, not indices."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
        values: dict[str, int],
    ) -> None:
        """Initialize the value-mapped select entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._values = values
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)
        self._attr_options = list(values)

    @property
    def current_option(self) -> str | None:
        """Return the option matching the raw value, if any."""
        raw_value = self.coordinator.get_value(self._value_path)
        try:
            raw = int(raw_value)
        except (TypeError, ValueError):
            return None
        for option, value in self._values.items():
            if value == raw:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        value = self._values[option]
        try:
            await self.coordinator.async_set_values({self._value_path: value})
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err


class AquariteLightModeSelectEntity(AquariteEntity, SelectEntity):
    """Select entity for the pool light mode (off / on / auto).

    Leaving auto must clear light.mode AND set light.status in the same
    cloud command (see AquariteDataUpdateCoordinator.async_set_values),
    so this entity writes through the coordinator instead of the client.
    """

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the light mode select entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_translation_key = "light_mode"
        self._attr_unique_id = self.build_unique_id("Light Mode")
        self._attr_options = list(LIGHT_MODE_UPDATES)

    @property
    def current_option(self) -> str | None:
        """Return auto when the schedule is armed, else the on/off state."""
        mode = self.coordinator.get_value("light.mode")
        status = self.coordinator.get_value("light.status")
        try:
            if int(mode) == 1:
                return "auto"
            return "on" if int(status) == 1 else "off"
        except (TypeError, ValueError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        updates = LIGHT_MODE_UPDATES[option]
        try:
            await self.coordinator.async_set_values(updates)
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
