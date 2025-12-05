#!/usr/bin/env python3
"""
THZ Protocol implementation for Tecalor THZ / Stiebel Eltron LWZ heat pumps.
Based on FHEM's 00_THZ.pm

This module provides the core protocol logic for communicating with THZ heat pumps.
"""
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import serial


class THZError(IntEnum):
    """THZ response error codes."""
    SUCCESS = 0x00
    CRC_ERROR = 0x02
    UNKNOWN_CMD = 0x03
    UNKNOWN_REG = 0x04


@dataclass
class THZResponse:
    """Response from THZ heat pump."""
    success: bool
    data: str | None = None
    error: THZError | None = None
    error_message: str | None = None


# Register definitions
REGISTERS = {
    "FD": {"name": "Firmware", "parse": "firmware"},
    "FB": {"name": "sGlobal (Temperaturen)", "parse": "sglobal"},
    "F3": {"name": "sDHW (Warmwasser)", "parse": "raw"},
    "F4": {"name": "sHC1 (Heizkreis 1)", "parse": "shc1"},
    "FC": {"name": "sTime (Zeit)", "parse": "time"},
    "17": {"name": "p01-p12 (Sollwerte) - alt", "parse": "p01"},
    "0A17": {"name": "p01-p12 (Sollwerte) - neu", "parse": "p01"},
    "09": {"name": "sHistory (Betriebsstunden)", "parse": "history"},
    "D1": {"name": "sLast (Fehler)", "parse": "errors"},
}


def calculate_checksum(cmd: str) -> int:
    """
    Calculate checksum for a command (FHEM style).
    
    The checksum is calculated over the header (0100) and the command bytes,
    excluding the checksum position itself and the footer (1003).
    
    Args:
        cmd: The command bytes as hex string (e.g., "FD" for firmware)
        
    Returns:
        Checksum value (0-255)
    """
    header = "0100"
    footer = "1003"
    template = header + "XX" + cmd + footer
    
    checksum = 0
    data_without_footer = template[:-4]  # Remove "1003"
    
    for i in range(0, len(data_without_footer), 2):
        if i == 4:  # Skip XX placeholder at position 4-5
            continue
        byte_hex = data_without_footer[i:i+2]
        if byte_hex != "XX":
            checksum += int(byte_hex, 16)
    
    return checksum % 256


def escape_data(data: str) -> str:
    """
    Apply escape sequences to data before sending.
    
    THZ protocol escapes:
    - 0x10 -> 0x10 0x10
    - 0x2B -> 0x2B 0x18
    
    Args:
        data: Hex string to escape
        
    Returns:
        Escaped hex string
    """
    result = ""
    i = 0
    while i < len(data):
        if i + 1 < len(data):
            two_chars = data[i:i+2]
            if two_chars == "10":
                result += "1010"
                i += 2
                continue
            elif two_chars == "2B":
                result += "2B18"
                i += 2
                continue
        result += data[i]
        i += 1
    return result


def unescape_data(data: str) -> str:
    """
    Remove escape sequences from received data.
    
    Args:
        data: Hex string with escape sequences
        
    Returns:
        Unescaped hex string
    """
    return data.replace("1010", "10").replace("2B18", "2B")


def build_command(register: str) -> str:
    """
    Build a complete command for a register.
    
    Format: 0100 + checksum(2) + register + 1003
    
    Args:
        register: Register address as hex string (e.g., "FD")
        
    Returns:
        Complete command as hex string
    """
    checksum = calculate_checksum(register)
    data_to_escape = f"{checksum:02X}" + register
    escaped = escape_data(data_to_escape)
    return "0100" + escaped + "1003"


def parse_response(data_hex: str) -> THZResponse:
    """
    Parse a raw response from the heat pump.
    
    Args:
        data_hex: Raw response as hex string
        
    Returns:
        THZResponse object
    """
    if not data_hex or len(data_hex) < 8:
        return THZResponse(success=False, error_message="Response too short")
    
    # Unescape first
    data_hex = unescape_data(data_hex.upper())
    
    header = data_hex[:4]
    
    if header == "0100":
        # Success - extract data: 0100 + checksum(2) + data + 1003
        return THZResponse(success=True, data=data_hex[6:-4])
    elif header == "0102":
        return THZResponse(success=False, error=THZError.CRC_ERROR, error_message="CRC Error")
    elif header == "0103":
        return THZResponse(success=False, error=THZError.UNKNOWN_CMD, error_message="Unknown command")
    elif header == "0104":
        return THZResponse(success=False, error=THZError.UNKNOWN_REG, error_message="Unknown register")
    else:
        return THZResponse(success=False, error_message=f"Unknown header: {header}")


def parse_temp(hex_val: str, signed: bool = True) -> float:
    """
    Parse a temperature value from hex string.
    
    Args:
        hex_val: 4-character hex string representing temperature * 10
        signed: Whether to interpret as signed value
        
    Returns:
        Temperature in degrees Celsius
    """
    val = int(hex_val, 16)
    if signed and val > 32767:
        val = val - 65536
    return val / 10


def parse_firmware(data_hex: str) -> dict[str, Any]:
    """Parse firmware register (FD)."""
    result = {}
    try:
        if len(data_hex) >= 6:
            version_hex = data_hex[2:6]
            version_raw = int(version_hex, 16)
            major = version_raw // 100
            minor = version_raw % 100
            result["version"] = f"{major}.{minor:02d}"
            result["version_raw"] = version_raw
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    return result


def parse_sglobal(data_hex: str) -> dict[str, Any]:
    """
    Parse sGlobal (FB) register - main sensor data.
    
    Structure (firmware 7.02):
    - Pos 0-3: collectorTemp
    - Pos 4-7: outsideTemp
    - Pos 8-11: flowTemp
    - Pos 12-15: returnTemp
    - Pos 16-19: hotGasTemp
    - Pos 20-23: dhwTemp
    - Pos 24-27: flowTempHC2
    - Pos 28-31: insideTemp
    - Pos 32-35: evaporatorTemp
    - Pos 36-39: condenserTemp
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 4:
            result["collector_temp"] = parse_temp(d[0:4])
        if len(d) >= 8:
            result["outside_temp"] = parse_temp(d[4:8])
        if len(d) >= 12:
            result["flow_temp"] = parse_temp(d[8:12])
        if len(d) >= 16:
            result["return_temp"] = parse_temp(d[12:16])
        if len(d) >= 20:
            result["hot_gas_temp"] = parse_temp(d[16:20])
        if len(d) >= 24:
            result["dhw_temp"] = parse_temp(d[20:24])
        if len(d) >= 28:
            result["flow_temp_hc2"] = parse_temp(d[24:28])
        if len(d) >= 32:
            inside = parse_temp(d[28:32])
            result["inside_temp"] = inside
            result["inside_temp_valid"] = -50 <= inside <= 50
        if len(d) >= 36:
            result["evaporator_temp"] = parse_temp(d[32:36])
        if len(d) >= 40:
            result["condenser_temp"] = parse_temp(d[36:40])
        
        # Fan speeds (positions vary by firmware)
        if len(d) >= 66:
            try:
                result["output_fan_speed"] = int(d[58:62], 16)
                result["input_fan_speed"] = int(d[62:66], 16)
            except ValueError:
                pass
                
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_shc1(data_hex: str) -> dict[str, Any]:
    """Parse sHC1 (F4) register - heating circuit 1."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 4:
            result["flow_temp_set"] = int(d[0:4], 16) / 10
        if len(d) >= 8:
            result["room_temp_set"] = int(d[4:8], 16) / 10
        if len(d) >= 12:
            result["room_temp"] = int(d[8:12], 16) / 10
        if len(d) >= 80:
            result["on_off_cycles"] = int(d[76:80], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_p01(data_hex: str) -> dict[str, Any]:
    """Parse p01-p12 register (17) - setpoints."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 4:
            result["p01_room_temp_day"] = int(d[0:4], 16) / 10
        if len(d) >= 8:
            result["p02_room_temp_night"] = int(d[4:8], 16) / 10
        if len(d) >= 16:
            result["p04_dhw_temp_day"] = int(d[12:16], 16) / 10
        if len(d) >= 28:
            result["p07_fan_stage_day"] = int(d[24:26], 16)
        if len(d) >= 30:
            result["p08_fan_stage_night"] = int(d[26:28], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_history(data_hex: str) -> dict[str, Any]:
    """Parse sHistory (09) register - operating hours."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 4:
            result["compressor_heating_hours"] = int(d[0:4], 16)
        if len(d) >= 8:
            result["compressor_cooling_hours"] = int(d[4:8], 16)
        if len(d) >= 12:
            result["compressor_dhw_hours"] = int(d[8:12], 16)
        if len(d) >= 16:
            result["booster_dhw_hours"] = int(d[12:16], 16)
        if len(d) >= 20:
            result["booster_heating_hours"] = int(d[16:20], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_time(data_hex: str) -> dict[str, Any]:
    """
    Parse sTime (FC) register.
    
    Structure (FCtime206 from FHEM):
    - Byte 0 (pos 0-1): Command echo (FC)
    - Byte 1 (pos 2-3): Weekday (1=Mon, 7=Sun)
    - Byte 2-3 (pos 4-7): Hour (as hex, e.g., 14 = 0x0E but stored as 14)
    - Byte 4-5 (pos 8-11): Minutes
    - Byte 6-7 (pos 12-15): Seconds
    - Byte 8-9 (pos 16-19): Year (2-digit, e.g., 25 for 2025)
    - Byte 10-11 (pos 20-23): Padding/unknown
    - Byte 12-13 (pos 24-27): Month
    - Byte 14-15 (pos 28-31): Day
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo (FC)
        
        if len(d) >= 2:
            result["weekday"] = int(d[0:2], 16)
        if len(d) >= 6:
            result["hour"] = int(d[2:6], 16)  # 2 bytes
        if len(d) >= 10:
            result["minute"] = int(d[6:10], 16)  # 2 bytes
        if len(d) >= 14:
            result["second"] = int(d[10:14], 16)  # 2 bytes
        if len(d) >= 18:
            year_short = int(d[14:18], 16)  # 2-digit year
            result["year"] = 2000 + year_short if year_short < 100 else year_short
        # Bytes 18-21 seem to be padding/unknown (skip)
        if len(d) >= 26:
            result["month"] = int(d[22:26], 16)
        if len(d) >= 30:
            result["day"] = int(d[26:30], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_errors(data_hex: str) -> dict[str, Any]:
    """Parse sLast (D1) register - error history."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 2:
            result["num_faults"] = int(d[0:2], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


# Parser registry
PARSERS = {
    "firmware": parse_firmware,
    "sglobal": parse_sglobal,
    "shc1": parse_shc1,
    "p01": parse_p01,
    "history": parse_history,
    "time": parse_time,
    "errors": parse_errors,
}


class THZConnection:
    """
    Connection handler for THZ heat pump.
    
    Implements the 3-step handshake protocol:
    - Step 0: Send STX (0x02) -> Expect DLE (0x10)
    - Step 1: Send command -> Expect DLE STX (0x10 0x02)
    - Step 2: Send DLE (0x10) -> Read response data
    """
    
    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 3.0,
        write_timeout: float = 2.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self._serial: serial.Serial | None = None
    
    def connect(self) -> None:
        """Open serial connection."""
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
        )
        time.sleep(0.2)
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
    
    def disconnect(self) -> None:
        """Close serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._serial is not None and self._serial.is_open
    
    def send_command(self, register: str) -> THZResponse:
        """
        Send a command and return the response.
        
        Args:
            register: Register address as hex string
            
        Returns:
            THZResponse object
        """
        if not self._serial:
            return THZResponse(success=False, error_message="Not connected")
        
        cmd = build_command(register)
        
        # Clear buffers
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        
        # Step 0: Send STX
        self._serial.write(bytes.fromhex("02"))
        self._serial.flush()
        time.sleep(0.1)
        
        response = self._serial.read(self._serial.in_waiting) if self._serial.in_waiting else b''
        if response != b'\x10':
            return THZResponse(
                success=False,
                error_message=f"Step 0 failed: expected 10, got {response.hex() if response else 'NONE'}"
            )
        
        # Step 1: Send command
        self._serial.write(bytes.fromhex(cmd))
        self._serial.flush()
        time.sleep(0.2)
        
        response = self._serial.read(self._serial.in_waiting) if self._serial.in_waiting else b''
        if response not in [b'\x10\x02', b'\x02', b'\x10']:
            return THZResponse(
                success=False,
                error_message=f"Step 1 failed: expected 1002, got {response.hex() if response else 'NONE'}"
            )
        
        if response == b'\x10':
            time.sleep(0.05)
            self._serial.read(1)  # Read the 02
        
        # Step 2: Send DLE
        self._serial.write(bytes.fromhex("10"))
        self._serial.flush()
        
        # Read response
        time.sleep(0.3)
        data = bytearray()
        start = time.time()
        while time.time() - start < 2.0:
            if self._serial.in_waiting:
                chunk = self._serial.read(self._serial.in_waiting)
                data.extend(chunk)
                data_hex = data.hex().upper()
                if data_hex.startswith("01") and data_hex.endswith("1003"):
                    break
            time.sleep(0.01)
        
        # Send final DLE
        self._serial.write(bytes.fromhex("10"))
        self._serial.flush()
        
        if not data:
            return THZResponse(success=False, error_message="No response data")
        
        return parse_response(data.hex())
    
    def read_register(self, register: str) -> dict[str, Any]:
        """
        Read and parse a register.
        
        Args:
            register: Register address as hex string
            
        Returns:
            Parsed data dictionary
        """
        response = self.send_command(register)
        
        if not response.success:
            return {"error": response.error_message}
        
        reg_info = REGISTERS.get(register, {})
        parser_name = reg_info.get("parse", "raw")
        
        if parser_name == "raw":
            return {"raw_data": response.data}
        
        parser = PARSERS.get(parser_name)
        if parser and response.data:
            return parser(response.data)
        
        return {"raw_data": response.data}
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
