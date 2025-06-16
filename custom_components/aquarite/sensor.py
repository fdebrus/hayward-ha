"""Aquarite Sensor entities."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    BRAND,
    MODEL,
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> bool:
    """Set up Aquarite sensor entities from a config entry."""
    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False

    pool_id = entry.data["pool_id"]
    pool_name = entry.data.get("pool_name", pool_id)
    entities = []

    entities.append(
        AquariteTemperatureSensorEntity(hass, dataservice, pool_id, pool_name, "Temperature", "main.temperature")
    )

    if dataservice.get_value(PATH_HASCD):
        entities.append(
            AquariteValueSensorEntity(hass, dataservice, pool_id, pool_name, "CD", "modules.cd.current")
        )

    if dataservice.get_value(PATH_HASCL):
        entities.append(
            AquariteValueSensorEntity(hass, dataservice, pool_id, pool_name, "Cl", "modules.cl.current", None, None, "mdi:gauge")
        )

    if dataservice.get_value(PATH_HASPH):
        entities.append(
            AquariteValueSensorEntity(hass, dataservice, pool_id, pool_name, "pH", "modules.ph.current", SensorDeviceClass.PH, None)
        )

    if dataservice.get_value(PATH_HASRX):
        entities.append(
            AquariteRxValueSensorEntity(hass, dataservice, pool_id, pool_name, "Rx", "modules.rx.current")
        )

    if dataservice.get_value(PATH_HASUV):
        entities.append(
            AquariteValueSensorEntity(hass, dataservice, pool_id, pool_name, "UV", "modules.uv.current")
        )

    if dataservice.get_value(PATH_HASHIDRO):
        entities.append(
            AquariteHydrolyserSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "Electrolysis" if dataservice.get_value("hidro.is_electrolysis") else "Hidrolysis",
                "hidro.current",
            ),
        )

    entities.append(
        AquariteTimeSensorEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            "Hidrolysis Cell Time",
            "hidro.cellTotalTime",
        ),
    )

    async_add_entities(entities)
    return True

class AquariteTemperatureSensorEntity(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._attr_unique_id = f"{self._pool_id}-{name}"

    @property
    def available(self) -> bool:
        return self._dataservice.data is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self):
        try:
            return self._dataservice.get_value(self._value_path)
        except Exception:
            return None

class AquariteValueSensorEntity(CoordinatorEntity, SensorEntity):
    def __init__(
        self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path,
        device_class: SensorDeviceClass = None, native_unit_of_measurement: str = None, icon: str = None
    ) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon
        self._attr_unique_id = f"{self._pool_id}-{name}"

    @property
    def available(self) -> bool:
        return self._dataservice.data is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self):
        try:
            value = self._dataservice.get_value(self._value_path)
            return float(value) / 100
        except Exception:
            return None

class AquariteTimeSensorEntity(CoordinatorEntity, SensorEntity):
    def __init__(
        self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path,
        device_class: SensorDeviceClass = None, native_unit_of_measurement: str = None, icon: str = None
    ) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon
        self._attr_unique_id = f"{self._pool_id}-{name}"

    @property
    def available(self) -> bool:
        return self._dataservice.data is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self):
        try:
            seconds = float(self._dataservice.get_value(self._value_path))
            hours = seconds / 3600
            return round(hours, 2)
        except Exception:
            return None

class AquariteHydrolyserSensorEntity(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._attr_unique_id = f"{self._pool_id}-{name}"

    @property
    def available(self) -> bool:
        return self._dataservice.data is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self) -> float:
        try:
            return float(self._dataservice.get_value(self._value_path)) / 10
        except Exception:
            return None

class AquariteRxValueSensorEntity(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice)
        self._dataservice = dataservice
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{self._pool_name}_{name}"
        self._value_path = value_path
        self._attr_unique_id = f"{self._pool_id}-{name}"

    @property
    def available(self) -> bool:
        return self._dataservice.data is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def native_value(self) -> int:
        try:
            return int(self._dataservice.get_value(self._value_path))
        except Exception:
            return None
