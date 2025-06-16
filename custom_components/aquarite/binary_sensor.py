"""Aquarite Binary_Sensor entity."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, BRAND, MODEL, PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False

    pool_id = entry.data["pool_id"]
    pool_name = entry.data.get("pool_name", pool_id)

    entities = [
        AquariteBinarySensorEntity(hass, dataservice, "Hidro Flow Status", "hidro.fl1", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Filtration Status", "filtration.status", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Backwash Status", "backwash.status", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Hidro Cover Reduction", "hidro.cover", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "pH Pump Alarm", "modules.ph.al3", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "CD Module Installed", "main.hasCD", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "CL Module Installed", "main.hasCL", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "RX Module Installed", "main.hasRX", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "pH Module Installed", "main.hasPH", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "IO Module Installed", "main.hasIO", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Hidro Module Installed", "main.hasHidro", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "pH Acid Pump", "modules.ph.pump_high_on", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Heating Status", "relays.filtration.heating.status", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Connected", "present", pool_id, pool_name)
    ]

    if dataservice.get_value("main.hasCL"):
        entities.append(AquariteBinarySensorEntity(hass, dataservice, "Hidro FL2 Status", "hidro.fl2", pool_id, pool_name))

    if any(
        dataservice.get_value(path)
        for path in [PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX]
    ):
        entities.append(AquariteBinarySensorTankEntity(hass, dataservice, "Acid Tank", pool_id, pool_name))

    entities.append(
        AquariteBinarySensorEntity(
            hass, dataservice,
            "Electrolysis Low" if dataservice.get_value("hidro.is_electrolysis") else "Hidrolysis Low",
            "hidro.low", pool_id, pool_name
        )
    )

    async_add_entities(entities)
    return True


class AquariteBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity such as flow sensors FL1 & FL2."""

    def __init__(self, hass: HomeAssistant, dataservice, name, value_path, pool_id, pool_name) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._value_path = value_path
        self._attr_name = f"{self._pool_name}_{name}"
        self._attr_unique_id = f"{self._pool_id}-{name}"
        # Uncomment for diagnostic entities:
        # self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._dataservice.data is not None

    @property
    def device_class(self):
        if self._value_path in {
            "hidro.fl1", "hidro.low", "modules.cl.pump_status",
            "modules.rx.pump_status", "modules.ph.al3"
        }:
            return BinarySensorDeviceClass.PROBLEM
        elif self._value_path in {
            "main.hasCD", "main.hasCL", "main.hasRX", "main.hasPH",
            "main.hasHidro", "main.hasIO", "present"
        }:
            return BinarySensorDeviceClass.CONNECTIVITY
        return BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self):
        """Return true if the device is on."""
        try:
            return bool(self._dataservice.get_value(self._value_path))
        except Exception:
            return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteBinarySensorTankEntity(CoordinatorEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity for Tank status."""

    def __init__(self, hass: HomeAssistant, dataservice, name, pool_id, pool_name) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._attr_unique_id = f"{self._pool_id}-{name}"
        # Uncomment if this is a diagnostic sensor:
        # self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._dataservice.data is not None

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        """Return True if any tank is not empty."""
        try:
            tank_modules = [
                "modules.ph.tank",
                "modules.rx.tank",
                "modules.cl.tank",
                "modules.cd.tank",
            ]
            return any(self._dataservice.get_value(module) for module in tank_modules)
        except Exception:
            return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }
