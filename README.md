# Tecalor THZ / Stiebel Eltron LWZ Heat Pump Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom component for **Tecalor THZ** and **Stiebel Eltron LWZ** heat pumps with ventilation (Lüftungsanlage).

Based on the excellent work from the [FHEM THZ module](https://wiki.fhem.de/wiki/Tecalor_THZ).

## Supported Devices

- Tecalor THZ 303/304/403/404/504 (SOL/ECO variants)
- Tecalor THZ 5.5 eco
- Stiebel Eltron LWZ 303/304/403/404/504

## Features

- **Read-Only** - No write operations to ensure safety
- Automatic firmware detection
- Temperature sensors (outside, flow, return, DHW, etc.)
- Fan stage settings
- Energy consumption (kWh)
- Operating hours (compressor, booster/Heizstab)
- Error/fault monitoring
- Pump and valve status

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → "Custom repositories"
3. Add `https://github.com/konstantinvogel/hass-thz` as Integration
4. Search for "THZ Heat Pump" and install
5. Restart Home Assistant
6. Go to Settings → Devices & Services → Add Integration → "THZ Heat Pump"

### Manual Installation

1. Copy `custom_components/thz` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services

## Configuration

During setup you'll need:
- **Serial Port**: USB port where your heat pump is connected (e.g., `/dev/ttyUSB0` or `COM3`)
- **Baud Rate**: Usually `115200` for USB connections

## Sensors

### Priority Sensors (your most important values)
| Sensor | Description |
|--------|-------------|
| THZ Outside Temperature | Current outside temperature |
| THZ Fan Stage Day | Fan stage for day mode |
| THZ Room Temp Day Setpoint | Target room temperature |
| THZ DHW Temp Day Setpoint | Target hot water temperature |
| THZ Electricity Heating Total | Total electricity consumption for heating (kWh) |
| THZ Booster Heating Total | Heizstab energy consumption (kWh) |
| THZ Compressor Heating Hours | Compressor operating hours |
| THZ Booster Heating Hours | Heizstab operating hours |
| THZ Last Fault | Last error code |

### All Available Sensors
- Temperatures: Outside, Flow, Return, DHW, Evaporator, Condenser, Inside
- Setpoints: Room temp, DHW temp, Heat temp
- Fan stages: Day, Night, Standby
- Energy: Electricity HC, Electricity DHW, Heat output, Booster consumption
- Hours: Compressor hours, Booster hours
- Status: Season mode, Operation mode, Faults

## Safety

⚠️ **This integration is READ-ONLY by design.**

No commands are sent to modify heat pump settings. This ensures your heat pump configuration cannot be accidentally changed.

## Credits

- FHEM THZ module by immi and Robert Penz
- Protocol documentation from the FHEM community

## License

GPL-3.0
