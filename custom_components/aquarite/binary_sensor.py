from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BRAND, MODEL, PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up a config entry."""
    dataservice = hass.data[DOMAIN].get(entry.entry_id)

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = [
        AquariteBinarySensorEntity(hass, dataservice, "Hidro Flow Status", "hidro.fl1", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Filtration Status", "filtration.status", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Backwash Status", "backwash.status", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "Hidro Cover Reduction", "hidro.cover", pool_id, pool_name),
        AquariteBinarySensorEntity(hass, dataservice, "pH Pump Alarm", "modules.ph.al3", pool_id, pool_name)
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
            hass, dataservice, "Electrolysis Low" if dataservice.get_value("hidro.is_electrolysis") else "Hidrolysis Low", "hidro.low", pool_id, pool_name
        )
    )

    async_add_entities(entities)
    
    return True


class AquariteBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity such as flow sensors FL1 & FL2."""

    def __init__(self, hass: HomeAssistant, dataservice, name, value_path, pool_id, pool_name) -> None:
        """Initialize an Aquarite Binary Sensor Entity."""
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{self._pool_id}-{name}"

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        if self._value_path in {"hidro.fl1", "hidro.low", "modules.cl.pump_status", "modules.rx.pump_status", "modules.ph.al3"}:
            return BinarySensorDeviceClass.PROBLEM
        return BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self):
        """Return true if the device is on."""
        return bool(self._dataservice.get_value(self._value_path))

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id

class AquariteBinarySensorTankEntity(CoordinatorEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity Tank."""

    def __init__(self, hass: HomeAssistant, dataservice, name, pool_id, pool_name) -> None:
        """Initialize an Aquarite Binary Sensor Entity."""
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._unique_id = f"{self._pool_id}-{name}"

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        """Return false if the tank is empty."""
        tank_modules = [
            "modules.ph.tank",
            "modules.rx.tank",
            "modules.cl.tank",
            "modules.cd.tank",
        ]
        return any(self._dataservice.get_value(module) for module in tank_modules)

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id
