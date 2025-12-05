#!/usr/bin/env python3
"""
Comprehensive pytest unit tests for THZ protocol implementation.

Run with: pytest tests/test_protocol.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from thz_protocol import (
    # Enums and dataclasses
    THZError,
    THZResponse,
    REGISTERS,
    PARSERS,
    # Core functions
    calculate_checksum,
    escape_data,
    unescape_data,
    build_command,
    parse_response,
    parse_temp,
    # Parser functions
    parse_firmware,
    parse_sglobal,
    parse_shc1,
    parse_dhw,
    parse_p01,
    parse_history,
    parse_time,
    parse_errors,
    # Connection class
    THZConnection,
)


# =============================================================================
# THZError Enum Tests
# =============================================================================

class TestTHZError:
    """Tests for THZError enum."""
    
    def test_error_values(self):
        """Test that error codes have correct values."""
        assert THZError.SUCCESS == 0x00
        assert THZError.CRC_ERROR == 0x02
        assert THZError.UNKNOWN_CMD == 0x03
        assert THZError.UNKNOWN_REG == 0x04
    
    def test_error_is_int(self):
        """Test that THZError is an IntEnum."""
        assert isinstance(THZError.CRC_ERROR, int)
        assert THZError.CRC_ERROR == 2


# =============================================================================
# THZResponse Dataclass Tests
# =============================================================================

class TestTHZResponse:
    """Tests for THZResponse dataclass."""
    
    def test_success_response(self):
        """Test creating a successful response."""
        response = THZResponse(success=True, data="ABCD")
        assert response.success is True
        assert response.data == "ABCD"
        assert response.error is None
        assert response.error_message is None
    
    def test_error_response(self):
        """Test creating an error response."""
        response = THZResponse(
            success=False,
            error=THZError.CRC_ERROR,
            error_message="CRC Error"
        )
        assert response.success is False
        assert response.data is None
        assert response.error == THZError.CRC_ERROR
        assert response.error_message == "CRC Error"
    
    def test_default_values(self):
        """Test default values."""
        response = THZResponse(success=True)
        assert response.data is None
        assert response.error is None
        assert response.error_message is None


# =============================================================================
# REGISTERS Dictionary Tests
# =============================================================================

class TestRegisters:
    """Tests for REGISTERS dictionary."""
    
    def test_registers_exist(self):
        """Test that expected registers are defined."""
        expected = ["FD", "FB", "F3", "F4", "FC", "17", "0A17", "09", "D1"]
        for reg in expected:
            assert reg in REGISTERS, f"Register {reg} not found"
    
    def test_registers_have_required_keys(self):
        """Test that each register has name and parse keys."""
        for reg, info in REGISTERS.items():
            assert "name" in info, f"Register {reg} missing 'name'"
            assert "parse" in info, f"Register {reg} missing 'parse'"
    
    def test_parsers_exist_for_registers(self):
        """Test that parsers exist for all non-raw registers."""
        for reg, info in REGISTERS.items():
            parse_type = info["parse"]
            if parse_type != "raw":
                assert parse_type in PARSERS, f"Parser '{parse_type}' not found for register {reg}"


# =============================================================================
# Checksum Tests
# =============================================================================

class TestChecksum:
    """Tests for checksum calculation."""
    
    def test_checksum_fd(self):
        """Test checksum for FD (firmware) command."""
        assert calculate_checksum("FD") == 0xFE
    
    def test_checksum_fb(self):
        """Test checksum for FB (sGlobal) command."""
        assert calculate_checksum("FB") == 0xFC
    
    def test_checksum_09(self):
        """Test checksum for 09 (history) command."""
        assert calculate_checksum("09") == 0x0A
    
    def test_checksum_f3(self):
        """Test checksum for F3 (sDHW) command."""
        assert calculate_checksum("F3") == 0xF4
    
    def test_checksum_f4(self):
        """Test checksum for F4 (sHC1) command."""
        assert calculate_checksum("F4") == 0xF5
    
    def test_checksum_fc(self):
        """Test checksum for FC (sTime) command."""
        assert calculate_checksum("FC") == 0xFD
    
    def test_checksum_d1(self):
        """Test checksum for D1 (sLast) command."""
        assert calculate_checksum("D1") == 0xD2
    
    def test_checksum_17(self):
        """Test checksum for 17 (p01-p12) command."""
        assert calculate_checksum("17") == 0x18
    
    def test_checksum_0a17(self):
        """Test checksum for 0A17 (p01-p12 new) command."""
        assert calculate_checksum("0A17") == 0x22
    
    def test_checksum_overflow(self):
        """Test that checksum wraps at 256."""
        result = calculate_checksum("FFFF")
        assert 0 <= result <= 255
    
    def test_checksum_empty_command(self):
        """Test checksum with empty command."""
        # 01 + 00 = 01, should work
        result = calculate_checksum("")
        assert result == 0x01
    
    def test_checksum_long_command(self):
        """Test checksum with longer command."""
        result = calculate_checksum("AABBCCDD")
        expected = (0x01 + 0x00 + 0xAA + 0xBB + 0xCC + 0xDD) % 256
        assert result == expected


# =============================================================================
# Escape Sequence Tests
# =============================================================================

class TestEscaping:
    """Tests for escape sequence handling."""
    
    def test_escape_10(self):
        """Test that 0x10 is escaped to 0x10 0x10."""
        assert escape_data("10") == "1010"
    
    def test_escape_2b(self):
        """Test that 0x2B is escaped to 0x2B 0x18."""
        assert escape_data("2B") == "2B18"
    
    def test_escape_no_change(self):
        """Test that non-special bytes pass through unchanged."""
        assert escape_data("AABBCCDD") == "AABBCCDD"
    
    def test_escape_multiple_10(self):
        """Test escaping multiple 0x10 bytes."""
        assert escape_data("101010") == "101010101010"
    
    def test_escape_multiple_2b(self):
        """Test escaping multiple 0x2B bytes."""
        assert escape_data("2B2B") == "2B182B18"
    
    def test_escape_mixed(self):
        """Test escaping with multiple special bytes."""
        assert escape_data("10FF2B") == "1010FF2B18"
    
    def test_escape_at_boundaries(self):
        """Test escaping at string boundaries."""
        assert escape_data("10") == "1010"
        assert escape_data("AA10") == "AA1010"
        assert escape_data("10AA") == "1010AA"
    
    def test_unescape_10(self):
        """Test unescaping 0x10 0x10 -> 0x10."""
        assert unescape_data("1010") == "10"
    
    def test_unescape_2b(self):
        """Test unescaping 0x2B 0x18 -> 0x2B."""
        assert unescape_data("2B18") == "2B"
    
    def test_unescape_multiple(self):
        """Test unescaping with multiple escape sequences."""
        assert unescape_data("1010FF2B18") == "10FF2B"
    
    def test_unescape_no_change(self):
        """Test that non-escaped data passes through unchanged."""
        assert unescape_data("AABBCCDD") == "AABBCCDD"
    
    def test_roundtrip(self):
        """Test that escape/unescape is reversible for data with special bytes."""
        original = "10FF2BAA"
        escaped = escape_data(original)
        unescaped = unescape_data(escaped)
        assert unescaped == original
    
    def test_roundtrip_no_special(self):
        """Test roundtrip with no special bytes."""
        original = "AABBCCDD"
        escaped = escape_data(original)
        unescaped = unescape_data(escaped)
        assert unescaped == original


# =============================================================================
# Build Command Tests
# =============================================================================

class TestBuildCommand:
    """Tests for command building."""
    
    def test_build_fd(self):
        """Test building FD command."""
        cmd = build_command("FD")
        assert cmd == "0100FEFD1003"
    
    def test_build_fb(self):
        """Test building FB command."""
        cmd = build_command("FB")
        assert cmd == "0100FCFB1003"
    
    def test_build_09(self):
        """Test building 09 command."""
        cmd = build_command("09")
        assert cmd == "01000A091003"
    
    def test_build_with_escape_checksum(self):
        """Test building command where checksum requires escaping."""
        # Register "0F" -> checksum = 01 + 00 + 0F = 0x10 (needs escaping!)
        cmd = build_command("0F")
        assert "1010" in cmd  # Should contain escaped 0x10
        assert cmd == "010010100F1003"
    
    def test_build_with_escape_register(self):
        """Test building command where register contains escapable byte."""
        # Register with 0x10 in it
        cmd = build_command("1000")
        assert "1010" in cmd
    
    def test_build_command_structure(self):
        """Test that command has correct structure."""
        cmd = build_command("FD")
        assert cmd.startswith("0100")  # Header
        assert cmd.endswith("1003")    # Footer
    
    def test_build_long_register(self):
        """Test building command with 4-char register."""
        cmd = build_command("0A17")
        assert cmd.startswith("0100")
        assert cmd.endswith("1003")
        assert "0A17" in cmd or "0A17" in unescape_data(cmd[4:-4])


# =============================================================================
# Parse Response Tests
# =============================================================================

class TestParseResponse:
    """Tests for response parsing."""
    
    def test_parse_success(self):
        """Test parsing successful response."""
        response = parse_response("0100FEFD0702001003")
        assert response.success is True
        assert response.data == "FD070200"
    
    def test_parse_crc_error(self):
        """Test parsing CRC error response."""
        response = parse_response("0102001003")
        assert response.success is False
        assert response.error == THZError.CRC_ERROR
        assert "CRC" in response.error_message
    
    def test_parse_unknown_cmd(self):
        """Test parsing unknown command response."""
        response = parse_response("0103001003")
        assert response.success is False
        assert response.error == THZError.UNKNOWN_CMD
        assert "command" in response.error_message.lower()
    
    def test_parse_unknown_reg(self):
        """Test parsing unknown register response."""
        response = parse_response("0104001003")
        assert response.success is False
        assert response.error == THZError.UNKNOWN_REG
        assert "register" in response.error_message.lower()
    
    def test_parse_too_short(self):
        """Test parsing response that is too short."""
        response = parse_response("0100")
        assert response.success is False
        assert "too short" in response.error_message.lower()
    
    def test_parse_empty(self):
        """Test parsing empty response."""
        response = parse_response("")
        assert response.success is False
    
    def test_parse_none(self):
        """Test parsing None response."""
        response = parse_response(None)
        assert response.success is False
    
    def test_parse_unknown_header(self):
        """Test parsing response with unknown header."""
        response = parse_response("0199AABBCC1003")
        assert response.success is False
        assert "Unknown header" in response.error_message
    
    def test_parse_with_escape_sequences(self):
        """Test parsing response containing escape sequences."""
        response = parse_response("0100AA10101003")
        assert response.success is True
        assert "10" in response.data
    
    def test_parse_lowercase(self):
        """Test parsing lowercase hex."""
        response = parse_response("0100fefd0702001003")
        assert response.success is True
    
    def test_parse_extracts_data_correctly(self):
        """Test that data extraction removes header, checksum, and footer."""
        # 0100 (header) + FE (checksum) + AABBCCDD (data) + 1003 (footer)
        response = parse_response("0100FEAABBCCDD1003")
        assert response.success is True
        assert response.data == "AABBCCDD"


# =============================================================================
# Parse Temperature Tests
# =============================================================================

class TestParseTemp:
    """Tests for temperature parsing."""
    
    def test_parse_positive_temp(self):
        """Test parsing positive temperature."""
        assert parse_temp("00C8") == 20.0  # 200 / 10
    
    def test_parse_negative_temp(self):
        """Test parsing negative temperature."""
        assert parse_temp("FFEC") == -2.0  # -20 / 10
    
    def test_parse_zero_temp(self):
        """Test parsing zero temperature."""
        assert parse_temp("0000") == 0.0
    
    def test_parse_unsigned(self):
        """Test parsing as unsigned value."""
        assert parse_temp("FFEC", signed=False) == 6551.6
    
    def test_parse_decimal(self):
        """Test temperature with decimal places."""
        assert parse_temp("0043") == 6.7  # 67 / 10
    
    def test_parse_large_positive(self):
        """Test large positive temperature."""
        assert parse_temp("0320") == 80.0  # 800 / 10
    
    def test_parse_large_negative(self):
        """Test large negative temperature."""
        assert parse_temp("FD8F") == -62.5  # -625 / 10 (approx -60 for no sensor)
    
    def test_parse_boundary_signed(self):
        """Test boundary between positive and negative."""
        assert parse_temp("7FFF") == 3276.7  # Max positive
        assert parse_temp("8000") == -3276.8  # Min negative (signed)


# =============================================================================
# Parse Firmware Tests
# =============================================================================

class TestParseFirmware:
    """Tests for firmware parsing."""
    
    def test_parse_firmware_702(self):
        """Test parsing firmware version 7.02."""
        result = parse_firmware("FD02BE")  # 0x02BE = 702
        assert result["version"] == "7.02"
        assert result["version_raw"] == 702
    
    def test_parse_firmware_206(self):
        """Test parsing firmware version 2.06."""
        result = parse_firmware("FD00CE")  # 0x00CE = 206
        assert result["version"] == "2.06"
        assert result["version_raw"] == 206
    
    def test_parse_firmware_100(self):
        """Test parsing firmware version 1.00."""
        result = parse_firmware("FD0064")  # 0x0064 = 100
        assert result["version"] == "1.00"
        assert result["version_raw"] == 100
    
    def test_parse_firmware_short(self):
        """Test parsing with insufficient data."""
        result = parse_firmware("FD")
        assert "version" not in result
    
    def test_parse_firmware_empty(self):
        """Test parsing empty data."""
        result = parse_firmware("")
        assert "version" not in result
    
    def test_parse_firmware_with_extra_data(self):
        """Test parsing with extra data."""
        result = parse_firmware("FD02BEAABBCCDD")
        assert result["version"] == "7.02"


# =============================================================================
# Parse sGlobal Tests
# =============================================================================

class TestParseSglobal:
    """Tests for sGlobal parsing."""
    
    def test_parse_sglobal_basic(self):
        """Test parsing basic sGlobal data."""
        # FB + 10 temperature values at 20.0°C = 0x00C8
        data = "FB" + "00C8" * 10
        result = parse_sglobal(data)
        
        assert result["collectorTemp"] == 20.0
        assert result["outsideTemp"] == 20.0
        assert result["flowTemp"] == 20.0
        assert result["returnTemp"] == 20.0
        assert result["hotGasTemp"] == 20.0
        assert result["dhwTemp"] == 20.0
        assert result["flowTempHC2"] == 20.0
        assert result["insideTemp"] == 20.0
    
    def test_parse_sglobal_negative_outside(self):
        """Test parsing negative outside temperature."""
        data = "FB" + "0000" + "FFCE" + "00C8" * 8  # -5.0°C outside
        result = parse_sglobal(data)
        assert result["outsideTemp"] == -5.0
    
    def test_parse_sglobal_invalid_inside(self):
        """Test detecting invalid inside temperature (no sensor)."""
        # Inside temp -60.0°C = 0xFDA8 - sensor not connected, should not be in result
        data = "FB" + "0000" * 7 + "FDA8" + "0000" * 2
        result = parse_sglobal(data)
        # insideTemp with -60.0 is filtered out (sensor not connected)
        assert "insideTemp" not in result
    
    def test_parse_sglobal_valid_inside(self):
        """Test valid inside temperature."""
        data = "FB" + "0000" * 7 + "00D7" + "0000" * 2  # 21.5°C
        result = parse_sglobal(data)
        assert result["insideTemp"] == 21.5
    
    def test_parse_sglobal_short_data(self):
        """Test parsing with minimal data."""
        data = "FB" + "0043"  # Only collector temp
        result = parse_sglobal(data)
        assert result["collectorTemp"] == 6.7
        assert "outsideTemp" not in result
    
    def test_parse_sglobal_empty(self):
        """Test parsing with only command echo."""
        result = parse_sglobal("FB")
        assert "collectorTemp" not in result
    
    def test_parse_sglobal_ventilator_power(self):
        """Test parsing ventilator power at position 72-73."""
        # mainVentilatorPower is at position 72-73 (chars 72-73 after FB prefix)
        # So we need: FB (removed) + 72 chars padding + 39 (power value)
        data = "FB" + "00" * 36 + "39"  # 36 bytes = 72 chars, then 0x39 = 57
        result = parse_sglobal(data)
        assert result["mainVentilatorPower"] == 57


# =============================================================================
# Parse sHC1 Tests
# =============================================================================

class TestParseShc1:
    """Tests for sHC1 parsing - positions verified with real device data."""
    
    def test_parse_shc1_basic(self):
        """Test parsing heating circuit 1 data with verified positions."""
        # Real device positions: outsideTemp at 0-3, returnTemp at 8-11, flowTemp at 16-19
        # F4 + outsideTemp(0-3) + padding(4-7) + returnTemp(8-11) + padding(12-15) + flowTemp(16-19)
        data = "F4" + "00C8" + "0000" + "00BE" + "0000" + "015E"  # 2 + 20 = 22 chars
        result = parse_shc1(data)
        
        assert result["hc1OutsideTemp"] == 20.0
        assert result["hc1ReturnTemp"] == 19.0
        assert result["hc1FlowTemp"] == 35.0
    
    def test_parse_shc1_with_temperatures(self):
        """Test parsing with all temperature fields."""
        # Real positions: outsideTemp(0-3), returnTemp(8-11), flowTemp(16-19), 
        # heatSetTemp(24-27), heatTemp(28-31)
        data = "F4" + "00C8" + "0000" + "00BE" + "0000" + "015E" + "0000" + "014A" + "00DC"
        # pos 0-3: 00C8=20.0, pos 8-11: 00BE=19.0, pos 16-19: 015E=35.0, 
        # pos 24-27: 014A=33.0, pos 28-31: 00DC=22.0
        result = parse_shc1(data)
        
        assert result.get("hc1OutsideTemp") == 20.0
        assert result.get("hc1ReturnTemp") == 19.0
        assert result.get("hc1FlowTemp") == 35.0
        assert result.get("heatSetTemp") == 33.0
        assert result.get("heatTemp") == 22.0
    
    def test_parse_shc1_with_cycles(self):
        """Test parsing with on/off cycles."""
        # After skipping "F4" (2 chars), need d[76:80] for cycles
        # So d needs 80 chars = 76 chars padding + 4 chars cycles
        # Total: "F4" (2) + 76 chars + 4 chars = 82 chars
        data = "F4" + "0000" * 19 + "0017"  # 2 + 76 + 4 = 82 chars, cycles=23
        result = parse_shc1(data)
        assert result["onOffCycles"] == 23
    
    def test_parse_shc1_short(self):
        """Test parsing with minimal data - only outsideTemp at pos 0-3."""
        data = "F4" + "00C8"  # F4 + outsideTemp=20.0 at pos 0-3
        result = parse_shc1(data)
        assert result["hc1OutsideTemp"] == 20.0
        assert "hc1FlowTemp" not in result  # Not enough data
    
    def test_parse_shc1_empty(self):
        """Test parsing with only command echo."""
        result = parse_shc1("F4")
        assert "hc1FlowTemp" not in result


# =============================================================================
# Parse DHW Tests
# =============================================================================

class TestParseDhw:
    """Tests for sDHW (F3) parsing - positions verified with real device data."""
    
    def test_parse_dhw_basic(self):
        """Test parsing DHW data with temperature values."""
        # Real positions: dhwTemp at 0-3, outsideTemp at 4-7, dhwSetTemp at 8-11
        data = "F3" + "01D6" + "00C8" + "01C2"  # dhwTemp=47.0, outside=20.0, setTemp=45.0
        result = parse_dhw(data)
        
        assert result["dhwTemp"] == 47.0
        assert result["dhwOutsideTemp"] == 20.0
        assert result["dhwSetTemp"] == 45.0
    
    def test_parse_dhw_with_block_times(self):
        """Test parsing with compressor block time."""
        # compBlockTime at pos 12-15
        data = "F3" + "01D6" + "00C8" + "01C2" + "003C"  # compBlockTime=60 at pos 12-15
        result = parse_dhw(data)
        assert result.get("dhwCompBlockTime") == 60
    
    def test_parse_dhw_with_mode(self):
        """Test parsing with booster stage and op mode."""
        # Real positions: boosterStage at 24-25, pasteurisationMode at 28-29, opMode at 30-31
        # Need 32 chars after F3 to get to opMode
        # F3 + 12 chars temps + 12 chars padding + booster(2) + 2 padding + pasteur(2) + opMode(2)
        padding1 = "0000" * 3  # 12 chars for positions 12-23
        data = "F3" + "01D6" + "00C8" + "01C2" + padding1 + "02" + "00" + "01" + "01"
        # pos 24-25: 02 (booster=2), pos 28-29: 01 (pasteur), pos 30-31: 01 (opMode)
        result = parse_dhw(data)
        assert result.get("dhwBoosterStage") == 2
        assert result.get("pasteurisationMode") == 1
        assert result.get("pasteurisationActive") == True
        assert result.get("dhwOpMode") == 1
        assert result.get("dhwOpModeText") == "normal"
    
    def test_parse_dhw_short(self):
        """Test parsing with minimal data."""
        data = "F3" + "01D6"  # Only dhwTemp at pos 0-3
        result = parse_dhw(data)
        assert result["dhwTemp"] == 47.0
        assert "dhwSetTemp" not in result
    
    def test_parse_dhw_empty(self):
        """Test parsing with only command echo."""
        result = parse_dhw("F3")
        assert "dhwTemp" not in result


# =============================================================================
# Parse p01 Tests
# =============================================================================

class TestParseP01:
    """Tests for p01-p12 parsing."""
    
    def test_parse_p01_basic(self):
        """Test parsing setpoints."""
        # 17 + p01(4) + p02(4) + p03(4) + p04(4)
        data = "17" + "00D2" + "00B4" + "0000" + "01E0"  # 21.0, 18.0, 0, 48.0
        result = parse_p01(data)
        
        assert result["p01RoomTempDay"] == 21.0
        assert result["p02RoomTempNight"] == 18.0
        assert result["p04DHWsetTempDay"] == 48.0
    
    def test_parse_p01_with_fan_stages(self):
        """Test parsing fan stages."""
        # Need 30 chars for fan stages at positions 24-26 and 26-28
        data = "17" + "0000" * 6 + "02" + "01" + "0000"  # fan day=2, night=1
        result = parse_p01(data)
        assert result["p07FanStageDay"] == 2
        assert result["p08FanStageNight"] == 1
    
    def test_parse_p01_short(self):
        """Test parsing with minimal data."""
        data = "17" + "00D2"  # Only p01
        result = parse_p01(data)
        assert result["p01RoomTempDay"] == 21.0
        assert "p02RoomTempNight" not in result


# =============================================================================
# Parse History Tests
# =============================================================================

class TestParseHistory:
    """Tests for history parsing."""
    
    def test_parse_history_basic(self):
        """Test parsing operating hours."""
        # 09 + 5 values at 1000 hours = 0x03E8
        data = "09" + "03E8" * 5
        result = parse_history(data)
        
        assert result["compressorHeatingHours"] == 1000
        assert result["compressorCoolingHours"] == 1000
        assert result["compressorDHWHours"] == 1000
        assert result["boosterDHWHours"] == 1000
        assert result["boosterHeatingHours"] == 1000
    
    def test_parse_history_real_data(self):
        """Test parsing with real-ish values."""
        # compressorHeatingHours: 3963 = 0x0F7B, boosterHeatingHours: 48 = 0x0030
        data = "09" + "0F7B" + "0000" + "0000" + "0000" + "0030"
        result = parse_history(data)
        
        assert result["compressorHeatingHours"] == 3963
        assert result["boosterHeatingHours"] == 48
    
    def test_parse_history_zero(self):
        """Test parsing all zeros."""
        data = "09" + "0000" * 5
        result = parse_history(data)
        
        assert result["compressorHeatingHours"] == 0
        assert result["boosterHeatingHours"] == 0
    
    def test_parse_history_short(self):
        """Test parsing with minimal data."""
        data = "09" + "0F7B"  # Only compressorHeatingHours
        result = parse_history(data)
        assert result["compressorHeatingHours"] == 3963
        assert "compressorCoolingHours" not in result


# =============================================================================
# Parse Time Tests
# =============================================================================

class TestParseTime:
    """Tests for time parsing."""
    
    def test_parse_time_basic(self):
        """Test parsing date/time based on real device response."""
        # Real response: FC04142417190C05
        data = "FC04142417190C05"
        result = parse_time(data)
        
        assert result["weekday"] == 4  # Thursday
        assert result["hour"] == 20    # 0x14 = 20
        assert result["minute"] == 36  # 0x24 = 36
        assert result["second"] == 23  # 0x17 = 23
        assert result["year"] == 2025  # 0x19 = 25 + 2000
        assert result["month"] == 12   # 0x0C = 12
        assert result["day"] == 5      # 0x05 = 5
    
    def test_parse_time_monday(self):
        """Test parsing Monday."""
        data = "FC01000000190101"  # Monday, 00:00:00, 2025-01-01
        result = parse_time(data)
        assert result["weekday"] == 1
    
    def test_parse_time_sunday(self):
        """Test parsing Sunday."""
        data = "FC07173B3B181231"  # Sunday, 23:59:59, 2024-12-31
        result = parse_time(data)
        assert result["weekday"] == 7
        assert result["hour"] == 23
        assert result["minute"] == 59
        assert result["second"] == 59
    
    def test_parse_time_year_2020(self):
        """Test parsing year 2020."""
        data = "FC0100000014010F"  # Year 0x14 = 20 -> 2020
        result = parse_time(data)
        assert result["year"] == 2020
    
    def test_parse_time_short(self):
        """Test parsing with minimal data."""
        data = "FC04"  # Only weekday
        result = parse_time(data)
        assert result["weekday"] == 4
        assert "hour" not in result


# =============================================================================
# Parse Errors Tests
# =============================================================================

class TestParseErrors:
    """Tests for error parsing."""
    
    def test_parse_errors_none(self):
        """Test parsing with no errors."""
        data = "D100"
        result = parse_errors(data)
        assert result["numberOfFaults"] == 0
    
    def test_parse_errors_some(self):
        """Test parsing with some errors."""
        data = "D103"
        result = parse_errors(data)
        assert result["numberOfFaults"] == 3
    
    def test_parse_errors_max(self):
        """Test parsing max errors (255)."""
        data = "D1FF"
        result = parse_errors(data)
        assert result["numberOfFaults"] == 255
    
    def test_parse_errors_short(self):
        """Test parsing with insufficient data."""
        data = "D1"
        result = parse_errors(data)
        assert "numberOfFaults" not in result


# =============================================================================
# PARSERS Registry Tests
# =============================================================================

class TestParsersRegistry:
    """Tests for PARSERS registry."""
    
    def test_all_parsers_callable(self):
        """Test that all parsers are callable functions."""
        for name, parser in PARSERS.items():
            assert callable(parser), f"Parser '{name}' is not callable"
    
    def test_parsers_return_dict(self):
        """Test that all parsers return dictionaries."""
        test_data = {
            "firmware": "FD02BE",
            "sglobal": "FB" + "00C8" * 10,
            "shc1": "F4" + "0000" * 10,
            "p01": "17" + "0000" * 10,
            "history": "09" + "0000" * 5,
            "time": "FC04142417190C05",
            "errors": "D100",
        }
        for name, parser in PARSERS.items():
            data = test_data.get(name, name.upper() + "0000")
            result = parser(data)
            assert isinstance(result, dict), f"Parser '{name}' did not return dict"
    
    def test_parsers_handle_empty_gracefully(self):
        """Test that parsers handle empty data without crashing."""
        for name, parser in PARSERS.items():
            result = parser("")
            assert isinstance(result, dict)
    
    def test_parsers_handle_invalid_gracefully(self):
        """Test that parsers handle invalid data without crashing."""
        for name, parser in PARSERS.items():
            result = parser("ZZZZ")  # Invalid hex
            assert isinstance(result, dict)
            # Should have parse_error or be empty
            assert "parse_error" in result or len(result) == 0


# =============================================================================
# THZConnection Tests (Mocked)
# =============================================================================

class TestTHZConnection:
    """Tests for THZConnection class with mocked serial."""
    
    def test_init(self):
        """Test connection initialization."""
        conn = THZConnection("/dev/ttyUSB0", baudrate=57600)
        assert conn.port == "/dev/ttyUSB0"
        assert conn.baudrate == 57600
        assert conn.timeout == 3.0
        assert conn.write_timeout == 2.0
        assert conn._serial is None
    
    def test_init_defaults(self):
        """Test connection initialization with defaults."""
        conn = THZConnection("/dev/ttyUSB1")
        assert conn.baudrate == 115200
    
    def test_is_connected_false(self):
        """Test is_connected when not connected."""
        conn = THZConnection("/dev/ttyUSB0")
        assert conn.is_connected() is False
    
    @patch('thz_protocol.serial.Serial')
    def test_connect(self, mock_serial_class):
        """Test connection establishment."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        conn = THZConnection("/dev/ttyUSB0")
        conn.connect()
        
        mock_serial_class.assert_called_once()
        mock_serial.reset_input_buffer.assert_called()
        mock_serial.reset_output_buffer.assert_called()
    
    @patch('thz_protocol.serial.Serial')
    def test_disconnect(self, mock_serial_class):
        """Test disconnection."""
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial
        
        conn = THZConnection("/dev/ttyUSB0")
        conn.connect()
        conn.disconnect()
        
        mock_serial.close.assert_called_once()
        assert conn._serial is None
    
    @patch('thz_protocol.serial.Serial')
    def test_is_connected_true(self, mock_serial_class):
        """Test is_connected when connected."""
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial
        
        conn = THZConnection("/dev/ttyUSB0")
        conn.connect()
        
        assert conn.is_connected() is True
    
    @patch('thz_protocol.serial.Serial')
    def test_context_manager(self, mock_serial_class):
        """Test context manager usage."""
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial
        
        with THZConnection("/dev/ttyUSB0") as conn:
            assert conn.is_connected()
        
        mock_serial.close.assert_called()
    
    def test_send_command_not_connected(self):
        """Test send_command when not connected."""
        conn = THZConnection("/dev/ttyUSB0")
        response = conn.send_command("FD")
        
        assert response.success is False
        assert "Not connected" in response.error_message
    
    @patch('thz_protocol.serial.Serial')
    @patch('thz_protocol.time.sleep')
    def test_send_command_step0_fail(self, mock_sleep, mock_serial_class):
        """Test send_command when step 0 fails."""
        mock_serial = MagicMock()
        mock_serial.in_waiting = 1
        mock_serial.read.return_value = b'\xFF'  # Wrong response
        mock_serial_class.return_value = mock_serial
        
        conn = THZConnection("/dev/ttyUSB0")
        conn.connect()
        response = conn.send_command("FD")
        
        assert response.success is False
        assert "Step 0 failed" in response.error_message
    
    def test_read_register_not_connected(self):
        """Test read_register when not connected."""
        conn = THZConnection("/dev/ttyUSB0")
        result = conn.read_register("FD")
        
        assert "error" in result


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the protocol."""
    
    def test_full_command_response_cycle(self):
        """Test building command and parsing response."""
        cmd = build_command("FD")
        assert cmd.startswith("0100")
        assert cmd.endswith("1003")
        
        # Simulate response (firmware 7.02)
        response_data = "0100" + "FE" + "FD02BE" + "1003"
        response = parse_response(response_data)
        
        assert response.success
        firmware = parse_firmware(response.data)
        assert firmware["version"] == "7.02"
    
    def test_command_with_real_sglobal_data(self):
        """Test with actual response data from device."""
        # Real-ish response from FB register
        real_data = "FBFDA80043012A0118024001CC"
        result = parse_sglobal(real_data)
        
        assert result["outsideTemp"] == 6.7
        assert result["flowTemp"] == 29.8
        assert result["returnTemp"] == 28.0
    
    def test_all_register_commands_build(self):
        """Test that all register commands can be built."""
        for reg in REGISTERS:
            cmd = build_command(reg)
            assert cmd.startswith("0100")
            assert cmd.endswith("1003")
            assert len(cmd) >= 12  # Minimum: 0100 + XX + reg(2) + 1003
    
    def test_error_responses_all_types(self):
        """Test all error response types."""
        errors = [
            ("0102001003", THZError.CRC_ERROR),
            ("0103001003", THZError.UNKNOWN_CMD),
            ("0104001003", THZError.UNKNOWN_REG),
        ]
        for data, expected_error in errors:
            response = parse_response(data)
            assert response.success is False
            assert response.error == expected_error


# =============================================================================
# Real Device Data Tests (Firmware 7.02)
# =============================================================================

class TestRealDeviceData:
    """Tests using real device data captured from Tecalor THZ with FW 7.02."""
    
    # Raw data from real device dump
    RAW_FD = "FD02BE"
    RAW_FB = "FBFDA8002A01170116022F01C18001FDA8000C0128100817000000000000000000000000003900000000032A070B00000000000000000000007E000000000116013A0095008A011A00000000097D"
    RAW_F3 = "F301C1002901E000001008202D02010001759E17"
    RAW_F4 = "F4002A000001180000011A011A011800000201100800640100000000CD01B5000000CD020000000017"
    RAW_FC = "FC04151728190C05"
    RAW_09 = "090F7C0000023000000030000007A3"
    RAW_D1 = "D10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    
    def test_parse_real_firmware(self):
        """Test parsing real firmware data."""
        result = parse_firmware(self.RAW_FD)
        assert result["version"] == "7.02"
        assert result["version_raw"] == 702
    
    def test_parse_real_sglobal_temperatures(self):
        """Test parsing real sGlobal temperatures."""
        result = parse_sglobal(self.RAW_FB)
        
        # These values were verified against the heat pump display
        assert result["outsideTemp"] == 4.2
        assert result["flowTemp"] == 27.9
        assert result["returnTemp"] == 27.8
        assert result["hotGasTemp"] == 55.9
        assert result["dhwTemp"] == 44.9
        
        # Collector temp -60.0 means no sensor (0xFDA8) - kept for diagnostics
        assert result["collectorTemp"] == -60.0
        
        # flowTempHC2 -3276.7 means not installed (0x8001)
        assert "flowTempHC2" not in result  # Filtered as not installed
    
    def test_parse_real_sglobal_evaporator_condenser(self):
        """Test parsing evaporator and condenser temps from real data."""
        result = parse_sglobal(self.RAW_FB)
        
        assert result["evaporatorTemp"] == 1.2
        assert result["condenserTemp"] == 29.6
    
    def test_parse_real_dhw(self):
        """Test parsing real DHW (F3) data."""
        result = parse_dhw(self.RAW_F3)
        
        # DHW temperatures
        assert result["dhwTemp"] == 44.9
        assert result["dhwOutsideTemp"] == 4.1
        assert result["dhwSetTemp"] == 48.0
        
        # DHW operation mode
        assert result.get("dhwOpMode") in [1, 2, 3]  # normal, setback, or standby
    
    def test_parse_real_shc1(self):
        """Test parsing real HC1 (F4) data."""
        result = parse_shc1(self.RAW_F4)
        
        # Temperatures
        assert result["hc1OutsideTemp"] == 4.2
        assert result["hc1ReturnTemp"] == 28.0
        assert result["hc1FlowTemp"] == 28.2
        
        # On/off cycles
        assert result["onOffCycles"] == 23
    
    def test_parse_real_time(self):
        """Test parsing real time (FC) data."""
        result = parse_time(self.RAW_FC)
        
        assert result["weekday"] == 4  # Thursday
        assert result["hour"] == 21
        assert result["minute"] == 23
        assert result["year"] == 2025
        assert result["month"] == 12
        assert result["day"] == 5
    
    def test_parse_real_history(self):
        """Test parsing real history (09) data."""
        result = parse_history(self.RAW_09)
        
        # Compressor hours
        assert result["compressorHeatingHours"] == 3964
        assert result["compressorDHWHours"] == 560
        
        # Booster hours
        assert result["boosterHeatingHours"] == 48
    
    def test_parse_real_errors_none(self):
        """Test parsing real error data with no faults."""
        result = parse_errors(self.RAW_D1)
        assert result["numberOfFaults"] == 0

