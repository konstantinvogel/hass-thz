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
    "F3": {"name": "sDHW (Warmwasser)", "parse": "dhw"},
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
    
    Based on FHEM 00_THZ.pm FBglob206 parsing for firmware 2.06/7.02.
    Positions are hex char positions after FB prefix (each value = 4 hex chars = 2 bytes).
    
    Verified with real device data (Firmware 7.02):
    === TEMPERATURES (4 hex chars each, signed word / 10) ===
    - 0-3: collectorTemp (-60.0 = not connected)
    - 4-7: outsideTemp (4.2°C)
    - 8-11: flowTemp (27.9°C)
    - 12-15: returnTemp (27.8°C)
    - 16-19: hotGasTemp (55.9°C)
    - 20-23: dhwTemp (44.9°C)
    - 24-27: flowTempHC2 (0x8001 = -3276.7 = not installed)
    - 28-31: insideTemp (0xFDA8 = -60.0 = no sensor)
    - 32-35: evaporatorTemp (1.2°C)
    - 36-39: condenserTemp (29.6°C)
    
    === STATUS BYTES (1 byte each, starting at pos 40) ===
    - 40-41: status byte 0
    - 42-43: status byte 1 (pumps/valves)
    - 44-45: status byte 2 (compressor/boosters)
    - 46-47: status byte 3
    
    === VENTILATOR DATA (starting around pos 72) ===
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo (FB)
        
        # Temperatures (each 4 hex chars = 2 bytes, signed, /10 for °C)
        if len(d) >= 4:
            temp = parse_temp(d[0:4])
            if temp > -100:  # Valid sensor
                result["collectorTemp"] = temp
        if len(d) >= 8:
            result["outsideTemp"] = parse_temp(d[4:8])
        if len(d) >= 12:
            result["flowTemp"] = parse_temp(d[8:12])
        if len(d) >= 16:
            result["returnTemp"] = parse_temp(d[12:16])
        if len(d) >= 20:
            result["hotGasTemp"] = parse_temp(d[16:20])
        if len(d) >= 24:
            result["dhwTemp"] = parse_temp(d[20:24])
        if len(d) >= 28:
            temp = parse_temp(d[24:28])
            if temp > -1000:  # 0x8001 = -32767 = not installed
                result["flowTempHC2"] = temp
        if len(d) >= 32:
            inside = parse_temp(d[28:32])
            if inside > -60:  # 0xFDA8 = -60.0 = no sensor
                result["insideTemp"] = inside
        if len(d) >= 36:
            result["evaporatorTemp"] = parse_temp(d[32:36])
        if len(d) >= 40:
            result["condenserTemp"] = parse_temp(d[36:40])
        
        # Status bytes at position 40-47 (single bytes)
        # Real data shows: pos 40=0x10, 42=0x08, 44=0x17, 46=0x00
        if len(d) >= 48:
            byte40 = int(d[40:42], 16)
            byte42 = int(d[42:44], 16)
            byte44 = int(d[44:46], 16)
            byte46 = int(d[46:48], 16)
            
            # Based on FHEM documentation and real data analysis:
            # byte44 (0x17 = 0b00010111): compressor and boosters
            result["compressor"] = (byte44 & 0x01) != 0
            result["boosterStage1"] = (byte44 & 0x02) != 0
            result["boosterStage2"] = (byte44 & 0x04) != 0
            result["boosterStage3"] = (byte44 & 0x08) != 0
            
            # byte42 (0x08 = 0b00001000): pumps and valves
            result["heatingCircuitPump"] = (byte42 & 0x01) != 0
            result["dhwPump"] = (byte42 & 0x02) != 0
            result["diverterValve"] = (byte42 & 0x04) != 0
            result["heatPipeValve"] = (byte42 & 0x08) != 0
            
            # byte40: mixer status
            result["mixerClosed"] = (byte40 & 0x01) != 0
            result["mixerOpen"] = (byte40 & 0x02) != 0
        
        # Ventilator data - check FHEM for exact positions
        # From real data: pos 72-73 = 0x39 (57), pos 82-83 = 0x03, pos 84-85 = 0x2A (42)
        # These seem to be ventilator speeds/power
        if len(d) >= 74:
            result["mainVentilatorPower"] = int(d[72:74], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_shc1(data_hex: str) -> dict[str, Any]:
    """
    Parse sHC1 (F4) register - heating circuit 1.
    
    Based on FHEM 00_THZ.pm F4hc1 parsing.
    Positions are in hex chars (0-based) after F4 prefix.
    
    Verified with real device data (Firmware 7.02):
    - 0-3: outsideTemp (4.2°C)
    - 8-11: returnTemp (28.0°C)
    - 16-19: flowTemp (28.2°C)
    - 24-27: heatSetTemp (28.0°C)
    - 28-31: heatTemp (0.0°C)
    - 32-33: onHysteresisNo (2)
    - 34-35: offHysteresisNo (1)
    - 52-55: roomSetTemp (20.5°C) - 0x00CD = 205 / 10
    - 64-67: insideTempRC (20.5°C) - 0x00CD = 205 / 10
    - 76-79: onOffCycles (23)
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo (F4)
        
        # outsideTemp at position 0-3
        if len(d) >= 4:
            result["hc1OutsideTemp"] = parse_temp(d[0:4])
            
        # returnTemp at position 8-11
        if len(d) >= 12:
            result["hc1ReturnTemp"] = parse_temp(d[8:12])
        
        # flowTemp at position 16-19
        if len(d) >= 20:
            result["hc1FlowTemp"] = parse_temp(d[16:20])
            
        # heatSetTemp at position 24-27
        if len(d) >= 28:
            result["heatSetTemp"] = parse_temp(d[24:28])
            
        # heatTemp at position 28-31
        if len(d) >= 32:
            result["heatTemp"] = parse_temp(d[28:32])
        
        # Hysteresis numbers at 32-33, 34-35
        if len(d) >= 36:
            result["onHysteresisNo"] = int(d[32:34], 16)
            result["offHysteresisNo"] = int(d[34:36], 16)
        
        # roomSetTemp at position 52-55 (0x00CD = 205 / 10 = 20.5°C)
        if len(d) >= 56:
            result["roomSetTemp"] = parse_temp(d[52:56])
            
        # insideTempRC at position 64-67 (0x00CD = 205 / 10 = 20.5°C)
        if len(d) >= 68:
            result["insideTempRC"] = parse_temp(d[64:68])
            
        # On/off cycles at position 76-79
        if len(d) >= 80:
            result["onOffCycles"] = int(d[76:80], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_dhw(data_hex: str) -> dict[str, Any]:
    """
    Parse sDHW (F3) register - domestic hot water.
    
    Real data structure (verified against FW 7.02):
    Positions are hex char positions AFTER skipping F3 prefix.
    Each temperature value is 2 bytes = 4 hex chars.
    
    Structure:
    - 0-3: dhwTemp (signed/10) - current DHW temperature
    - 4-7: outsideTemp (signed/10) - outside temperature  
    - 8-11: dhwSetTemp (signed/10) - target DHW temperature
    - 12-15: compBlockTime (signed int)
    - 16-19: unknown
    - 20-23: heatBlockTime related
    - 24-25: dhwBoosterStage
    - 28-29: pasteurisationMode
    - 30-31: dhwOpMode (1=normal, 2=setback, 3=standby)
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo (F3)
        
        # dhwTemp at position 0-3 (current DHW temperature)
        if len(d) >= 4:
            result["dhwTemp"] = parse_temp(d[0:4])
            
        # outsideTemp at position 4-7
        if len(d) >= 8:
            result["dhwOutsideTemp"] = parse_temp(d[4:8])
            
        # dhwSetTemp at position 8-11 (target temperature)
        if len(d) >= 12:
            result["dhwSetTemp"] = parse_temp(d[8:12])
            
        # compBlockTime at position 12-15 (compressor block time in minutes)
        if len(d) >= 16:
            val = int(d[12:16], 16)
            if val > 32767:
                val = val - 65536
            result["dhwCompBlockTime"] = val
            
        # dhwBoosterStage at position 24-25
        if len(d) >= 26:
            result["dhwBoosterStage"] = int(d[24:26], 16)
            
        # pasteurisationMode at position 28-29
        if len(d) >= 30:
            mode_byte = int(d[28:30], 16)
            result["pasteurisationMode"] = mode_byte
            result["pasteurisationActive"] = mode_byte == 1
            
        # dhwOpMode at position 30-31
        if len(d) >= 32:
            op_mode = int(d[30:32], 16)
            result["dhwOpMode"] = op_mode
            modes = {1: "normal", 2: "setback", 3: "standby", 4: "restart", 5: "restart"}
            result["dhwOpModeText"] = modes.get(op_mode, str(op_mode))
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_p01(data_hex: str) -> dict[str, Any]:
    """Parse p01-p12 register (17) - setpoints."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 4:
            result["p01RoomTempDay"] = int(d[0:4], 16) / 10
        if len(d) >= 8:
            result["p02RoomTempNight"] = int(d[4:8], 16) / 10
        if len(d) >= 16:
            result["p04DHWsetTempDay"] = int(d[12:16], 16) / 10
        if len(d) >= 28:
            result["p07FanStageDay"] = int(d[24:26], 16)
        if len(d) >= 30:
            result["p08FanStageNight"] = int(d[26:28], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_history(data_hex: str) -> dict[str, Any]:
    """
    Parse sHistory (09) register - operating hours and statistics.
    
    30 bytes = 15 hex pairs after command echo.
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo (09)
        
        # Operating hours (each 4 hex = 2 bytes = hours)
        if len(d) >= 4:
            result["compressorHeatingHours"] = int(d[0:4], 16)
        if len(d) >= 8:
            result["compressorCoolingHours"] = int(d[4:8], 16)
        if len(d) >= 12:
            result["compressorDHWHours"] = int(d[8:12], 16)
        if len(d) >= 16:
            result["boosterDHWHours"] = int(d[12:16], 16)
        if len(d) >= 20:
            result["boosterHeatingHours"] = int(d[16:20], 16)
            
        # Additional statistics
        if len(d) >= 24:
            result["compressorHeatingStarts"] = int(d[20:24], 16)
        if len(d) >= 28:
            result["compressorCoolingStarts"] = int(d[24:28], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_time(data_hex: str) -> dict[str, Any]:
    """
    Parse sTime (FC) register.
    
    Structure (based on actual device response FC04142417190C05):
    - Byte 0 (pos 0-1): Command echo (FC)
    - Byte 1 (pos 2-3): Weekday (1=Mon, 7=Sun)
    - Byte 2 (pos 4-5): Hour (0-23)
    - Byte 3 (pos 6-7): Minute (0-59)
    - Byte 4 (pos 8-9): Unknown/Second?
    - Byte 5 (pos 10-11): Year (2-digit, e.g., 19 = 2025)
    - Byte 6 (pos 12-13): Month (1-12)
    - Byte 7 (pos 14-15): Day (1-31)
    """
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo (FC)
        
        if len(d) >= 2:
            result["weekday"] = int(d[0:2], 16)
        if len(d) >= 4:
            result["hour"] = int(d[2:4], 16)
        if len(d) >= 6:
            result["minute"] = int(d[4:6], 16)
        if len(d) >= 8:
            result["second"] = int(d[6:8], 16)  # Might be something else
        if len(d) >= 10:
            year_short = int(d[8:10], 16)
            result["year"] = 2000 + year_short
        if len(d) >= 12:
            result["month"] = int(d[10:12], 16)
        if len(d) >= 14:
            result["day"] = int(d[12:14], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_errors(data_hex: str) -> dict[str, Any]:
    """Parse sLast (D1) register - error history."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 2:
            result["numberOfFaults"] = int(d[0:2], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


# Parser registry
PARSERS = {
    "firmware": parse_firmware,
    "sglobal": parse_sglobal,
    "shc1": parse_shc1,
    "dhw": parse_dhw,
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
