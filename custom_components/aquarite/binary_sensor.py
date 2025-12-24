from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .entity import AquariteEntity

from .const import DOMAIN, PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX


PROBLEM_VALUE_PATHS = {
    "hidro.fl1",
    "hidro.low",
    "modules.cl.pump_status",
    "modules.ph.al3",
    "modules.rx.pump_status",
}

CONNECTIVITY_VALUE_PATHS = {
    "main.hasCD",
    "main.hasCL",
    "main.hasHidro",
    "main.hasIO",
    "main.hasPH",
    "main.hasRX",
    "present",
}

TANK_MODULE_PATHS = (
    "modules.ph.tank",
    "modules.rx.tank",
    "modules.cl.tank",
    "modules.cd.tank",
)


@dataclass(frozen=True)
class AquariteBinarySensorConfig:
    """Configuration for a binary sensor entity."""

    name: str
    value_path: str
    device_class: BinarySensorDeviceClass | None = None


BASE_SENSORS: tuple[AquariteBinarySensorConfig, ...] = (
    AquariteBinarySensorConfig("Hidro Flow Status", "hidro.fl1", BinarySensorDeviceClass.PROBLEM),
    AquariteBinarySensorConfig("Filtration Status", "filtration.status", BinarySensorDeviceClass.RUNNING),
    AquariteBinarySensorConfig("Backwash Status", "backwash.status", BinarySensorDeviceClass.RUNNING),
    AquariteBinarySensorConfig("Hidro Cover Reduction", "hidro.cover", BinarySensorDeviceClass.RUNNING),
    AquariteBinarySensorConfig("pH Pump Alarm", "modules.ph.al3", BinarySensorDeviceClass.PROBLEM),
    AquariteBinarySensorConfig("CD Module Installed", "main.hasCD", BinarySensorDeviceClass.CONNECTIVITY),
    AquariteBinarySensorConfig("CL Module Installed", "main.hasCL", BinarySensorDeviceClass.CONNECTIVITY),
    AquariteBinarySensorConfig("RX Module Installed", "main.hasRX", BinarySensorDeviceClass.CONNECTIVITY),
    AquariteBinarySensorConfig("pH Module Installed", "main.hasPH", BinarySensorDeviceClass.CONNECTIVITY),
    AquariteBinarySensorConfig("IO Module Installed", "main.hasIO", BinarySensorDeviceClass.CONNECTIVITY),
    AquariteBinarySensorConfig("Hidro Module Installed", "main.hasHidro", BinarySensorDeviceClass.CONNECTIVITY),
    AquariteBinarySensorConfig("pH Acid Pump", "modules.ph.pump_high_on", BinarySensorDeviceClass.RUNNING),
    AquariteBinarySensorConfig("Heating Status", "relays.filtration.heating.status", BinarySensorDeviceClass.RUNNING),
    AquariteBinarySensorConfig("Filtration Smart Freeze", "filtration.smart.freeze", BinarySensorDeviceClass.RUNNING),
    AquariteBinarySensorConfig("Connected", "present", BinarySensorDeviceClass.CONNECTIVITY),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up a config entry."""

    dataservice = hass.data[DOMAIN]["coordinator"]
    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities: list[BinarySensorEntity] = [
        AquariteBinarySensorEntity(hass, dataservice, config, pool_id, pool_name)
        for config in BASE_SENSORS
    ]

    if dataservice.get_value("main.hasCL"):
        entities.append(
            AquariteBinarySensorEntity(
                hass,
                dataservice,
                AquariteBinarySensorConfig(
                    "Hidro FL2 Status", "hidro.fl2", BinarySensorDeviceClass.PROBLEM
                ),
                pool_id,
                pool_name,
            )
        )

    if any(
        dataservice.get_value(path) for path in (PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX)
    ):
        entities.append(AquariteBinarySensorTankEntity(hass, dataservice, "Acid Tank", pool_id, pool_name))

    entities.append(
        AquariteBinarySensorEntity(
            hass,
            dataservice,
            AquariteBinarySensorConfig(
                "Electrolysis Low"
                if dataservice.get_value("hidro.is_electrolysis")
                else "Hidrolysis Low",
                "hidro.low",
                BinarySensorDeviceClass.PROBLEM,
            ),
            pool_id,
            pool_name,
        )
    )

    async_add_entities(entities)

    return True


class AquariteBinarySensorEntity(AquariteEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity such as flow sensors FL1 & FL2."""

    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        config: AquariteBinarySensorConfig,
        pool_id,
        pool_name,
    ) -> None:
        """Initialize an Aquarite Binary Sensor Entity."""

        super().__init__(dataservice, pool_id, pool_name, name_suffix=config.name)
        self._value_path = config.value_path
        self._device_class = config.device_class
        self._attr_unique_id = self.build_unique_id(config.name)

    @property
    def device_class(self):
        """Return the class of the binary sensor."""

        if self._device_class:
            return self._device_class

        if self._value_path in PROBLEM_VALUE_PATHS:
            return BinarySensorDeviceClass.PROBLEM
        if self._value_path in CONNECTIVITY_VALUE_PATHS:
            return BinarySensorDeviceClass.CONNECTIVITY
        return BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self):
        """Return true if the device is on."""
        return bool(self._dataservice.get_value(self._value_path))


class AquariteBinarySensorTankEntity(AquariteEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity Tank."""

    def __init__(self, hass: HomeAssistant, dataservice, name, pool_id, pool_name) -> None:
        """Initialize an Aquarite Binary Sensor Entity."""
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        """Return false if the tank is empty."""

        return any(self._dataservice.get_value(module) for module in TANK_MODULE_PATHS)

    
