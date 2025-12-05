"""THZ Device communication module.

This module handles all communication with the Stiebel Eltron / Tecalor THZ heat pump
via USB/Serial or TCP/IP connection.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import time
from typing import TYPE_CHECKING, Any

import serial  # pyright: ignore[reportMissingModuleSource]

from .const import (
    DATALINKESCAPE,
    DEFAULT_BAUDRATE,
    DEFAULT_CACHE_DURATION,
    ENDOFTEXT,
    MIN_REQUEST_INTERVAL,
    STARTOFTEXT,
    TIMEOUT,
)
from .register_maps.register_map_manager import (
    RegisterMapManager,
    RegisterMapManagerWrite,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]

_LOGGER = logging.getLogger(__name__)

class THZDevice:
    """Represents the connection to a THZ heat pump.

    This class handles all low-level communication with the heat pump,
    including serial/USB and TCP/IP connections, protocol handling,
    and register read/write operations.

    Attributes:
        connection: Connection type ('usb' or 'ip').
        port: Serial port path for USB connections.
        host: Hostname/IP for network connections.
        tcp_port: TCP port number for network connections.
        firmware_version: Detected firmware version of the device.
    """

    def __init__(
        self,
        connection: str = "usb",
        port: str | None = None,
        host: str | None = None,
        tcp_port: int | None = None,
        baudrate: int = DEFAULT_BAUDRATE,
        read_timeout: float = TIMEOUT,
    ) -> None:
        """Initialize THZ device configuration.

        Note: This only sets up configuration. Call async_initialize()
        to actually connect to the device.

        Args:
            connection: Connection type ('usb' or 'ip').
            port: Serial port path (e.g., '/dev/ttyUSB0').
            host: Hostname or IP address for network connection.
            tcp_port: TCP port number for network connection.
            baudrate: Baud rate for serial connection.
            read_timeout: Read timeout in seconds.
        """
        self.connection = connection
        self.port = port
        self.host = host
        self.tcp_port = tcp_port
        self.baudrate = baudrate
        self.read_timeout = read_timeout
        self._initialized = False

        # Connection handle (serial or socket)
        self._ser: serial.Serial | socket.socket | None = None

        # Firmware and register maps
        self._firmware_version: str | None = None
        self._register_map_manager: RegisterMapManager | None = None
        self._write_register_map_manager: RegisterMapManagerWrite | None = None

        # Cache for block reads
        self._cache: dict[str, tuple[float, bytes]] = {}
        self._cache_duration = DEFAULT_CACHE_DURATION

        # Thread-safety lock for concurrent access
        self.lock = asyncio.Lock()
        self._last_access = 0.0
        self._min_interval = MIN_REQUEST_INTERVAL

    @property
    def ser(self) -> serial.Serial | socket.socket | None:
        """Return the underlying connection object."""
        return self._ser

    @ser.setter
    def ser(self, value: serial.Serial | socket.socket | None) -> None:
        """Set the underlying connection object."""
        self._ser = value

    async def async_initialize(self, hass: HomeAssistant) -> None:
        """Open connection and initialize firmware-dependent data structures.

        Args:
            hass: The Home Assistant instance.

        Raises:
            ValueError: If the connection type is unknown.
            RuntimeError: If firmware version cannot be read.
        """
        _LOGGER.debug("Initializing THZ device (%s)", self.connection)

        # Open connection
        if self.connection == "usb":
            self._connect_serial()
        elif self.connection == "ip":
            self._connect_tcp()
        else:
            raise ValueError(f"Unknown connection type: {self.connection}")

        # Read firmware version (runs synchronously in executor)
        self._firmware_version = await hass.async_add_executor_job(
            self.read_firmware_version
        )
        _LOGGER.info("Firmware version detected: %s", self._firmware_version)

        # Load firmware-specific register maps
        self._register_map_manager = RegisterMapManager(self._firmware_version)
        self._write_register_map_manager = RegisterMapManagerWrite(self._firmware_version)

        self._cache = {}
        self._cache_duration = DEFAULT_CACHE_DURATION
        self._initialized = True

    @property
    def register_map_manager(self) -> RegisterMapManager | None:
        """Return the register map manager."""
        return self._register_map_manager

    @property
    def write_register_map_manager(self) -> RegisterMapManagerWrite | None:
        """Return the write register map manager."""
        return self._write_register_map_manager

    def _connect_serial(self) -> None:
        """Open USB/Serial connection."""
        _LOGGER.debug("Opening serial connection: %s @ %d baud", self.port, self.baudrate)
        self._ser = serial.Serial(
            self.port,
            baudrate=self.baudrate,
            timeout=self.read_timeout,
        )

    def _connect_tcp(self) -> None:
        """Connect via TCP/IP (ser2net)."""
        _LOGGER.debug("Opening TCP connection: %s:%s", self.host, self.tcp_port)
        self._ser = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._ser.settimeout(self.read_timeout)
        self._ser.connect((self.host, self.tcp_port))

    def read_block_cached(
        self, block: bytes | str, cache_duration: float = DEFAULT_CACHE_DURATION
    ) -> bytes:
        """Read a block with caching support.

        Args:
            block: Block identifier (bytes or hex string).
            cache_duration: How long to cache results in seconds.

        Returns:
            Raw bytes read from the device.
        """
        now = time.time()
        block_key = block.hex() if isinstance(block, bytes) else block

        if block_key in self._cache:
            ts, data = self._cache[block_key]
            if now - ts < cache_duration:
                return data

        data = self.read_block(block, "get")
        self._cache[block_key] = (now, data)
        return data

    def send_request(self, telegram: bytes) -> bytes:
        """Send a request and receive the response.

        Implements the THZ protocol handshake and data exchange.

        Args:
            telegram: The telegram bytes to send.

        Returns:
            Raw response bytes from the device.

        Raises:
            ValueError: If handshake fails or response is invalid.
        """
        timeout = self.read_timeout
        data = bytearray()

        # 1. Send greeting (0x02)
        self._write_bytes(STARTOFTEXT)

        # 2. Wait for 0x10 response
        response = self._read_exact(1, timeout)
        if response != DATALINKESCAPE:
            raise ValueError(f"Handshake 1 failed, received: {response.hex()}")

        # 3. Send telegram
        self._reset_input_buffer()
        self._write_bytes(telegram)

        # 4. Wait for 0x10 0x02 response
        response = self._read_exact(2, timeout)
        if response != DATALINKESCAPE + STARTOFTEXT:
            raise ValueError(f"Handshake 2 failed, received: {response.hex()}")

        # 5. Send confirmation (0x10)
        self._write_bytes(DATALINKESCAPE)

        # 6. Receive data telegram until 0x10 0x03
        start_time = time.time()
        while time.time() - start_time < timeout:
            chunk = self._read_available()
            if chunk:
                data.extend(chunk)
                if len(data) >= 8 and data[-2:] == DATALINKESCAPE + ENDOFTEXT:
                    break
            else:
                time.sleep(0.01)

        if not (len(data) >= 8 and data[-2:] == DATALINKESCAPE + ENDOFTEXT):
            raise ValueError("No valid response after data request")

        # 7. End communication
        self._write_bytes(STARTOFTEXT)
        return bytes(data)

    def _write_bytes(self, data: bytes) -> None:
        """Send bytes via serial or TCP.

        Args:
            data: Bytes to send.
        """
        if hasattr(self._ser, "send"):  # TCP Socket
            self._ser.send(data)
        else:  # Serial
            self._ser.write(data)
            self._ser.flush()

    def _read_exact(self, size: int, timeout: float) -> bytes:
        """Read exactly n bytes.

        Args:
            size: Number of bytes to read.
            timeout: Timeout in seconds.

        Returns:
            The bytes read.
        """
        end_time = time.time() + timeout
        buf = bytearray()
        while len(buf) < size and time.time() < end_time:
            chunk = self._read_available()
            if chunk:
                buf.extend(chunk)
            else:
                time.sleep(0.01)
        return bytes(buf)

    def _read_available(self) -> bytes:
        """Read available bytes from connection.

        Returns:
            Available bytes or empty bytes if none available.
        """
        if hasattr(self._ser, "recv"):  # TCP Socket
            try:
                self._ser.setblocking(False)
                return self._ser.recv(1024)
            except BlockingIOError:
                return b""
        else:
            waiting = getattr(self._ser, "in_waiting", 0)
            if waiting > 0:
                return self._ser.read(waiting)
            return b""

    def _reset_input_buffer(self) -> None:
        """Clear input buffer if possible."""
        if hasattr(self._ser, "reset_input_buffer"):
            self._ser.reset_input_buffer()
        # TCP has no input buffer, so no reset needed

    def close(self) -> None:
        """Close the connection."""
        if self._ser:
            self._ser.close()

    def thz_checksum(self, data: bytes) -> bytes:
        """Calculate THZ protocol checksum.

        Args:
            data: Data bytes to checksum (byte at index 2 is excluded).

        Returns:
            Single byte checksum.
        """
        checksum = sum(b for i, b in enumerate(data) if i != 2)
        checksum = checksum % 256
        return bytes([checksum])

    def unescape(self, data: bytes) -> bytes:
        """Unescape protocol escape sequences.

        Args:
            data: Raw data with escape sequences.

        Returns:
            Unescaped data.
        """
        # 0x10 0x10 -> 0x10
        data = data.replace(DATALINKESCAPE + DATALINKESCAPE, DATALINKESCAPE)
        # 0x2B 0x18 -> 0x2B
        data = data.replace(b"\x2B\x18", b"\x2B")
        return data

    def decode_response(self, data: bytes) -> bytes:
        """Decode and validate a response from the device.

        Args:
            data: Raw response bytes.

        Returns:
            Validated payload bytes.

        Raises:
            ValueError: If response is invalid or contains an error code.
        """
        if len(data) < 6:
            raise ValueError(f"Response too short: {data.hex()}")

        data = self.unescape(data)

        # Header is the first 2 bytes
        header = data[0:2]
        if header in (b"\x01\x80", b"\x01\x00"):
            # Normal response: 0x01 0x80 for "set", 0x01 0x00 for "get"
            crc = data[2]
            payload = data[3:-2]

            # Verify CRC
            check_data = data[:2] + b"\x00" + payload
            checksum_bytes = self.thz_checksum(check_data)
            calc_crc = checksum_bytes[0]
            if calc_crc != crc:
                raise ValueError(
                    f"CRC error in response. Expected {crc:02X}, calculated {calc_crc:02X}"
                )

            return checksum_bytes + payload
        elif header == b"\x01\x01":
            raise ValueError("Timing issue from device")
        elif header == b"\x01\x02":
            raise ValueError("CRC error in request")
        elif header == b"\x01\x03":
            raise ValueError("Command not recognized")
        elif header == b"\x01\x04":
            raise ValueError("Unknown register request")
        else:
            raise ValueError(f"Unknown response: {data.hex()}")

    def read_write_register(
        self,
        addr_bytes: bytes,
        get_or_set: str = "get",
        payload_to_deliver: bytes = b"",
    ) -> bytes:
        """Read or write a register.

        Args:
            addr_bytes: Register address (e.g., b'\\xFB' for global status).
            get_or_set: 'get' for read, 'set' for write.
            payload_to_deliver: Data to write (only for 'set').

        Returns:
            Response payload bytes.
        """
        header = b"\x01\x00" if get_or_set == "get" else b"\x01\x80"
        footer = DATALINKESCAPE + ENDOFTEXT

        checksum = self.thz_checksum(
            header + b"\x00" + addr_bytes + payload_to_deliver
        )
        telegram = self.construct_telegram(
            addr_bytes + payload_to_deliver, header, footer, checksum
        )
        raw_response = self.send_request(telegram)
        payload = self.decode_response(raw_response)
        return payload

    def construct_telegram(
        self,
        addr_bytes: bytes,
        header: bytes,
        footer: bytes,
        checksum: bytes,
    ) -> bytes:
        """Construct a telegram for the THZ device.

        Args:
            addr_bytes: Address and optional payload bytes.
            header: Protocol header bytes.
            footer: Protocol footer bytes.
            checksum: Calculated checksum.

        Returns:
            Complete telegram ready to send.
        """
        return header + checksum + addr_bytes + footer

    def read_firmware_version(self) -> str:
        """Read the firmware version from the device.

        Returns:
            Firmware version as string.

        Raises:
            RuntimeError: If firmware cannot be read.
        """
        try:
            value_raw = self.read_value(b"\xFD", "get", 2, 2)
            firmware_version = int.from_bytes(value_raw, byteorder="big", signed=False)
            _LOGGER.debug(f"Firmware-Version gelesen: {firmware_version}")
            return str(firmware_version)
        except Exception as e:
            # Fehlerbehandlung oder Logging, falls z. B. keine Verbindung oder ungültige Antwort
            raise RuntimeError(f"Firmware-Version konnte nicht gelesen werden: {e}")
        

    def read_value(self, addr_bytes: bytes, get_or_set: str, offset: int, length: int) -> bytes:
        """
        Reads a value from the THZ device.
        addr_bytes: bytes (e.g. b'\xFB')
        get_or_set: "get" or "set"
        Returns: byte value read from the device
        """
        response = self.read_write_register(addr_bytes, get_or_set)
        # _LOGGER.info(f"Antwort von Wärmepumpe: {response.hex()}")
        value_raw = response[offset: offset + length]
        # _LOGGER.info(f"Gelesener Wert (Offset {offset}, Length {length}): {value_raw.hex()}")
        return value_raw
    
    def write_value(self, addr_bytes: bytes, value: bytes) -> None:
        """
        Writes a value to the THZ device.
        addr_bytes: bytes (e.g. b'\xFB')
        value: integer value to write
        """
        self.read_write_register(addr_bytes, "set", value)
        _LOGGER.debug(f"Wert {value} an Adresse {addr_bytes.hex()} geschrieben.")
    
    def read_block(self, addr_bytes: bytes, get_or_set: str) -> bytes:
        """
        Reads a value from the THZ device.
        addr_bytes: bytes (e.g. "\xFB")
        get_or_set: "get" or "set"
        Returns: block read from the device
        """
        response = self.read_write_register(addr_bytes, get_or_set)
        return response

    @property
    def firmware_version(self) -> str:
        return self._firmware_version
    
    @property
    def available_reading_blocks(self) -> list[str]:
        if self.register_map_manager:
            return list(self.register_map_manager.get_all_registers().keys())
        return []

# from homeassistant.helpers.update_coordinator import DataUpdateCoordinator # pyright: ignore[reportMissingImports, reportMissingModuleSource]
# class THZCoordinator(DataUpdateCoordinator):
#     def __init__(self, hass, device, refresh_interval: int):
#         super().__init__(
#             hass,
#             _LOGGER,
#             name="THZ Coordinator",
#             update_interval= time.timedelta(seconds=refresh_interval),
#         )
#         self.device = device

#     async def _async_update_data(self):
#         return await self.device.read_all()



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    dev = THZDevice('/dev/ttyUSB0')



