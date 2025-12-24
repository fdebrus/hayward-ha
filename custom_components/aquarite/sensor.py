"""Aquarite Sensor entities."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant

from .entity import AquariteEntity

from .const import (
    DOMAIN,
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)

async def async_setup_entry(hass : HomeAssistant, entry, async_add_entities) -> bool:
    
    dataservice = hass.data[DOMAIN]["coordinator"]

    if not dataservice:
        return False

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    entities = []

    entities.append(
        AquariteTemperatureSensorEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            "Temperature",
            "main.temperature",
        ),
    )

    entities.append(
        AquariteTemperatureSensorEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            "Filtration Intel Temperature",
            "filtration.intel.temp",
        ),
    )

    if dataservice.get_value( PATH_HASCD ):
        entities.append(
            AquariteValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "CD",
                "modules.cd.current",
            ),
        )

    if dataservice.get_value( PATH_HASCL ):
        entities.append(
            AquariteValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "Cl",
                "modules.cl.current",
                None,
                None,
                "mdi:gauge"
            ),
        )

    if dataservice.get_value( PATH_HASPH ):
        entities.append(
            AquariteValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "pH",
                "modules.ph.current",
                SensorDeviceClass.PH,
                None
            ),
        )

    if dataservice.get_value( PATH_HASRX ):
        entities.append(
            AquariteRxValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "Rx",
                "modules.rx.current",
            ),
        )

    if dataservice.get_value( PATH_HASUV ):
        entities.append(
            AquariteValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "UV",
                "modules.uv.current",
            ),
        )

    if dataservice.get_value( PATH_HASHIDRO ):
        entities.append(
            AquariteHydrolyserSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "Electrolysis" if dataservice.get_value( "hidro.is_electrolysis") else "Hidrolysis",
                "hidro.current",
            ),
        )

    entities.append(
            AquariteTimeSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "Filtration Intel Time",
                "filtration.intel.time",
                native_unit_of_measurement="h",
            )
        )

    entities.append(
        AquariteTemperatureSensorEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            "Filtration Smart Min Temp",
            "filtration.smart.tempMin",
        ),
    )

    entities.append(
        AquariteTemperatureSensorEntity(
            hass,
            dataservice,
            pool_id,
            pool_name,
            "Filtration Smart High Temp",
            "filtration.smart.tempHigh",
        ),
    )

    entities.append(AquariteIntervalTimeSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Interval 1 From", "filtration.interval1.from", "mdi:clock-start"))
    entities.append(AquariteIntervalTimeSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Interval 1 To", "filtration.interval1.to", "mdi:clock-end"))
    entities.append(AquariteIntervalTimeSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Interval 2 From", "filtration.interval2.from", "mdi:clock-start"))
    entities.append(AquariteIntervalTimeSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Interval 2 To", "filtration.interval2.to", "mdi:clock-end"))
    entities.append(AquariteIntervalTimeSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Interval 3 From", "filtration.interval3.from", "mdi:clock-start"))
    entities.append(AquariteIntervalTimeSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Interval 3 To", "filtration.interval3.to", "mdi:clock-end"))
    entities.append(AquariteSpeedLabelSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Timer Speed 1", "filtration.timerVel1"))
    entities.append(AquariteSpeedLabelSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Timer Speed 2", "filtration.timerVel2"))
    entities.append(AquariteSpeedLabelSensorEntity(hass, dataservice, pool_id, pool_name, "Filtration Timer Speed 3", "filtration.timerVel3"))

    entities.append(AquariteLocationSensorEntity(hass, dataservice, pool_id, pool_name, "City", "city","mdi:city"))
    entities.append(AquariteLocationSensorEntity(hass, dataservice, pool_id, pool_name, "Street", "street", "mdi:road"))
    entities.append(AquariteLocationSensorEntity(hass, dataservice, pool_id, pool_name, "Zipcode", "zipcode", "mdi:numeric"))
    entities.append(AquariteLocationSensorEntity(hass, dataservice, pool_id, pool_name, "Country", "country", "mdi:earth"))
    entities.append(AquariteLocationSensorEntity(hass, dataservice, pool_id, pool_name, "Latitude", "lat", "mdi:latitude"))
    entities.append(AquariteLocationSensorEntity(hass, dataservice, pool_id, pool_name, "Longitude", "lng", "mdi:longitude"))

    entities.append(AquaritePoolNameSensorEntity(hass, dataservice, pool_id))

    async_add_entities(entities)

    return True

class AquariteSpeedLabelSensorEntity(AquariteEntity, SensorEntity):
    _attr_icon = "mdi:speedometer"

    SPEED_LABELS = {
        0: "Slow",
        1: "Medium",
        2: "High",
    }

    def __init__(self, hass, dataservice, pool_id, pool_name, name, value_path):
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self):
        value = self._dataservice.get_value(self._value_path)
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            int_value = -1
        return self.SPEED_LABELS.get(int_value, "Unknown")

class AquariteIntervalTimeSensorEntity(AquariteEntity, SensorEntity):
    def __init__(self, hass, dataservice, pool_id, pool_name, name, value_path, icon=None):
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self):
        """Return value as 'HH:MM' or 'HH:MM (+Xd)' if >24h."""
        seconds = int(self._dataservice.get_value(self._value_path))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours < 24:
            return f"{hours:02d}:{minutes:02d}"
        else:
            display_hours = hours % 24
            days_later = hours // 24
            return f"{display_hours:02d}:{minutes:02d} (+{days_later}d)"

class AquariteTemperatureSensorEntity(AquariteEntity, SensorEntity):

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self):
        """Return temperature."""
        return self._dataservice.get_value(self._value_path)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

class AquariteValueSensorEntity(AquariteEntity, SensorEntity):

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path, device_class:SensorDeviceClass = None, native_unit_of_measurement:str = None, icon:str = None) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self):
        """Return value of sensor."""
        value = self._dataservice.get_value(self._value_path)
        return float(value) / 100

class AquariteTimeSensorEntity(AquariteEntity, SensorEntity):

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path, device_class:SensorDeviceClass = None, native_unit_of_measurement:str = None, icon:str = None) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self):
        """Return value of sensor."""
        minutes = float(self._dataservice.get_value(self._value_path))
        hours = minutes / 60 
        return hours

class AquariteHydrolyserSensorEntity(AquariteEntity, SensorEntity):

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "gr/h"

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float:
        """Return value of sensor."""
        return float(self._dataservice.get_value(self._value_path)) / 10

class AquariteRxValueSensorEntity(AquariteEntity, SensorEntity):

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT

    def __init__(self, hass : HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:

        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)
    
    @property
    def native_value(self) -> int:
        """Return value of sensor."""
        return int(self._dataservice.get_value(self._value_path))

class AquariteLocationSensorEntity(AquariteEntity, SensorEntity):
    def __init__(self, hass, dataservice, pool_id, pool_name, name, form_key, icon=None):
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._form_key = form_key
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self):
        form = self._dataservice.get_value("form")
        if not form:
            return None
        return form.get(self._form_key)

class AquaritePoolNameSensorEntity(AquariteEntity, SensorEntity):
    def __init__(self, hass, dataservice, pool_id):
        pool_name = dataservice.get_pool_name(pool_id)
        super().__init__(dataservice, pool_id, pool_name, full_name=f"{pool_name} Name")
        self._unique_id = dataservice.get_value("id") + "-name"
        self._attr_icon = "mdi:pool"

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        return self._dataservice.get_pool_name(self._pool_id)
