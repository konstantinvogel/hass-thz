"""THZ Heat Pump Protocol Handler.

This module implements the serial protocol for Tecalor THZ / Stiebel Eltron LWZ 
heat pumps, ported from FHEM's 00_THZ.pm.

Protocol overview:
- GET request: 0100 + cmd + checksum + 1003
- Response: data + checksum + 1003
- Checksum: sum of bytes mod 256
- Escaping: 0x10 -> 0x10 0x10, 0x2B -> 0x2B 0x18
"""
from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from typing import Any

import serial

_LOGGER = logging.getLogger(__name__)

# Protocol constants
HEADER_GET = bytes.fromhex("0100")
HEADER_SET = bytes.fromhex("0180")  # Not used - READ ONLY
FOOTER = bytes.fromhex("1003")
ACK = bytes.fromhex("10")
STX = bytes.fromhex("02")
DLE = bytes.fromhex("10")

# Timeouts (increased for reliability)
READ_TIMEOUT = 3.0
WRITE_TIMEOUT = 2.0
RETRY_COUNT = 3
RETRY_DELAY = 0.8


@dataclass
class ParsingRule:
    """Definition for parsing a field from a response."""
    name: str
    position: int
    length: int
    data_type: str
    divisor: float = 1.0


# Register definitions with parsing rules
# Format: register -> list of (name, position, length, type, divisor)
PARSING_RULES: dict[str, list[ParsingRule]] = {
    # FBglob - Main sensor data (firmware 4.39+)
    "FBglob": [
        ParsingRule("collectorTemp", 4, 4, "hex2int", 10),
        ParsingRule("outsideTemp", 8, 4, "hex2int", 10),
        ParsingRule("flowTemp", 12, 4, "hex2int", 10),
        ParsingRule("returnTemp", 16, 4, "hex2int", 10),
        ParsingRule("hotGasTemp", 20, 4, "hex2int", 10),
        ParsingRule("dhwTemp", 24, 4, "hex2int", 10),
        ParsingRule("flowTempHC2", 28, 4, "hex2int", 10),
        ParsingRule("insideTemp", 32, 4, "hex2int", 10),
        ParsingRule("evaporatorTemp", 36, 4, "hex2int", 10),
        ParsingRule("condenserTemp", 40, 4, "hex2int", 10),
        # Bit fields at positions 44-49
        ParsingRule("dhwPump", 44, 1, "bit0", 1),
        ParsingRule("heatingCircuitPump", 44, 1, "bit1", 1),
        ParsingRule("solarPump", 44, 1, "bit3", 1),
        ParsingRule("mixerOpen", 45, 1, "bit0", 1),
        ParsingRule("mixerClosed", 45, 1, "bit1", 1),
        ParsingRule("heatPipeValve", 45, 1, "bit2", 1),
        ParsingRule("diverterValve", 45, 1, "bit3", 1),
        ParsingRule("boosterStage3", 46, 1, "bit0", 1),
        ParsingRule("boosterStage2", 46, 1, "bit1", 1),
        ParsingRule("boosterStage1", 46, 1, "bit2", 1),
        ParsingRule("compressor", 47, 1, "bit3", 1),
        ParsingRule("evuRelease", 48, 1, "bit0", 1),
        ParsingRule("ovenFireplace", 48, 1, "bit1", 1),
        ParsingRule("STB", 48, 1, "bit2", 1),
        ParsingRule("highPressureSensor", 49, 1, "nbit0", 1),  # inverted
        ParsingRule("lowPressureSensor", 49, 1, "nbit1", 1),   # inverted
        ParsingRule("evaporatorIceMonitor", 49, 1, "bit2", 1),
        ParsingRule("signalAnode", 49, 1, "bit3", 1),
        # Ventilator data
        ParsingRule("outputVentilatorPower", 50, 4, "hex", 10),
        ParsingRule("inputVentilatorPower", 54, 4, "hex", 10),
        ParsingRule("mainVentilatorPower", 58, 4, "hex", 10),
        ParsingRule("outputVentilatorSpeed", 62, 4, "hex", 1),
        ParsingRule("inputVentilatorSpeed", 66, 4, "hex", 1),
        ParsingRule("mainVentilatorSpeed", 70, 4, "hex", 1),
        ParsingRule("outsideTempFiltered", 74, 4, "hex2int", 10),
        ParsingRule("relHumidity", 78, 4, "hex2int", 10),
        ParsingRule("dewPoint", 82, 4, "hex2int", 10),
        ParsingRule("P_Nd", 86, 4, "hex2int", 100),
        ParsingRule("P_Hd", 90, 4, "hex2int", 100),
        ParsingRule("flowRate", 110, 4, "hex", 100),
        ParsingRule("p_HCw", 114, 4, "hex", 100),
    ],
    # FBglob206 - Main sensor data for firmware 2.06
    "FBglob206": [
        ParsingRule("collectorTemp", 4, 4, "hex2int", 10),
        ParsingRule("outsideTemp", 8, 4, "hex2int", 10),
        ParsingRule("flowTemp", 12, 4, "hex2int", 10),
        ParsingRule("returnTemp", 16, 4, "hex2int", 10),
        ParsingRule("hotGasTemp", 20, 4, "hex2int", 10),
        ParsingRule("dhwTemp", 24, 4, "hex2int", 10),
        ParsingRule("flowTempHC2", 28, 4, "hex2int", 10),
        ParsingRule("insideTemp", 32, 4, "hex2int", 10),
        ParsingRule("evaporatorTemp", 36, 4, "hex2int", 10),
        ParsingRule("condenserTemp", 40, 4, "hex2int", 10),
        ParsingRule("compressor", 44, 1, "bit0", 1),
        ParsingRule("boosterStage1", 44, 1, "bit1", 1),
        ParsingRule("boosterStage2", 44, 1, "bit2", 1),
        ParsingRule("boosterStage3", 44, 1, "bit3", 1),
        ParsingRule("heatingCircuitPump", 45, 1, "bit0", 1),
        ParsingRule("dhwPump", 45, 1, "bit1", 1),
        ParsingRule("diverterValve", 45, 1, "bit2", 1),
        ParsingRule("heatPipeValve", 45, 1, "bit3", 1),
        ParsingRule("mixerClosed", 47, 1, "bit0", 1),
        ParsingRule("mixerOpen", 47, 1, "bit1", 1),
        ParsingRule("outputVentilatorPower", 48, 2, "hex", 1),
        ParsingRule("inputVentilatorPower", 50, 2, "hex", 1),
        ParsingRule("mainVentilatorPower", 52, 2, "hex", 2.55),
        ParsingRule("highPressureSensor", 54, 1, "bit3", 1),
        ParsingRule("lowPressureSensor", 54, 1, "bit2", 1),
        ParsingRule("signalAnode", 54, 1, "bit1", 1),
        ParsingRule("ovenFireplace", 54, 1, "bit0", 1),
        ParsingRule("evaporatorIceMonitor", 55, 1, "bit3", 1),
        ParsingRule("outputVentilatorSpeed", 56, 2, "hex", 1),
        ParsingRule("inputVentilatorSpeed", 58, 2, "hex", 1),
        ParsingRule("mainVentilatorSpeed", 60, 2, "hex", 1),
        ParsingRule("outsideTempFiltered", 64, 4, "hex2int", 10),
    ],
    # F3dhw - DHW (Domestic Hot Water) data
    "F3dhw": [
        ParsingRule("dhwTemp", 4, 4, "hex2int", 10),
        ParsingRule("outsideTemp", 8, 4, "hex2int", 10),
        ParsingRule("dhwSetTemp", 12, 4, "hex2int", 10),
        ParsingRule("compBlockTime", 16, 4, "hex2int", 1),
        ParsingRule("heatBlockTime", 24, 4, "hex2int", 1),
        ParsingRule("dhwBoosterStage", 28, 2, "hex", 1),
        ParsingRule("pasteurisationMode", 32, 2, "hex", 1),
        ParsingRule("dhwOpMode", 34, 2, "opmodehc", 1),
    ],
    # F4hc1 - Heating Circuit 1
    "F4hc1": [
        ParsingRule("outsideTemp", 4, 4, "hex2int", 10),
        ParsingRule("returnTemp", 12, 4, "hex2int", 10),
        ParsingRule("integralHeat", 16, 4, "hex2int", 1),
        ParsingRule("flowTemp", 20, 4, "hex2int", 10),
        ParsingRule("heatSetTemp", 24, 4, "hex2int", 10),
        ParsingRule("heatTemp", 28, 4, "hex2int", 10),
        ParsingRule("onHysteresisNo", 32, 2, "hex", 1),
        ParsingRule("offHysteresisNo", 34, 2, "hex", 1),
        ParsingRule("hcBoosterStage", 36, 2, "hex", 1),
        ParsingRule("seasonMode", 38, 2, "somwinmode", 1),
        ParsingRule("integralSwitch", 44, 4, "hex2int", 1),
        ParsingRule("hcOpMode", 48, 2, "opmodehc", 1),
        ParsingRule("roomSetTemp", 56, 4, "hex2int", 10),
        ParsingRule("insideTempRC", 68, 4, "hex2int", 10),
    ],
    # F5hc2 - Heating Circuit 2
    "F5hc2": [
        ParsingRule("outsideTemp", 4, 4, "hex2int", 10),
        ParsingRule("returnTemp", 8, 4, "hex2int", 10),
        ParsingRule("vorlaufTemp", 12, 4, "hex2int", 10),
        ParsingRule("heatSetTemp", 16, 4, "hex2int", 10),
        ParsingRule("heatTemp", 20, 4, "hex2int", 10),
        ParsingRule("stellgroesse", 24, 4, "hex2int", 10),
        ParsingRule("seasonMode", 30, 2, "somwinmode", 1),
        ParsingRule("hcOpMode", 36, 2, "opmodehc", 1),
    ],
    # F2ctrl - Control data
    "F2ctrl": [
        ParsingRule("heatRequest", 4, 2, "hex", 1),
        ParsingRule("heatRequest2", 6, 2, "hex", 1),
        ParsingRule("hcStage", 8, 2, "hex", 1),
        ParsingRule("dhwStage", 10, 2, "hex", 1),
        ParsingRule("heatStageControlModul", 12, 2, "hex", 1),
        ParsingRule("compBlockTime", 14, 4, "hex2int", 1),
        ParsingRule("pasteurisationMode", 18, 2, "hex", 1),
        ParsingRule("compressor", 22, 1, "bit0", 1),
        ParsingRule("boosterStage1", 22, 1, "bit1", 1),
        ParsingRule("solarPump", 22, 1, "bit2", 1),
        ParsingRule("boosterStage2", 22, 1, "bit3", 1),
        ParsingRule("heatingCircuitPump", 23, 1, "bit0", 1),
        ParsingRule("dhwPump", 23, 1, "bit1", 1),
        ParsingRule("diverterValve", 23, 1, "bit2", 1),
        ParsingRule("heatPipeValve", 23, 1, "bit3", 1),
        ParsingRule("mixerClosed", 25, 1, "bit0", 1),
        ParsingRule("mixerOpen", 25, 1, "bit1", 1),
        ParsingRule("boostBlockTimeAfterPumpStart", 30, 4, "hex2int", 1),
        ParsingRule("boostBlockTimeAfterHD", 34, 4, "hex2int", 1),
    ],
    # FDfirm - Firmware information
    "FDfirm": [
        ParsingRule("version", 4, 4, "hex", 100),
        ParsingRule("date_day", 8, 2, "hex", 1),
        ParsingRule("date_month", 10, 2, "hex", 1),
        ParsingRule("date_year", 12, 4, "hex", 1),
        ParsingRule("id", 16, 4, "hex", 1),
    ],
    # FCtime - Date and Time
    "FCtime": [
        ParsingRule("year", 4, 4, "hex", 1),
        ParsingRule("seconds", 8, 2, "hex", 1),
        ParsingRule("minutes", 10, 2, "hex", 1),
        ParsingRule("hours", 12, 2, "hex", 1),
        ParsingRule("day", 14, 2, "hex", 1),
        ParsingRule("month", 16, 2, "hex", 1),
        ParsingRule("weekday", 18, 2, "hex", 1),
    ],
    # 09his - Operating hours history (firmware 4.39+)
    "09his": [
        ParsingRule("compressorHeatingHours", 4, 4, "hex", 1),
        ParsingRule("compressorCoolingHours", 8, 4, "hex", 1),
        ParsingRule("compressorDHWHours", 12, 4, "hex", 1),
        ParsingRule("boosterDHWHours", 16, 4, "hex", 1),
        ParsingRule("boosterHeatingHours", 20, 4, "hex", 1),
    ],
    # 09his206 - Operating hours history (firmware 2.xx)
    "09his206": [
        ParsingRule("operatingHours1", 4, 4, "hex", 1),
        ParsingRule("operatingHours2", 8, 4, "hex", 1),
        ParsingRule("heatingHours", 12, 4, "hex", 1),
        ParsingRule("DHWhours", 16, 4, "hex", 1),
        ParsingRule("coolingHours", 20, 4, "hex", 1),
    ],
    # 17pxx206 - Parameters p01-p12 (room temp, DHW temp, fan stages)
    "17pxx": [
        ParsingRule("p01RoomTempDay", 4, 4, "hex", 10),
        ParsingRule("p02RoomTempNight", 8, 4, "hex", 10),
        ParsingRule("p03RoomTempStandby", 12, 4, "hex", 10),
        ParsingRule("p04DHWsetTempDay", 16, 4, "hex", 10),
        ParsingRule("p05DHWsetTempNight", 20, 4, "hex", 10),
        ParsingRule("p06DHWsetTempStandby", 24, 4, "hex", 10),
        ParsingRule("p07FanStageDay", 28, 2, "hex", 1),
        ParsingRule("p08FanStageNight", 30, 2, "hex", 1),
        ParsingRule("p09FanStageStandby", 32, 2, "hex", 1),
        ParsingRule("p10HCTempManual", 34, 4, "hex", 10),
        ParsingRule("p11DHWsetTempManual", 38, 4, "hex", 10),
        ParsingRule("p12FanStageManual", 42, 2, "hex", 1),
    ],
    # D1last - Last 10 errors (firmware 4.39+)
    "D1last": [
        ParsingRule("numberOfFaults", 4, 2, "hex", 1),
        ParsingRule("fault0Code", 8, 2, "faultmap", 1),
        ParsingRule("fault1Code", 20, 2, "faultmap", 1),
        ParsingRule("fault2Code", 32, 2, "faultmap", 1),
        ParsingRule("fault3Code", 44, 2, "faultmap", 1),
    ],
    # D1last206 - Last errors (firmware 2.xx)
    "D1last206": [
        ParsingRule("numberOfFaults", 4, 2, "hex", 1),
        ParsingRule("fault0Code", 8, 4, "faultmap", 1),
        ParsingRule("fault1Code", 20, 4, "faultmap", 1),
        ParsingRule("fault2Code", 32, 4, "faultmap", 1),
        ParsingRule("fault3Code", 44, 4, "faultmap", 1),
    ],
    # Energy counters - single value registers (need special handling)
    "1clean": [
        ParsingRule("value", 4, 4, "hex", 1),
    ],
}

# Register commands
REGISTERS: dict[str, dict[str, Any]] = {
    "sGlobal": {"cmd": "FB", "type": "FBglob"},
    "sGlobal206": {"cmd": "FB", "type": "FBglob206"},
    "sDHW": {"cmd": "F3", "type": "F3dhw"},
    "sHC1": {"cmd": "F4", "type": "F4hc1"},
    "sHC2": {"cmd": "F5", "type": "F5hc2"},
    "sControl": {"cmd": "F2", "type": "F2ctrl"},
    "sFirmware": {"cmd": "FD", "type": "FDfirm"},
    "sTimedate": {"cmd": "FC", "type": "FCtime"},
    "sHistory": {"cmd": "09", "type": "09his"},
    "sHistory206": {"cmd": "09", "type": "09his206"},
    "p01-p12": {"cmd": "17", "type": "17pxx"},
    "sLast10errors": {"cmd": "D1", "type": "D1last"},
    "sLast10errors206": {"cmd": "D1", "type": "D1last206"},
    # Energy registers (combined high/low word)
    "sBoostDHWTotal": {"cmd": "0A0924", "cmd2": "0A0925", "type": "energy_combined", "unit": "kWh"},
    "sBoostHCTotal": {"cmd": "0A0928", "cmd2": "0A0929", "type": "energy_combined", "unit": "kWh"},
    "sHeatDHWTotal": {"cmd": "0A092C", "cmd2": "0A092D", "type": "energy_combined", "unit": "kWh"},
    "sHeatHCTotal": {"cmd": "0A0930", "cmd2": "0A0931", "type": "energy_combined", "unit": "kWh"},
    "sElectrDHWTotal": {"cmd": "0A091C", "cmd2": "0A091D", "type": "energy_combined", "unit": "kWh"},
    "sElectrHCTotal": {"cmd": "0A0920", "cmd2": "0A0921", "type": "energy_combined", "unit": "kWh"},
}

# Fault code mappings
FAULT_CODES: dict[int, str] = {
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
    52: "F52_SensorCondenserOutlet",
}

# Operation mode mappings
OP_MODES: dict[int, str] = {
    1: "standby",
    11: "automatic", 
    3: "DAYmode",
    4: "setback",
    5: "DHWmode",
    14: "manual",
    0: "emergency",
}

OP_MODES_HC: dict[int, str] = {
    1: "normal",
    2: "setback", 
    3: "standby",
    4: "restart",
    5: "restart",
}

SEASON_MODES: dict[int, str] = {
    1: "winter",
    2: "summer",
}


class THZProtocolError(Exception):
    """Exception for protocol errors."""


class THZProtocol:
    """Protocol handler for THZ heat pumps."""

    def __init__(
        self, 
        port: str, 
        baudrate: int = 115200,
        firmware: str = "auto"
    ) -> None:
        """Initialize the protocol handler.
        
        Args:
            port: Serial port path (e.g., /dev/ttyUSB0 or COM3)
            baudrate: Baud rate (usually 115200)
            firmware: Firmware version or "auto" to detect
        """
        self.port = port
        self.baudrate = baudrate
        self._firmware = firmware
        self._detected_firmware: str | None = None
        self._serial: serial.Serial | None = None
        _LOGGER.debug("THZProtocol initialized: port=%s, baudrate=%d", port, baudrate)

    @property
    def firmware(self) -> str:
        """Get the firmware version (detected or configured)."""
        return self._detected_firmware or self._firmware

    def open(self) -> None:
        """Open the serial connection."""
        if self._serial and self._serial.is_open:
            return
            
        _LOGGER.debug("Opening serial port %s at %d baud", self.port, self.baudrate)
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=READ_TIMEOUT,
            write_timeout=WRITE_TIMEOUT,
        )
        time.sleep(0.1)  # Give device time to initialize
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def close(self) -> None:
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            _LOGGER.debug("Closing serial port")
            self._serial.close()
        self._serial = None

    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate checksum (sum of bytes mod 256)."""
        return sum(data) % 256

    def _escape_bytes(self, data: bytes) -> bytes:
        """Escape special bytes in data.
        
        0x10 -> 0x10 0x10
        0x2B -> 0x2B 0x18
        """
        result = bytearray()
        for byte in data:
            if byte == 0x10:
                result.extend([0x10, 0x10])
            elif byte == 0x2B:
                result.extend([0x2B, 0x18])
            else:
                result.append(byte)
        return bytes(result)

    def _unescape_bytes(self, data: bytes) -> bytes:
        """Unescape special bytes in data.
        
        0x10 0x10 -> 0x10
        0x2B 0x18 -> 0x2B
        """
        result = bytearray()
        i = 0
        while i < len(data):
            if i + 1 < len(data):
                if data[i] == 0x10 and data[i + 1] == 0x10:
                    result.append(0x10)
                    i += 2
                    continue
                elif data[i] == 0x2B and data[i + 1] == 0x18:
                    result.append(0x2B)
                    i += 2
                    continue
            result.append(data[i])
            i += 1
        return bytes(result)

    def _encode_command(self, register: str) -> bytes:
        """Encode a GET command for a register.
        
        Based on FHEM THZ_encodecommand:
        Format: header + checksum + cmd + footer
        
        Checksum is calculated over: header + "XX" + cmd + footer
        (where XX is a placeholder for checksum position)
        
        Then escape sequences are applied to checksum + cmd portion.
        """
        header = "0100"
        footer = "1003"
        cmd = register.upper()
        
        # Calculate checksum over: header + XX (placeholder) + cmd + footer
        # The checksum itself is NOT included in the calculation
        checksum_input = header + "XX" + cmd + footer
        
        # Sum all bytes except the XX placeholder (positions 4-5)
        checksum = 0
        for i in range(0, len(checksum_input) - 4, 2):  # -4 to skip footer in loop
            if i != 4:  # Skip the XX placeholder at position 4
                checksum += int(checksum_input[i:i+2], 16)
        checksum = checksum % 256
        
        # Build: checksum + cmd (this part gets escaped)
        data_to_escape = f"{checksum:02X}" + cmd
        
        # Apply escape sequences:
        # 10 -> 1010
        # 2B -> 2B18
        escaped = ""
        i = 0
        while i < len(data_to_escape):
            two_chars = data_to_escape[i:i+2]
            if two_chars == "10":
                escaped += "1010"
                i += 2
            elif two_chars == "2B":
                escaped += "2B18"
                i += 2
            else:
                escaped += data_to_escape[i]
                i += 1
        
        # Final message: header + escaped(checksum + cmd) + footer
        message_hex = header + escaped + footer
        message = bytes.fromhex(message_hex)
        
        _LOGGER.debug("Encoded command for %s: %s", register, message.hex())
        return message

    def _read_byte(self, timeout: float = READ_TIMEOUT) -> bytes | None:
        """Read a single byte with timeout."""
        if not self._serial:
            return None
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._serial.in_waiting:
                return self._serial.read(1)
            time.sleep(0.002)
        return None

    def _read_until_complete(self, timeout: float = READ_TIMEOUT) -> bytes:
        """Read response until complete (starts with 01, ends with 1003).
        
        Based on FHEM THZ_ReadAnswer - handles chunked reads.
        """
        if not self._serial:
            raise THZProtocolError("Serial port not open")
        
        buffer = bytearray()
        start_time = time.time()
        max_iterations = 300  # Safety limit
        iteration = 0
        
        while time.time() - start_time < timeout and iteration < max_iterations:
            iteration += 1
            
            # Read available bytes
            if self._serial.in_waiting:
                chunk = self._serial.read(self._serial.in_waiting)
                buffer.extend(chunk)
                
                # Check if we have a complete message
                data_hex = buffer.hex().upper()
                
                # Message complete when: starts with 01 and ends with 1003
                if data_hex.startswith("01") and data_hex.endswith("1003"):
                    _LOGGER.debug("Complete message received: %s", data_hex)
                    return bytes(buffer)
                    
                # Also check for single NAK (0x15)
                if data_hex == "15":
                    return bytes(buffer)
            
            # Small delay between reads
            time.sleep(0.005)
        
        # Timeout - return what we have for debugging
        if buffer:
            raise THZProtocolError(f"Timeout reading response, partial data: {buffer.hex()}")
        else:
            raise THZProtocolError("Timeout reading response, no data received")

    def _send_and_receive(self, command: bytes) -> bytes:
        """Send a command and receive the response using proper handshake.
        
        Protocol sequence (from FHEM 00_THZ.pm):
        1. Send STX (0x02) -> Expect DLE (0x10)
        2. Send command -> Expect DLE STX (0x10 0x02) or just STX (0x02)
        3. Send DLE (0x10) -> Read response data
        """
        if not self._serial:
            raise THZProtocolError("Serial port not open")

        for attempt in range(RETRY_COUNT):
            try:
                # Clear buffers
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()
                
                # Step 0: Send STX (0x02) to initiate communication
                _LOGGER.debug("Step 0: Sending STX (attempt %d)", attempt + 1)
                self._serial.write(STX)
                self._serial.flush()
                
                # Expect DLE (0x10) response
                response = self._read_byte(timeout=1.0)
                if response is None:
                    raise THZProtocolError("No response to STX")
                if response != DLE:
                    if response == b'\x15':  # NAK
                        raise THZProtocolError("Received NAK at step 0")
                    raise THZProtocolError(f"Expected DLE (0x10) at step 0, got: {response.hex()}")
                _LOGGER.debug("Step 0: Received DLE OK")
                
                # Step 1: Send the actual command
                _LOGGER.debug("Step 1: Sending command: %s", command.hex())
                self._serial.write(command)
                self._serial.flush()
                
                # Expect DLE STX (0x10 0x02) - sometimes comes as separate bytes
                response = self._read_byte(timeout=1.0)
                if response is None:
                    raise THZProtocolError("No response to command")
                
                # Handle responses: could be "10", "02", "1002", or "15" (NAK)
                if response == b'\x15':  # NAK
                    raise THZProtocolError("Received NAK at step 1")
                
                if response == DLE:  # 0x10
                    # Read next byte, should be STX (0x02)
                    time.sleep(0.005)  # Small delay for slow devices
                    response2 = self._read_byte(timeout=0.5)
                    if response2 != STX:
                        raise THZProtocolError(f"Expected STX after DLE, got: {response2.hex() if response2 else 'None'}")
                elif response != STX:  # Should be 0x02 directly
                    raise THZProtocolError(f"Expected DLE or STX at step 1, got: {response.hex()}")
                
                _LOGGER.debug("Step 1: Received DLE STX OK")
                
                # Step 2: Send DLE (0x10) to request data
                _LOGGER.debug("Step 2: Sending DLE to request data")
                self._serial.write(DLE)
                self._serial.flush()
                
                # Read the actual response data
                raw_response = self._read_until_complete()
                _LOGGER.debug("Raw response: %s", raw_response.hex())
                
                # Send final DLE acknowledgment
                self._serial.write(DLE)
                self._serial.flush()
                
                # Decode response according to FHEM THZ_decode
                # Response format: header(2 bytes) + checksum(1 byte) + data + footer(2 bytes)
                # First unescape, then validate
                
                response_hex = raw_response.hex().upper()
                
                # Unescape: 1010 -> 10, 2B18 -> 2B
                response_hex = response_hex.replace("1010", "10")
                response_hex = response_hex.replace("2B18", "2B")
                
                _LOGGER.debug("Unescaped response: %s", response_hex)
                
                # Check for NAK
                if response_hex == "15":
                    raise THZProtocolError("NAK received from device")
                
                # Check minimum length
                if len(response_hex) < 8:  # header(4) + checksum(2) + footer(4) minimum
                    raise THZProtocolError(f"Response too short: {response_hex}")
                
                # Check header
                header = response_hex[:4]
                if header == "0100":
                    # Normal GET response - verify checksum
                    # Checksum is calculated over entire message, checksum byte position is skipped
                    received_checksum = response_hex[4:6]
                    
                    # Calculate checksum: sum of all bytes except checksum position, mod 256
                    calc_sum = 0
                    for i in range(0, len(response_hex) - 4, 2):  # exclude footer
                        if i != 4:  # skip checksum position
                            calc_sum += int(response_hex[i:i+2], 16)
                    calculated_checksum = f"{calc_sum % 256:02X}"
                    
                    if received_checksum != calculated_checksum:
                        raise THZProtocolError(
                            f"Checksum mismatch: received {received_checksum}, "
                            f"calculated {calculated_checksum}"
                        )
                    
                    # Extract data between checksum and footer: 0100 XX data 1003
                    # Data starts at position 6 (after header + checksum) and ends before footer
                    data_hex = response_hex[6:-4]  # Remove header+checksum and footer
                    _LOGGER.debug("Response data: %s", data_hex)
                    return bytes.fromhex(data_hex) if data_hex else b''
                    
                elif header == "0101":
                    raise THZProtocolError("Timing issue in communication")
                elif header == "0102":
                    raise THZProtocolError("CRC error in request")
                elif header == "0103":
                    raise THZProtocolError("Unknown command")
                elif header == "0104":
                    raise THZProtocolError("Unknown register requested")
                elif header == "0180":
                    # SET response (we don't use this, but handle it)
                    return bytes.fromhex(response_hex)
                else:
                    raise THZProtocolError(f"Unknown response header: {header}")
                
            except THZProtocolError as err:
                _LOGGER.warning("Attempt %d failed: %s", attempt + 1, err)
                if attempt < RETRY_COUNT - 1:
                    time.sleep(RETRY_DELAY)
                    # Reset the serial line
                    if self._serial:
                        self._serial.reset_input_buffer()
                        self._serial.reset_output_buffer()
                else:
                    raise

        raise THZProtocolError("All retry attempts failed")

    def _parse_value(self, data: bytes, rule: ParsingRule) -> Any:
        """Parse a value from response data according to the rule."""
        try:
            # Extract raw bytes
            start = rule.position
            end = start + rule.length
            
            if end > len(data) * 2:  # data is in hex representation
                _LOGGER.debug(
                    "Field %s out of bounds (pos=%d, len=%d, data_len=%d)",
                    rule.name, rule.position, rule.length, len(data)
                )
                return None

            # Convert data to hex string for position-based access
            hex_str = data.hex()
            value_hex = hex_str[start:end]
            
            if not value_hex:
                return None

            # Parse based on type
            if rule.data_type == "hex":
                value = int(value_hex, 16)
                return value / rule.divisor
                
            elif rule.data_type == "hex2int":
                # Signed integer
                value = int(value_hex, 16)
                # Handle signed values (2's complement for 16-bit)
                if rule.length == 4 and value > 32767:
                    value -= 65536
                return value / rule.divisor
                
            elif rule.data_type.startswith("bit"):
                # Single bit extraction
                byte_val = int(value_hex, 16)
                bit_num = int(rule.data_type[3:])
                return bool(byte_val & (1 << bit_num))
                
            elif rule.data_type.startswith("nbit"):
                # Inverted bit extraction
                byte_val = int(value_hex, 16)
                bit_num = int(rule.data_type[4:])
                return not bool(byte_val & (1 << bit_num))
                
            elif rule.data_type == "somwinmode":
                value = int(value_hex, 16)
                return SEASON_MODES.get(value, f"unknown({value})")
                
            elif rule.data_type == "opmodehc":
                value = int(value_hex, 16)
                return OP_MODES_HC.get(value, f"unknown({value})")
            
            elif rule.data_type == "faultmap":
                value = int(value_hex, 16)
                return FAULT_CODES.get(value, f"unknown({value})")
                
            elif rule.data_type == "raw":
                return value_hex
                
            else:
                _LOGGER.debug("Unknown data type: %s", rule.data_type)
                return int(value_hex, 16)
                
        except (ValueError, IndexError) as err:
            _LOGGER.debug("Error parsing %s: %s", rule.name, err)
            return None

    def _parse_response(self, data: bytes, register_type: str) -> dict[str, Any]:
        """Parse a response according to the register type."""
        rules = PARSING_RULES.get(register_type)
        if not rules:
            _LOGGER.warning("No parsing rules for type: %s", register_type)
            return {"raw": data.hex()}

        result: dict[str, Any] = {}
        for rule in rules:
            value = self._parse_value(data, rule)
            if value is not None:
                result[rule.name] = value

        return result

    def read_register(self, register_name: str) -> dict[str, Any]:
        """Read a register from the heat pump.
        
        Args:
            register_name: Name of the register (e.g., "sGlobal", "sDHW")
            
        Returns:
            Dictionary with parsed values
        """
        reg_info = REGISTERS.get(register_name)
        if not reg_info:
            raise THZProtocolError(f"Unknown register: {register_name}")

        cmd = self._encode_command(reg_info["cmd"])
        response = self._send_and_receive(cmd)
        
        return self._parse_response(response, reg_info["type"])

    def detect_firmware(self) -> str:
        """Detect the firmware version of the heat pump.
        
        Returns:
            Firmware version string (e.g., "5.39")
        """
        self.open()
        try:
            # Read firmware register (FD)
            cmd = self._encode_command("FD")
            response = self._send_and_receive(cmd)
            
            # Response is the data portion (after header+checksum, before footer)
            # According to FHEM parsing for sFirmware:
            # Position 0-1: Command echo (FD)
            # Position 2-5: Version (4 hex chars = 2 bytes)
            hex_str = response.hex().upper()
            _LOGGER.debug("Firmware register response: %s", hex_str)
            
            if len(hex_str) >= 6:
                # Skip command echo (first 2 chars), get version (next 4 chars)
                version_hex = hex_str[2:6]
                version_raw = int(version_hex, 16)
                major = version_raw // 100
                minor = version_raw % 100
                self._detected_firmware = f"{major}.{minor:02d}"
                _LOGGER.info("Detected firmware: %s", self._detected_firmware)
                return self._detected_firmware
            else:
                raise THZProtocolError(f"Invalid firmware response: {hex_str}")
        except Exception as err:
            _LOGGER.error("Failed to detect firmware: %s", err)
            raise

    def test_connection(self) -> bool:
        """Test the connection to the heat pump.
        
        Returns:
            True if connection successful
        """
        try:
            self.open()
            # Try to read firmware - this validates the connection
            self.detect_firmware()
            return True
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False
        finally:
            self.close()

    def get_all_sensor_data(self) -> dict[str, Any]:
        """Read all sensor data from the heat pump.
        
        Returns:
            Dictionary with all sensor values
        """
        self.open()
        try:
            result: dict[str, Any] = {}
            
            # Determine which register types to use based on firmware
            fw = self.firmware
            is_old_firmware = fw.startswith("2.")
            
            if is_old_firmware:
                global_type = "sGlobal206"
                history_type = "sHistory206"
                errors_type = "sLast10errors206"
            else:
                global_type = "sGlobal"
                history_type = "sHistory"
                errors_type = "sLast10errors"
            
            # Read main registers
            for reg_name in [global_type, "sDHW", "sHC1", "sControl"]:
                try:
                    data = self.read_register(reg_name)
                    result.update(data)
                    time.sleep(0.1)  # Small delay between requests
                except THZProtocolError as err:
                    _LOGGER.warning("Failed to read %s: %s", reg_name, err)

            # Read parameters p01-p12 (FanStageDay, setpoints, etc.)
            try:
                data = self.read_register("p01-p12")
                result.update(data)
                time.sleep(0.1)
            except THZProtocolError as err:
                _LOGGER.warning("Failed to read p01-p12: %s", err)

            # Read operating hours/history
            try:
                data = self.read_register(history_type)
                result.update(data)
                time.sleep(0.1)
            except THZProtocolError as err:
                _LOGGER.warning("Failed to read history: %s", err)

            # Read last errors
            try:
                data = self.read_register(errors_type)
                result.update(data)
                time.sleep(0.1)
            except THZProtocolError as err:
                _LOGGER.warning("Failed to read errors: %s", err)

            # Read energy counters (only for newer firmware)
            if not is_old_firmware:
                energy_regs = [
                    "sBoostDHWTotal",
                    "sBoostHCTotal",
                    "sElectrDHWTotal",
                    "sElectrHCTotal",
                    "sHeatDHWTotal",
                    "sHeatHCTotal",
                ]
                for reg_name in energy_regs:
                    try:
                        value = self._read_energy_register(reg_name)
                        if value is not None:
                            result[reg_name] = value
                        time.sleep(0.1)
                    except THZProtocolError as err:
                        _LOGGER.debug("Failed to read %s: %s", reg_name, err)

            return result
            
        finally:
            pass  # Keep connection open for coordinator

    def _read_energy_register(self, register_name: str) -> float | None:
        """Read a combined energy register (high + low word).
        
        These registers store values as two 16-bit words that need to be combined.
        """
        reg_info = REGISTERS.get(register_name)
        if not reg_info or reg_info.get("type") != "energy_combined":
            return None

        try:
            # Read low word
            cmd = self._encode_command(reg_info["cmd"])
            response_low = self._send_and_receive(cmd)
            hex_str = response_low.hex()
            if len(hex_str) >= 8:
                low_word = int(hex_str[4:8], 16)
            else:
                return None
            
            time.sleep(0.05)
            
            # Read high word
            cmd = self._encode_command(reg_info["cmd2"])
            response_high = self._send_and_receive(cmd)
            hex_str = response_high.hex()
            if len(hex_str) >= 8:
                high_word = int(hex_str[4:8], 16)
            else:
                return None
            
            # Combine: high_word * 1000 + low_word (based on FHEM logic)
            value = high_word * 1000 + low_word
            return float(value)
            
        except THZProtocolError:
            return None

    def get_firmware_info(self) -> dict[str, Any]:
        """Get detailed firmware information."""
        self.open()
        return self.read_register("sFirmware")

    def get_all_raw_registers(self) -> dict[str, str]:
        """Read all registers and return raw hex data for backup.
        
        Returns a dictionary mapping register command to raw hex response.
        This is used for creating a backup of all register values.
        """
        self.open()
        raw_data = {}
        
        # Collect all unique commands from REGISTERS
        commands_read = set()
        
        for register_name, reg_info in REGISTERS.items():
            cmd_hex = reg_info.get("cmd", "")
            if not cmd_hex or cmd_hex in commands_read:
                continue
                
            commands_read.add(cmd_hex)
            
            try:
                cmd = self._encode_command(cmd_hex)
                response = self._send_and_receive(cmd)
                raw_data[cmd_hex] = response.hex()
                time.sleep(0.05)  # Small delay between reads
            except THZProtocolError as e:
                _LOGGER.debug("Failed to read register %s: %s", cmd_hex, e)
                raw_data[cmd_hex] = f"ERROR: {e}"
            except Exception as e:
                _LOGGER.warning("Unexpected error reading %s: %s", cmd_hex, e)
                raw_data[cmd_hex] = f"ERROR: {e}"
        
        # Also read energy combined registers' second commands
        for register_name, reg_info in REGISTERS.items():
            if reg_info.get("type") == "energy_combined":
                cmd2_hex = reg_info.get("cmd2", "")
                if cmd2_hex and cmd2_hex not in commands_read:
                    commands_read.add(cmd2_hex)
                    try:
                        cmd = self._encode_command(cmd2_hex)
                        response = self._send_and_receive(cmd)
                        raw_data[cmd2_hex] = response.hex()
                        time.sleep(0.05)
                    except Exception as e:
                        raw_data[cmd2_hex] = f"ERROR: {e}"
        
        return raw_data
