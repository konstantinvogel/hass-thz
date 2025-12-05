"""Constants for the THZ integration."""
from typing import Final

DOMAIN: Final = "hass_thz"

# Configuration
CONF_SERIAL_PORT: Final = "serial_port"
CONF_BAUDRATE: Final = "baudrate"
CONF_FIRMWARE: Final = "firmware"

# Defaults
DEFAULT_BAUDRATE: Final = 115200
DEFAULT_FIRMWARE: Final = "5.39"

# Firmware options
FIRMWARE_OPTIONS: Final = ["2.06", "2.14", "4.39", "5.39", "5.39technician"]

# Polling intervals (seconds)
DEFAULT_SCAN_INTERVAL: Final = 60

# Protocol constants
HEADER_GET: Final = "0100"
HEADER_SET: Final = "0180"
FOOTER: Final = "1003"

# Operation modes
OP_MODES: Final = {
    "1": "standby",
    "11": "automatic", 
    "3": "DAYmode",
    "4": "setback",
    "5": "DHWmode",
    "14": "manual",
    "0": "emergency"
}

OP_MODES_HC: Final = {
    "1": "normal",
    "2": "setback", 
    "3": "standby",
    "4": "restart",
    "5": "restart"
}

SEASON_MODES: Final = {
    "01": "winter",
    "02": "summer"
}

# Fault codes mapping
FAULT_CODES: Final = {
    0: "n.a.",
    1: "F01_AnodeFault",
    2: "F02_SafetyTempDelimiterEngaged",
    3: "F03_HighPressureGuardFault",
    4: "F04_LowPressureGuardFault",
    5: "F05_OutletFanFault",
    6: "F06_InletFanFault",
    7: "F07_MainOutputFanFault",
    11: "F11_LowPressureSensorFault",
    12: "F12_HighPressureSensorFault",
    15: "F15_DHW_TemperatureFault",
    17: "F17_DefrostingDurationExceeded",
    20: "F20_SolarSensorFault",
    21: "F21_OutsideTemperatureSensorFault",
    22: "F22_HotGasTemperatureFault",
    23: "F23_CondenserTemperatureSensorFault",
    24: "F24_EvaporatorTemperatureSensorFault",
    26: "F26_ReturnTemperatureSensorFault",
    28: "F28_FlowTemperatureSensorFault",
    29: "F29_DHW_TemperatureSensorFault",
    30: "F30_SoftwareVersionFault",
    31: "F31_RAMfault",
    32: "F32_EEPromFault",
    33: "F33_ExtractAirHumiditySensor",
    34: "F34_FlowSensor",
    35: "F35_minFlowCooling",
    36: "F36_MinFlowRate",
    37: "F37_MinWaterPressure",
    40: "F40_FloatSwitch",
    50: "F50_SensorHeatPumpReturn",
    51: "F51_SensorHeatPumpFlow",
    52: "F52_SensorCondenserOutlet"
}
