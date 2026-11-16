"""On/off states from schema.jsp, plus the login status."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_POINTS, LOGIN_KEY
from .coordinator import NeuraDataUpdateCoordinator
from .entity import neura_device_info

_DEVICE_CLASSES = {
    "heat": BinarySensorDeviceClass.HEAT,
    "running": BinarySensorDeviceClass.RUNNING,
}

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    *(
        BinarySensorEntityDescription(
            key=point.key,
            translation_key=point.key,
            icon=point.icon,
            device_class=_DEVICE_CLASSES.get(point.binary_device_class) if point.binary_device_class else None,
        )
        for point in DATA_POINTS
        if point.kind == "bool"
    ),
    BinarySensorEntityDescription(
        key=LOGIN_KEY,
        translation_key=LOGIN_KEY,
        icon="mdi:login",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create binary sensors for the boolean schema fields and the login state."""

    coordinator: NeuraDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        NeuraBinarySensor(coordinator, entry, description) for description in BINARY_SENSOR_DESCRIPTIONS
    )


class NeuraBinarySensor(CoordinatorEntity[NeuraDataUpdateCoordinator], BinarySensorEntity):
    """A boolean Neura value. MQTT still receives 1 or 0."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = f"neura_{description.key}"
        self._attr_device_info = neura_device_info(entry)

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return super().available and isinstance(data, dict) and self.entity_description.key in data

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        value = data.get(self.entity_description.key)
        if value is None:
            return None
        return bool(value)
