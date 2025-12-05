"""Constants for the THZ integration."""
from __future__ import annotations

from typing import Final

# Domain
DOMAIN: Final = "thz"

# Connection types
CONF_CONNECTION_TYPE: Final = "connection_type"
CONNECTION_USB: Final = "usb"
CONNECTION_IP: Final = "ip"

# Serial communication
SERIAL_PORT: Final = "/dev/ttyUSB0"
DEFAULT_BAUDRATE: Final = 115200
DEFAULT_PORT: Final = 2323
TIMEOUT: Final = 1

# Protocol bytes
DATALINKESCAPE: Final = b"\x10"  # Data Link Escape (DLE)
STARTOFTEXT: Final = b"\x02"  # Start of Text (STX)
ENDOFTEXT: Final = b"\x03"  # End of Text (ETX)

# Update intervals
DEFAULT_UPDATE_INTERVAL: Final = 60  # seconds
MIN_UPDATE_INTERVAL: Final = 5  # seconds
MAX_UPDATE_INTERVAL: Final = 86400  # seconds (24 hours)

# Cache
DEFAULT_CACHE_DURATION: Final = 60  # seconds

# Communication timing
MIN_REQUEST_INTERVAL: Final = 0.1  # seconds between requests

# Platforms
PLATFORMS: Final = ["sensor", "number", "switch", "select", "time"]

# Response headers
HEADER_GET_RESPONSE: Final = b"\x01\x00"
HEADER_SET_RESPONSE: Final = b"\x01\x80"

# Error codes from device
ERROR_TIMING: Final = b"\x01\x01"
ERROR_CRC: Final = b"\x01\x02"
ERROR_UNKNOWN_CMD: Final = b"\x01\x03"
ERROR_UNKNOWN_REG: Final = b"\x01\x04"

# Log levels for config
LOG_LEVELS: Final = {
    "Error": "error",
    "Warning": "warning",
    "Info": "info",
    "Debug": "debug",
}