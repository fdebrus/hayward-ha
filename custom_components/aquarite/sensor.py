"""Aquarite Sensor entities."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import (
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite sensors."""
    dataservice = entry.runtime_data.coordinator
    pool_id = dataservice.pool_id
    pool_name = entry.title

    entities: list[AquariteEntity] = []

    # Temperature Sensors
    for name, translation_key, path in (
        ("Temperature", "temperature", "main.temperature"),
        ("Filtration Intel Temperature", "filtration_intel_temperature", "filtration.intel.temp"),
        ("Filtration Smart Min Temp", "filtration_smart_min_temp", "filtration.smart.tempMin"),
        ("Filtration Smart High Temp", "filtration_smart_high_temp", "filtration.smart.tempHigh"),
    ):
        entities.append(
            AquariteTemperatureSensorEntity(
                dataservice, pool_id, pool_name, name, translation_key, path
            )
        )

    # Module Presence Sensors
    if dataservice.get_value(PATH_HASCD):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "CD", "cd", "modules.cd.current"
            )
        )

    if dataservice.get_value(PATH_HASCL):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "Cl", "cl", "modules.cl.current"
            )
        )

    if dataservice.get_value(PATH_HASPH):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "pH", "ph",
                "modules.ph.current",
                device_class=SensorDeviceClass.PH,
            )
        )

    if dataservice.get_value(PATH_HASRX):
        entities.append(
            AquariteRxValueSensorEntity(
                dataservice, pool_id, pool_name, "Rx", "rx", "modules.rx.current"
            )
        )

    if dataservice.get_value(PATH_HASUV):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "UV", "uv", "modules.uv.current"
            )
        )

    if dataservice.get_value(PATH_HASHIDRO):
        is_electrolysis = dataservice.get_value("hidro.is_electrolysis")
        name = "Electrolysis" if is_electrolysis else "Hidrolysis"
        key = "electrolysis" if is_electrolysis else "hydrolysis"
        entities.append(
            AquariteHydrolyserSensorEntity(
                dataservice, pool_id, pool_name, name, key, "hidro.current"
            )
        )
        entities.extend([
            AquariteCellRuntimeSensorEntity(
                dataservice, pool_id, pool_name,
                "Cell Total Time", "cell_total_time", "hidro.cellTotalTime",
            ),
            AquariteCellRuntimeSensorEntity(
                dataservice, pool_id, pool_name,
                "Cell Partial Time", "cell_partial_time", "hidro.cellPartialTime",
            ),
        ])

    # Wi-Fi signal strength (diagnostic, off by default — only useful on Wi-Fi controllers)
    entities.append(
        AquariteRssiSensorEntity(dataservice, pool_id, pool_name)
    )

    # Time and Interval Sensors
    entities.append(
        AquariteTimeSensorEntity(
            dataservice, pool_id, pool_name,
            "Filtration Intel Time", "filtration_intel_time",
            "filtration.intel.time",
            native_unit_of_measurement="h",
        )
    )

    for name, translation_key, path in (
        ("Filtration Interval 1 From", "filtration_interval_1_from", "filtration.interval1.from"),
        ("Filtration Interval 1 To", "filtration_interval_1_to", "filtration.interval1.to"),
        ("Filtration Interval 2 From", "filtration_interval_2_from", "filtration.interval2.from"),
        ("Filtration Interval 2 To", "filtration_interval_2_to", "filtration.interval2.to"),
        ("Filtration Interval 3 From", "filtration_interval_3_from", "filtration.interval3.from"),
        ("Filtration Interval 3 To", "filtration_interval_3_to", "filtration.interval3.to"),
    ):
        entities.append(
            AquariteIntervalTimeSensorEntity(
                dataservice, pool_id, pool_name, name, translation_key, path
            )
        )

    # Speed sensors
    for index in range(1, 4):
        entities.append(
            AquariteSpeedLabelSensorEntity(
                dataservice, pool_id, pool_name,
                f"Filtration Timer Speed {index}",
                f"filtration_timer_speed_{index}",
                f"filtration.timerVel{index}",
            )
        )

    # Location sensors (diagnostic)
    for name, translation_key, key in (
        ("City", "city", "city"),
        ("Street", "street", "street"),
        ("Zipcode", "zipcode", "zipcode"),
        ("Country", "country", "country"),
        ("Latitude", "latitude", "lat"),
        ("Longitude", "longitude", "lng"),
    ):
        entities.append(
            AquariteLocationSensorEntity(
                dataservice, pool_id, pool_name, name, translation_key, key
            )
        )

    entities.append(
        AquaritePoolNameSensorEntity(dataservice, pool_id, pool_name)
    )

    async_add_entities(entities)


class AquariteSpeedLabelSensorEntity(AquariteEntity, SensorEntity):
    """Speed label sensor entity."""

    SPEED_LABELS: dict[int, str] = {0: "Slow", 1: "Medium", 2: "High"}

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the speed label sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> str:
        """Return the speed label."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return self.SPEED_LABELS.get(int(value), "Unknown")
        except (ValueError, TypeError):
            return "Unknown"


class AquariteIntervalTimeSensorEntity(AquariteEntity, SensorEntity):
    """Interval time sensor entity."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the interval time sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> str | None:
        """Return the time interval as HH:MM."""
        raw_value = self.coordinator.get_value(self._value_path)
        try:
            seconds = int(raw_value)
            hours, minutes = seconds // 3600, (seconds % 3600) // 60
            if hours < 24:
                return f"{hours:02d}:{minutes:02d}"
            return f"{hours % 24:02d}:{minutes:02d} (+{hours // 24}d)"
        except (TypeError, ValueError):
            return None


class AquariteTemperatureSensorEntity(AquariteEntity, SensorEntity):
    """Temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class AquariteValueSensorEntity(AquariteEntity, SensorEntity):
    """Generic value sensor entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize the value sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 100
        except (TypeError, ValueError):
            return None


class AquariteTimeSensorEntity(AquariteEntity, SensorEntity):
    """Time sensor entity."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize the time sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the time value in hours."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 60
        except (TypeError, ValueError):
            return None


class AquariteHydrolyserSensorEntity(AquariteEntity, SensorEntity):
    """Hydrolyser sensor entity."""

    _attr_native_unit_of_measurement = "gr/h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the hydrolyser sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the hydrolyser value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 10
        except (TypeError, ValueError):
            return None


class AquariteRxValueSensorEntity(AquariteEntity, SensorEntity):
    """Redox value sensor entity."""

    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the Rx sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> int | None:
        """Return the Rx value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class AquariteLocationSensorEntity(AquariteEntity, SensorEntity):
    """Location sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        form_key: str,
    ) -> None:
        """Initialize the location sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._form_key = form_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> str | None:
        """Return the location value."""
        form = self.coordinator.get_value("form")
        return form.get(self._form_key) if form else None


class AquaritePoolNameSensorEntity(AquariteEntity, SensorEntity):
    """Pool name sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the pool name sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_translation_key = "pool_name"
        self._attr_unique_id = f"{pool_id}-name"

    @property
    def native_value(self) -> str:
        """Return the pool name."""
        return self._pool_name


class AquariteCellRuntimeSensorEntity(AquariteEntity, SensorEntity):
    """Electrolysis cell runtime sensor (raw seconds reported as hours)."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the cell runtime sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return runtime in hours, rounded to one decimal."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return round(int(value) / 3600, 1)
        except (TypeError, ValueError):
            return None


class AquariteRssiSensorEntity(AquariteEntity, SensorEntity):
    """Controller Wi-Fi signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the RSSI sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_translation_key = "rssi"
        self._attr_unique_id = self.build_unique_id("RSSI")

    @property
    def native_value(self) -> int | None:
        """Return the RSSI value."""
        value = self.coordinator.get_value("main.RSSI")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
