"""Aquarite Sensor entities."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)
from .entity import AquariteEntity


def _build_entities(
    hass: HomeAssistant,
    dataservice,
    pool_id: str,
    pool_name: str,
) -> list[AquariteEntity]:
    """Assemble the list of sensor entities for the pool."""

    entities: list[AquariteEntity] = []

    for name, path in (
        ("Temperature", "main.temperature"),
        ("Filtration Intel Temperature", "filtration.intel.temp"),
        ("Filtration Smart Min Temp", "filtration.smart.tempMin"),
        ("Filtration Smart High Temp", "filtration.smart.tempHigh"),
    ):
        entities.append(
            AquariteTemperatureSensorEntity(
                hass, dataservice, pool_id, pool_name, name, path
            )
        )

    if dataservice.get_value(PATH_HASCD):
        entities.append(
            AquariteValueSensorEntity(
                hass, dataservice, pool_id, pool_name, "CD", "modules.cd.current"
            )
        )

    if dataservice.get_value(PATH_HASCL):
        entities.append(
            AquariteValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "Cl",
                "modules.cl.current",
                icon="mdi:gauge",
            )
        )

    if dataservice.get_value(PATH_HASPH):
        entities.append(
            AquariteValueSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                "pH",
                "modules.ph.current",
                SensorDeviceClass.PH,
            )
        )

    if dataservice.get_value(PATH_HASRX):
        entities.append(
            AquariteRxValueSensorEntity(
                hass, dataservice, pool_id, pool_name, "Rx", "modules.rx.current"
            )
        )

    if dataservice.get_value(PATH_HASUV):
        entities.append(
            AquariteValueSensorEntity(
                hass, dataservice, pool_id, pool_name, "UV", "modules.uv.current"
            )
        )

    if dataservice.get_value(PATH_HASHIDRO):
        name = (
            "Electrolysis"
            if dataservice.get_value("hidro.is_electrolysis")
            else "Hidrolysis"
        )
        entities.append(
            AquariteHydrolyserSensorEntity(
                hass, dataservice, pool_id, pool_name, name, "hidro.current"
            )
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

    for name, path, icon in (
        (
            "Filtration Interval 1 From",
            "filtration.interval1.from",
            "mdi:clock-start",
        ),
        (
            "Filtration Interval 1 To",
            "filtration.interval1.to",
            "mdi:clock-end",
        ),
        (
            "Filtration Interval 2 From",
            "filtration.interval2.from",
            "mdi:clock-start",
        ),
        (
            "Filtration Interval 2 To",
            "filtration.interval2.to",
            "mdi:clock-end",
        ),
        (
            "Filtration Interval 3 From",
            "filtration.interval3.from",
            "mdi:clock-start",
        ),
        (
            "Filtration Interval 3 To",
            "filtration.interval3.to",
            "mdi:clock-end",
        ),
    ):
        entities.append(
            AquariteIntervalTimeSensorEntity(
                hass, dataservice, pool_id, pool_name, name, path, icon
            )
        )

    for index in range(1, 4):
        entities.append(
            AquariteSpeedLabelSensorEntity(
                hass,
                dataservice,
                pool_id,
                pool_name,
                f"Filtration Timer Speed {index}",
                f"filtration.timerVel{index}",
            )
        )

    for name, key, icon in (
        ("City", "city", "mdi:city"),
        ("Street", "street", "mdi:road"),
        ("Zipcode", "zipcode", "mdi:numeric"),
        ("Country", "country", "mdi:earth"),
        ("Latitude", "lat", "mdi:latitude"),
        ("Longitude", "lng", "mdi:longitude"),
    ):
        entities.append(
            AquariteLocationSensorEntity(
                hass, dataservice, pool_id, pool_name, name, key, icon
            )
        )

    entities.append(AquaritePoolNameSensorEntity(hass, dataservice, pool_id))

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return False

    dataservice = entry_data["coordinator"]

    pool_id = dataservice.get_value("id")
    pool_name = dataservice.get_pool_name(pool_id)

    async_add_entities(_build_entities(hass, dataservice, pool_id, pool_name))

    return True


class AquariteSpeedLabelSensorEntity(AquariteEntity, SensorEntity):
    _attr_icon = "mdi:speedometer"

    SPEED_LABELS = {
        0: "Slow",
        1: "Medium",
        2: "High",
    }

    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        pool_id,
        pool_name,
        name,
        value_path,
    ) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> str:
        value = self._dataservice.get_value(self._value_path)
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return "Unknown"
        return self.SPEED_LABELS.get(int_value, "Unknown")


class AquariteIntervalTimeSensorEntity(AquariteEntity, SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        pool_id,
        pool_name,
        name,
        value_path,
        icon: str | None = None,
    ) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> str | None:
        """Return value as 'HH:MM' or 'HH:MM (+Xd)' if >24h."""
        raw_value = self._dataservice.get_value(self._value_path)
        try:
            seconds = int(raw_value)
        except (TypeError, ValueError):
            return None

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours < 24:
            return f"{hours:02d}:{minutes:02d}"

        display_hours = hours % 24
        days_later = hours // 24
        return f"{display_hours:02d}:{minutes:02d} (+{days_later}d)"


class AquariteTemperatureSensorEntity(AquariteEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return temperature."""
        value = self._dataservice.get_value(self._value_path)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS


class AquariteValueSensorEntity(AquariteEntity, SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        pool_id,
        pool_name,
        name,
        value_path,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return value of sensor."""
        value = self._dataservice.get_value(self._value_path)
        try:
            return float(value) / 100
        except (TypeError, ValueError):
            return None


class AquariteTimeSensorEntity(AquariteEntity, SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        pool_id,
        pool_name,
        name,
        value_path,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_icon = icon
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return value of sensor."""
        value = self._dataservice.get_value(self._value_path)
        try:
            minutes = float(value)
        except (TypeError, ValueError):
            return None

        hours = minutes / 60
        return hours


class AquariteHydrolyserSensorEntity(AquariteEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "gr/h"

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return value of sensor."""
        value = self._dataservice.get_value(self._value_path)
        try:
            return float(value) / 10
        except (TypeError, ValueError):
            return None


class AquariteRxValueSensorEntity(AquariteEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT

    def __init__(self, hass: HomeAssistant, dataservice, pool_id, pool_name, name, value_path) -> None:
        super().__init__(dataservice, pool_id, pool_name, name_suffix=name)
        self._value_path = value_path
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> int | None:
        """Return value of sensor."""
        value = self._dataservice.get_value(self._value_path)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class AquariteLocationSensorEntity(AquariteEntity, SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        dataservice,
        pool_id,
        pool_name,
        name,
        form_key,
        icon: str | None = None,
    ):
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
    def __init__(self, hass: HomeAssistant, dataservice, pool_id):
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
