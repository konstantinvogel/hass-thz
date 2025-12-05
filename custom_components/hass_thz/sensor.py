"""Sensor platform for THZ Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import THZDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# Temperature sensors from sGlobal (FB)
TEMPERATURE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="outsideTemp",
        name="Outside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="flowTemp",
        name="Flow Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="returnTemp",
        name="Return Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dhwTemp",
        name="Hot Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hotGasTemp",
        name="Hot Gas Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="evaporatorTemp",
        name="Evaporator Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="condenserTemp",
        name="Condenser Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="collectorTemp",
        name="Collector Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="insideTemp",
        name="Inside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="flowTempHC2",
        name="Flow Temperature HC2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Heating circuit sensors from sHC1 (F4)
HEATING_CIRCUIT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="flowTempSet",
        name="Flow Temperature Setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
    SensorEntityDescription(
        key="roomTempSet",
        name="Room Temperature Setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
    SensorEntityDescription(
        key="roomTemp",
        name="Room Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="onOffCycles",
        name="Compressor On/Off Cycles",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

# Operating hours from sHistory (09)
HOURS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="compressorHeatingHours",
        name="Compressor Heating Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="compressorCoolingHours",
        name="Compressor Cooling Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="compressorDHWHours",
        name="Compressor DHW Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="boosterHeatingHours",
        name="Booster Heating Hours",
        icon="mdi:timer-alert",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="boosterDHWHours",
        name="Booster DHW Hours",
        icon="mdi:timer-alert",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

# Fan sensors from sGlobal (FB)
FAN_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="inputVentilatorSpeed",
        name="Input Fan Speed",
        icon="mdi:fan",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outputVentilatorSpeed",
        name="Output Fan Speed",
        icon="mdi:fan",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Error sensors from sLast (D1)
ERROR_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="numberOfFaults",
        name="Number of Faults",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# All sensors combined
ALL_SENSORS = (
    TEMPERATURE_SENSORS
    + HEATING_CIRCUIT_SENSORS
    + HOURS_SENSORS
    + FAN_SENSORS
    + ERROR_SENSORS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ sensors based on a config entry."""
    coordinator: THZDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[THZSensor] = []

    for description in ALL_SENSORS:
        # Only add sensor if data is available
        if coordinator.data and description.key in coordinator.data:
            entities.append(THZSensor(coordinator, description))
            _LOGGER.debug("Adding sensor: %s", description.key)
        else:
            _LOGGER.debug(
                "Skipping sensor %s - not available in data",
                description.key
            )

    async_add_entities(entities)
    _LOGGER.info("Added %d sensors", len(entities))


class THZSensor(CoordinatorEntity[THZDataUpdateCoordinator], SensorEntity):
    """Representation of a THZ sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: THZDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )
