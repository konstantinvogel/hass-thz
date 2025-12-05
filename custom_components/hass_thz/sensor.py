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
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import THZDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Temperature sensors from sGlobal (FB)
# =============================================================================
TEMPERATURE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="outsideTemp",
        name="Outside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="outsideTempFiltered",
        name="Outside Temperature (Filtered)",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="flowTemp",
        name="Flow Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-up",
    ),
    SensorEntityDescription(
        key="returnTemp",
        name="Return Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-down",
    ),
    SensorEntityDescription(
        key="dhwTemp",
        name="Hot Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-thermometer",
    ),
    SensorEntityDescription(
        key="hotGasTemp",
        name="Hot Gas Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-burner",
    ),
    SensorEntityDescription(
        key="evaporatorTemp",
        name="Evaporator Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:snowflake-thermometer",
    ),
    SensorEntityDescription(
        key="condenserTemp",
        name="Condenser Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="collectorTemp",
        name="Collector Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-panel",
    ),
    SensorEntityDescription(
        key="insideTemp",
        name="Inside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-thermometer",
    ),
    SensorEntityDescription(
        key="flowTempHC2",
        name="Flow Temperature HC2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-up",
    ),
)

# =============================================================================
# Heating circuit sensors from sHC1 (F4)
# =============================================================================
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
        icon="mdi:home-thermometer",
    ),
    SensorEntityDescription(
        key="heatSetTemp",
        name="Heating Setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
    SensorEntityDescription(
        key="heatTemp",
        name="Heating Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="dhwSetTemp",
        name="DHW Setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-thermometer",
    ),
    SensorEntityDescription(
        key="heatingCurve",
        name="Heating Curve",
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="heatingCurveOffset",
        name="Heating Curve Offset",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tune-vertical",
    ),
    SensorEntityDescription(
        key="compBlockTime",
        name="Compressor Block Time",
        icon="mdi:timer-lock",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="onOffCycles",
        name="Compressor On/Off Cycles",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

# =============================================================================
# Mode sensors from sHC1 (F4) - Text values
# =============================================================================
MODE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="seasonModeText",
        name="Season Mode",
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key="hcOpModeText",
        name="Heating Operation Mode",
        icon="mdi:thermostat",
    ),
)

# =============================================================================
# Operating hours from sHistory (09)
# =============================================================================
HOURS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="compressorHeatingHours",
        name="Compressor Heating Hours",
        icon="mdi:heat-pump",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="compressorCoolingHours",
        name="Compressor Cooling Hours",
        icon="mdi:snowflake",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="compressorDHWHours",
        name="Compressor DHW Hours",
        icon="mdi:water-boiler",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="boosterHeatingHours",
        name="Booster Heating Hours",
        icon="mdi:heating-coil",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="boosterDHWHours",
        name="Booster DHW Hours",
        icon="mdi:heating-coil",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="compressorHeatingStarts",
        name="Compressor Heating Starts",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="compressorCoolingStarts",
        name="Compressor Cooling Starts",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

# =============================================================================
# Fan sensors from sGlobal (FB)
# =============================================================================
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
    SensorEntityDescription(
        key="inputVentilatorPower",
        name="Input Fan Power",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outputVentilatorPower",
        name="Output Fan Power",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# =============================================================================
# Pressure sensors from sGlobal (FB)
# =============================================================================
PRESSURE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="highPressureSensor",
        name="High Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge-full",
    ),
    SensorEntityDescription(
        key="lowPressureSensor",
        name="Low Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge-low",
    ),
)

# =============================================================================
# Other sensors from sGlobal (FB)
# =============================================================================
OTHER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="flowRate",
        name="Flow Rate",
        icon="mdi:water-pump",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="relHumidity",
        name="Relative Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
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
    + MODE_SENSORS
    + HOURS_SENSORS
    + FAN_SENSORS
    + PRESSURE_SENSORS
    + OTHER_SENSORS
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
