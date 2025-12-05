"""Sensor platform for THZ Heat Pump."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import THZDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class THZSensorEntityDescription(SensorEntityDescription):
    """Describes a THZ sensor entity."""
    
    value_fn: Callable[[dict[str, Any]], Any] | None = None


# Define all temperature sensors
TEMPERATURE_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="outsideTemp",
        translation_key="outside_temp",
        name="Outside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="outsideTempFiltered",
        translation_key="outside_temp_filtered",
        name="Outside Temperature (Filtered)",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="flowTemp",
        translation_key="flow_temp",
        name="Flow Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="returnTemp",
        translation_key="return_temp",
        name="Return Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="dhwTemp",
        translation_key="dhw_temp",
        name="Hot Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="hotGasTemp",
        translation_key="hot_gas_temp",
        name="Hot Gas Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="evaporatorTemp",
        translation_key="evaporator_temp",
        name="Evaporator Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="condenserTemp",
        translation_key="condenser_temp",
        name="Condenser Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="insideTemp",
        translation_key="inside_temp",
        name="Inside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Setpoint sensors - YOUR PRIORITIES
SETPOINT_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="p01RoomTempDay",
        translation_key="room_temp_day_setpoint",
        name="Room Temp Day Setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
    THZSensorEntityDescription(
        key="p04DHWsetTempDay",
        translation_key="dhw_temp_day_setpoint",
        name="DHW Temp Day Setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-water",
    ),
    THZSensorEntityDescription(
        key="roomSetTemp",
        translation_key="room_set_temp",
        name="Room Set Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
    THZSensorEntityDescription(
        key="dhwSetTemp",
        translation_key="dhw_set_temp",
        name="DHW Set Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-water",
    ),
    THZSensorEntityDescription(
        key="heatSetTemp",
        translation_key="heat_set_temp",
        name="Heat Set Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-check",
    ),
)

# Fan stage sensors - YOUR PRIORITY
FAN_STAGE_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="p07FanStageDay",
        translation_key="fan_stage_day",
        name="Fan Stage Day",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="p08FanStageNight",
        translation_key="fan_stage_night",
        name="Fan Stage Night",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="p09FanStageStandby",
        translation_key="fan_stage_standby",
        name="Fan Stage Standby",
        icon="mdi:fan-off",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Status and mode sensors
STATUS_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="seasonMode",
        translation_key="season_mode",
        name="Season Mode",
        icon="mdi:weather-sunny",
    ),
    THZSensorEntityDescription(
        key="hcOpMode",
        translation_key="hc_operation_mode",
        name="HC Operation Mode",
        icon="mdi:thermostat",
    ),
    THZSensorEntityDescription(
        key="dhwOpMode",
        translation_key="dhw_operation_mode",
        name="DHW Operation Mode",
        icon="mdi:water-boiler",
    ),
    THZSensorEntityDescription(
        key="numberOfFaults",
        translation_key="number_of_faults",
        name="Number of Faults",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="fault0Code",
        translation_key="last_fault",
        name="Last Fault",
        icon="mdi:alert",
    ),
)

# Energy sensors - YOUR PRIORITY
ENERGY_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="sElectrHCTotal",
        translation_key="electricity_heating_total",
        name="Electricity Heating Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:lightning-bolt",
    ),
    THZSensorEntityDescription(
        key="sElectrDHWTotal",
        translation_key="electricity_dhw_total",
        name="Electricity DHW Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:lightning-bolt",
    ),
    THZSensorEntityDescription(
        key="sHeatHCTotal",
        translation_key="heat_output_heating_total",
        name="Heat Output Heating Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:fire",
    ),
    THZSensorEntityDescription(
        key="sHeatDHWTotal",
        translation_key="heat_output_dhw_total",
        name="Heat Output DHW Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:fire",
    ),
    THZSensorEntityDescription(
        key="sBoostHCTotal",
        translation_key="booster_heating_total",
        name="Booster/Heizstab Heating Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:heating-coil",
    ),
    THZSensorEntityDescription(
        key="sBoostDHWTotal",
        translation_key="booster_dhw_total",
        name="Booster/Heizstab DHW Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:heating-coil",
    ),
)

# Operating hours - YOUR PRIORITY
HOURS_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="compressorHeatingHours",
        translation_key="compressor_heating_hours",
        name="Compressor Heating Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    THZSensorEntityDescription(
        key="compressorDHWHours",
        translation_key="compressor_dhw_hours",
        name="Compressor DHW Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    THZSensorEntityDescription(
        key="boosterHeatingHours",
        translation_key="booster_heating_hours",
        name="Booster/Heizstab Heating Hours",
        icon="mdi:timer-alert",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    THZSensorEntityDescription(
        key="boosterDHWHours",
        translation_key="booster_dhw_hours",
        name="Booster/Heizstab DHW Hours",
        icon="mdi:timer-alert",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # For older firmware
    THZSensorEntityDescription(
        key="heatingHours",
        translation_key="heating_hours",
        name="Heating Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    THZSensorEntityDescription(
        key="DHWhours",
        translation_key="dhw_hours",
        name="DHW Hours",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

# Fan sensors
FAN_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="inputVentilatorSpeed",
        translation_key="input_fan_speed",
        name="Input Fan Speed",
        icon="mdi:fan",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="outputVentilatorSpeed",
        translation_key="output_fan_speed",
        name="Output Fan Speed",
        icon="mdi:fan",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="inputVentilatorPower",
        translation_key="input_fan_power",
        name="Input Fan Power",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="outputVentilatorPower",
        translation_key="output_fan_power",
        name="Output Fan Power",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Other sensors
OTHER_SENSORS: tuple[THZSensorEntityDescription, ...] = (
    THZSensorEntityDescription(
        key="relHumidity",
        translation_key="humidity",
        name="Relative Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="flowRate",
        translation_key="flow_rate",
        name="Flow Rate",
        icon="mdi:water-pump",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    THZSensorEntityDescription(
        key="compBlockTime",
        translation_key="compressor_block_time",
        name="Compressor Block Time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Combine all sensors
ALL_SENSORS = (
    TEMPERATURE_SENSORS 
    + SETPOINT_SENSORS
    + FAN_STAGE_SENSORS
    + STATUS_SENSORS 
    + ENERGY_SENSORS
    + HOURS_SENSORS
    + FAN_SENSORS 
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
        else:
            _LOGGER.debug(
                "Skipping sensor %s - not available in data", 
                description.key
            )

    async_add_entities(entities)


class THZSensor(CoordinatorEntity[THZDataUpdateCoordinator], SensorEntity):
    """Representation of a THZ sensor."""

    entity_description: THZSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: THZDataUpdateCoordinator,
        description: THZSensorEntityDescription,
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
            
        value = self.coordinator.data.get(self.entity_description.key)
        
        # Handle special value functions
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)
            
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available 
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )
