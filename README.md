# Stiebel Eltron LWZ / Tecalor THZ Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration to connect Stiebel Eltron LWZ or Tecalor THZ heat pumps.

## Features

- USB or TCP/IP (ser2net) connection support
- Sensor readings (temperatures, pressures, states)
- Writable settings (temperatures, operating modes)
- Multiple firmware versions supported

## Confirmed Working Devices

| Model | Firmware |
|-------|----------|
| LWZ5  | 7.59     |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/konstantinvogel/hass-thz` with category "Integration"
6. Click "Add"
7. Search for "Stiebel Eltron" and install

### Manual Installation

1. Copy the `custom_components/thz` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Stiebel Eltron LWZ / Tecalor THZ"
4. Follow the setup wizard

### Connection Types

- **USB**: Direct serial connection (e.g., `/dev/ttyUSB0`)
- **TCP/IP**: Network connection via ser2net (e.g., `192.168.1.100:5555`)

## Credits

Based on the [FHEM THZ module](https://wiki.fhem.de/wiki/THZ) by Immi.

## Disclaimer

⚠️ **Use at your own risk.** This integration modifies heat pump settings. Incorrect settings may cause damage or unsafe operation. The authors are not responsible for any damage.

## License

See [LICENSE](LICENSE) file.

