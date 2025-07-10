from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, BRAND, MODEL, PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX


def get_value(data, path):
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

    entities = [
        AquariteBinarySensorEntity(
            coordinator, "Hidro Flow Status", "hidro.fl1", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "Filtration Status", "filtration.status", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "Backwash Status", "backwash.status", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "Hidro Cover Reduction", "hidro.cover", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "pH Pump Alarm", "modules.ph.al3", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "CD Module Installed", "main.hasCD", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "CL Module Installed", "main.hasCL", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "RX Module Installed", "main.hasRX", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "pH Module Installed", "main.hasPH", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "IO Module Installed", "main.hasIO", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "Hidro Module Installed", "main.hasHidro", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator, "pH Acid Pump", "modules.ph.pump_high_on", pool_id, pool_name
        ),
        AquariteBinarySensorEntity(
            coordinator,
            "Heating Status",
            "relays.filtration.heating.status",
            pool_id,
            pool_name,
        ),
        AquariteBinarySensorEntity(
            coordinator,
            "Filtration Smart Freeze",
            "filtration.smart.freeze",
            pool_id,
            pool_name,
        ),
        AquariteBinarySensorEntity(
            coordinator, "Connected", "present", pool_id, pool_name
        ),
    ]

    if get_value(data, "main.hasCL"):
        entities.append(
            AquariteBinarySensorEntity(
                coordinator, "Hidro FL2 Status", "hidro.fl2", pool_id, pool_name
            )
        )

    if any(
        get_value(data, path)
        for path in [PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX]
    ):
        entities.append(
            AquariteBinarySensorTankEntity(coordinator, "Acid Tank", pool_id, pool_name)
        )

    entities.append(
        AquariteBinarySensorEntity(
            coordinator,
            "Electrolysis Low"
            if get_value(data, "hidro.is_electrolysis")
            else "Hidrolysis Low",
            "hidro.low",
            pool_id,
            pool_name,
        )
    )

    async_add_entities(entities)
    return True


class AquariteBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity such as flow sensors FL1 & FL2."""

    def __init__(self, coordinator, name, value_path, pool_id, pool_name):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name}_{name}"
        self._value_path = value_path
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"

    @property
    def device_class(self):
        if self._value_path in {
            "hidro.fl1",
            "hidro.low",
            "modules.cl.pump_status",
            "modules.rx.pump_status",
            "modules.ph.al3",
        }:
            return BinarySensorDeviceClass.PROBLEM
        elif self._value_path in {
            "main.hasCD",
            "main.hasCL",
            "main.hasRX",
            "main.hasPH",
            "main.hasHidro",
            "main.hasIO",
            "present",
        }:
            return BinarySensorDeviceClass.CONNECTIVITY
        return BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self):
        return bool(get_value(self.coordinator.data, self._value_path))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def unique_id(self):
        return self._unique_id


class AquariteBinarySensorTankEntity(CoordinatorEntity, BinarySensorEntity):
    """Aquarite Binary Sensor Entity Tank."""

    def __init__(self, coordinator, name, pool_id, pool_name):
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        self._attr_name = f"{pool_name}_{name}"
        self._unique_id = f"{pool_id}-{name.replace(' ', '_').lower()}"

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        tank_modules = [
            "modules.ph.tank",
            "modules.rx.tank",
            "modules.cl.tank",
            "modules.cd.tank",
        ]
        return any(get_value(self.coordinator.data, module) for module in tank_modules)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._pool_id)},
            "name": self._pool_name,
            "manufacturer": BRAND,
            "model": MODEL,
        }

    @property
    def unique_id(self):
        return self._unique_id
