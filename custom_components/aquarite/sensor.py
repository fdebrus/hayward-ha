from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
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


def get_value(data, path):
    """Helper to get value from nested dict by dot path."""
    keys = path.split(".")
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    data = coordinator.data
    pool_id = coordinator.pool_id
    pool_name = coordinator.get_pool_name()

    entities = []

    # Temperature sensors
    entities.append(
        AquariteTemperatureSensor(
            coordinator, pool_id, pool_name, "Temperature", "main.temperature"
        )
    )
    entities.append(
        AquariteTemperatureSensor(
            coordinator,
            pool_id,
            pool_name,
            "Filtration Intel Temperature",
            "filtration.intel.temp",
        )
    )

    # Value sensors
    if get_value(data, PATH_HASCD):
        entities.append(
            AquariteValueSensor(
                coordinator, pool_id, pool_name, "CD", "modules.cd.current"
            )
        )
    if get_value(data, PATH_HASCL):
        entities.append(
            AquariteValueSensor(
                coordinator,
                pool_id,
                pool_name,
                "Cl",
                "modules.cl.current",
                icon="mdi:gauge",
            )
        )
    if get_value(data, PATH_HASPH):
        entities.append(
            AquariteValueSensor(
                coordinator,
                pool_id,
                pool_name,
                "pH",
                "modules.ph.current",
                device_class=SensorDeviceClass.PH,
            )
        )
    if get_value(data, PATH_HASRX):
        entities.append(
            AquariteRxValueSensor(
                coordinator, pool_id, pool_name, "Rx", "modules.rx.current"
            )
        )
    if get_value(data, PATH_HASUV):
        entities.append(
            AquariteValueSensor(
                coordinator, pool_id, pool_name, "UV", "modules.uv.current"
            )
        )
    if get_value(data, PATH_HASHIDRO):
        hydro_name = (
            "Electrolysis" if get_value(data, "hidro.is_electrolysis") else "Hidrolysis"
        )
        entities.append(
            AquariteHydrolyserSensor(
                coordinator, pool_id, pool_name, hydro_name, "hidro.current"
            )
        )

    # Time, interval, speed sensors
    entities.append(
        AquariteTimeSensor(
            coordinator,
            pool_id,
            pool_name,
            "Filtration Intel Time",
            "filtration.intel.time",
            native_unit_of_measurement="h",
        )
    )
    entities.append(
        AquariteTemperatureSensor(
            coordinator,
            pool_id,
            pool_name,
            "Filtration Smart Min Temp",
            "filtration.smart.tempMin",
        )
    )
    entities.append(
        AquariteTemperatureSensor(
            coordinator,
            pool_id,
            pool_name,
            "Filtration Smart High Temp",
            "filtration.smart.tempHigh",
        )
    )

    for i in range(1, 4):
        entities.append(
            AquariteIntervalTimeSensor(
                coordinator,
                pool_id,
                pool_name,
                f"Filtration Interval {i} From",
                f"filtration.interval{i}.from",
                "mdi:clock-start",
            )
        )
        entities.append(
            AquariteIntervalTimeSensor(
                coordinator,
                pool_id,
                pool_name,
                f"Filtration Interval {i} To",
                f"filtration.interval{i}.to",
                "mdi:clock-end",
            )
        )
        entities.append(
            AquariteSpeedLabelSensor(
                coordinator,
                pool_id,
                pool_name,
                f"Filtration Timer Speed {i}",
                f"filtration.timerVel{i}",
            )
        )

    # Location sensors
    entities.append(
        AquariteLocationSensor(
            coordinator, pool_id, pool_name, "City", "city", "mdi:city"
        )
    )
    entities.append(
        AquariteLocationSensor(
            coordinator, pool_id, pool_name, "Street", "street", "mdi:road"
        )
    )
    entities.append(
        AquariteLocationSensor(
            coordinator, pool_id, pool_name, "Zipcode", "zipcode", "mdi:numeric"
        )
    )
    entities.append(
        AquariteLocationSensor(
            coordinator, pool_id, pool_name, "Country", "country", "mdi:earth"
        )
    )
    entities.append(
        AquariteLocationSensor(
            coordinator, pool_id, pool_name, "Latitude", "lat", "mdi:latitude"
        )
    )
    entities.append(
        AquariteLocationSensor(
            coordinator, pool_id, pool_name, "Longitude", "lng", "mdi:longitude"
        )
    )

    entities.append(AquaritePoolNameSensor(coordinator, pool_id, pool_name))

    async_add_entities(entities)


# ---- Entity Classes ----


class AquariteTemperatureSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        return get_value(self.coordinator.data, self._value_path)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteValueSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        pool_id,
        pool_name,
        name,
        value_path,
        device_class=None,
        native_unit_of_measurement=None,
        icon=None,
    ):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        value = get_value(self.coordinator.data, self._value_path)
        return float(value) / 100 if value is not None else None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteRxValueSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT

    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        value = get_value(self.coordinator.data, self._value_path)
        return int(value) if value is not None else None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteHydrolyserSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "gr/h"

    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        value = get_value(self.coordinator.data, self._value_path)
        return float(value) / 10 if value is not None else None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteTimeSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        pool_id,
        pool_name,
        name,
        value_path,
        device_class=None,
        native_unit_of_measurement=None,
        icon=None,
    ):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        minutes = get_value(self.coordinator.data, self._value_path)
        return float(minutes) / 60 if minutes is not None else None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteIntervalTimeSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, pool_id, pool_name, name, value_path, icon=None):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path
        self._attr_icon = icon

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        seconds = get_value(self.coordinator.data, self._value_path)
        if seconds is None:
            return None
        try:
            seconds = int(seconds)
        except (ValueError, TypeError):
            return None
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours < 24:
            return f"{hours:02d}:{minutes:02d}"
        else:
            display_hours = hours % 24
            days_later = hours // 24
            return f"{display_hours:02d}:{minutes:02d} (+{days_later}d)"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteSpeedLabelSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:speedometer"

    SPEED_LABELS = {0: "Slow", 1: "Medium", 2: "High"}

    def __init__(self, coordinator, pool_id, pool_name, name, value_path):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._value_path = value_path

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        value = get_value(self.coordinator.data, self._value_path)
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            int_value = -1
        return self.SPEED_LABELS.get(int_value, "Unknown")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquariteLocationSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, pool_id, pool_name, name, form_key, icon=None):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._form_key = form_key
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"
        self._attr_icon = icon

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        form = get_value(self.coordinator.data, "form")
        if not form:
            return None
        return form.get(self._form_key)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }


class AquaritePoolNameSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, pool_id, pool_name):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._unique_id = f"{pool_id}-name"
        self._attr_name = f"{pool_name} Name"
        self._attr_icon = "mdi:pool"

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        return self._attr_name

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._attr_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }
