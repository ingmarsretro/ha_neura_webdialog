"""Temperature sensors from schema.jsp."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_POINTS
from .coordinator import NeuraDataUpdateCoordinator
from .entity import neura_device_info

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = tuple(
    SensorEntityDescription(
        key=point.key,
        translation_key=point.key,
        icon=point.icon,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    )
    for point in DATA_POINTS
    if point.kind == "float"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one temperature sensor per float field."""

    coordinator: NeuraDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        NeuraTemperatureSensor(coordinator, entry, description) for description in SENSOR_DESCRIPTIONS
    )


class NeuraTemperatureSensor(CoordinatorEntity[NeuraDataUpdateCoordinator], SensorEntity):
    """A temperature read from the Neura schema page."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description: SensorEntityDescription) -> None:
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
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        value = data.get(self.entity_description.key)
        if value is None:
            return None
        return float(value)
