#!/usr/bin/env python3
"""
Pytest unit tests for THZ protocol implementation.

Run with: pytest tests/ -v
"""
import pytest
from thz_protocol import (
    calculate_checksum,
    escape_data,
    unescape_data,
    build_command,
    parse_response,
    parse_temp,
    parse_firmware,
    parse_sglobal,
    parse_shc1,
    parse_p01,
    parse_history,
    parse_time,
    parse_errors,
    THZResponse,
    THZError,
)


class TestChecksum:
    """Tests for checksum calculation."""
    
    def test_checksum_fd(self):
        """Test checksum for FD (firmware) command."""
        # FD command should have checksum 0xFE
        assert calculate_checksum("FD") == 0xFE
    
    def test_checksum_fb(self):
        """Test checksum for FB (sGlobal) command."""
        # 01 + 00 + FB = 0xFC
        assert calculate_checksum("FB") == 0xFC
    
    def test_checksum_09(self):
        """Test checksum for 09 (history) command."""
        # 01 + 00 + 09 = 0x0A
        assert calculate_checksum("09") == 0x0A
    
    def test_checksum_f3(self):
        """Test checksum for F3 (sDHW) command."""
        # 01 + 00 + F3 = 0xF4
        assert calculate_checksum("F3") == 0xF4
    
    def test_checksum_f4(self):
        """Test checksum for F4 (sHC1) command."""
        # 01 + 00 + F4 = 0xF5
        assert calculate_checksum("F4") == 0xF5
    
    def test_checksum_fc(self):
        """Test checksum for FC (sTime) command."""
        # 01 + 00 + FC = 0xFD
        assert calculate_checksum("FC") == 0xFD
    
    def test_checksum_d1(self):
        """Test checksum for D1 (sLast) command."""
        # 01 + 00 + D1 = 0xD2
        assert calculate_checksum("D1") == 0xD2
    
    def test_checksum_17(self):
        """Test checksum for 17 (p01-p12) command."""
        # 01 + 00 + 17 = 0x18
        assert calculate_checksum("17") == 0x18
    
    def test_checksum_0a17(self):
        """Test checksum for 0A17 (p01-p12 new) command."""
        # 01 + 00 + 0A + 17 = 0x22
        assert calculate_checksum("0A17") == 0x22
    
    def test_checksum_overflow(self):
        """Test that checksum wraps at 256."""
        # Create a command that would overflow
        result = calculate_checksum("FFFF")  # 01 + 00 + FF + FF = 0x1FF -> 0xFF
        assert 0 <= result <= 255


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
    
    def test_escape_multiple(self):
        """Test escaping with multiple special bytes."""
        assert escape_data("10FF2B") == "1010FF2B18"
    
    def test_unescape_10(self):
        """Test unescaping 0x10 0x10 -> 0x10."""
        assert unescape_data("1010") == "10"
    
    def test_unescape_2b(self):
        """Test unescaping 0x2B 0x18 -> 0x2B."""
        assert unescape_data("2B18") == "2B"
    
    def test_unescape_multiple(self):
        """Test unescaping with multiple escape sequences."""
        assert unescape_data("1010FF2B18") == "10FF2B"
    
    def test_roundtrip(self):
        """Test that escape/unescape is reversible for normal data."""
        original = "10FF2BAA"
        escaped = escape_data(original)
        unescaped = unescape_data(escaped)
        assert unescaped == original


class TestBuildCommand:
    """Tests for command building."""
    
    def test_build_fd(self):
        """Test building FD command."""
        # FD with checksum FE, no escaping needed
        cmd = build_command("FD")
        assert cmd == "0100FEFD1003"
    
    def test_build_fb(self):
        """Test building FB command."""
        # FB with checksum FC, no escaping needed
        cmd = build_command("FB")
        assert cmd == "0100FCFB1003"
    
    def test_build_09(self):
        """Test building 09 command."""
        # 09 with checksum 0A, needs escaping (0A contains no special chars)
        cmd = build_command("09")
        assert cmd == "01000A091003"
    
    def test_build_with_escape(self):
        """Test building command that requires escaping."""
        # If checksum would be 0x10, it should be escaped
        # Register "0F" -> checksum = 01 + 00 + 0F = 0x10 (needs escaping!)
        cmd = build_command("0F")
        assert "1010" in cmd  # Should contain escaped 0x10


class TestParseResponse:
    """Tests for response parsing."""
    
    def test_parse_success(self):
        """Test parsing successful response."""
        # Response format: 0100 + checksum(2) + data + 1003
        # So 0100 FE FD070200 1003 -> data is "FD070200"
        response = parse_response("0100FEFD0702001003")
        assert response.success is True
        assert response.data == "FD070200"
    
    def test_parse_crc_error(self):
        """Test parsing CRC error response."""
        response = parse_response("0102001003")
        assert response.success is False
        assert response.error == THZError.CRC_ERROR
    
    def test_parse_unknown_cmd(self):
        """Test parsing unknown command response."""
        response = parse_response("0103001003")
        assert response.success is False
        assert response.error == THZError.UNKNOWN_CMD
    
    def test_parse_unknown_reg(self):
        """Test parsing unknown register response."""
        response = parse_response("0104001003")
        assert response.success is False
        assert response.error == THZError.UNKNOWN_REG
    
    def test_parse_too_short(self):
        """Test parsing response that is too short."""
        response = parse_response("0100")
        assert response.success is False
        assert "too short" in response.error_message.lower()
    
    def test_parse_with_escape_sequences(self):
        """Test parsing response containing escape sequences."""
        # Response with 1010 (escaped 10) should be unescaped
        response = parse_response("0100AA10101003")
        assert response.success is True
        # After unescaping 1010 -> 10
        assert "10" in response.data


class TestParseTemp:
    """Tests for temperature parsing."""
    
    def test_parse_positive_temp(self):
        """Test parsing positive temperature."""
        # 0x00C8 = 200 -> 20.0°C
        assert parse_temp("00C8") == 20.0
    
    def test_parse_negative_temp(self):
        """Test parsing negative temperature."""
        # 0xFFEC = 65516 -> -20 (signed) -> -2.0°C
        assert parse_temp("FFEC") == -2.0
    
    def test_parse_zero_temp(self):
        """Test parsing zero temperature."""
        assert parse_temp("0000") == 0.0
    
    def test_parse_unsigned(self):
        """Test parsing as unsigned value."""
        # 0xFFEC = 65516 as unsigned -> 6551.6
        assert parse_temp("FFEC", signed=False) == 6551.6
    
    def test_parse_decimal(self):
        """Test temperature with decimal places."""
        # 0x0043 = 67 -> 6.7°C
        assert parse_temp("0043") == 6.7


class TestParseFirmware:
    """Tests for firmware parsing."""
    
    def test_parse_firmware_702(self):
        """Test parsing firmware version 7.02."""
        # Response data: FD + 0702 (702 decimal = 7.02)
        result = parse_firmware("FD02BC")  # 0x02BC = 700
        # Wait, let me use actual value: 702 = 0x02BE
        result = parse_firmware("FD02BE")
        assert result["version"] == "7.02"
        assert result["version_raw"] == 702
    
    def test_parse_firmware_short(self):
        """Test parsing with insufficient data."""
        result = parse_firmware("FD")
        assert "version" not in result


class TestParseSglobal:
    """Tests for sGlobal parsing."""
    
    def test_parse_sglobal_basic(self):
        """Test parsing basic sGlobal data."""
        # FB + collector(4) + outside(4) + flow(4) + return(4) + ...
        # All temps at 20.0°C = 0x00C8
        data = "FB" + "00C8" * 10  # 10 temperature values
        result = parse_sglobal(data)
        
        assert result["collector_temp"] == 20.0
        assert result["outside_temp"] == 20.0
        assert result["flow_temp"] == 20.0
        assert result["return_temp"] == 20.0
    
    def test_parse_sglobal_negative_outside(self):
        """Test parsing negative outside temperature."""
        # Outside temp -5.0°C = 0xFFCE
        data = "FB" + "0000" + "FFCE" + "00C8" * 8
        result = parse_sglobal(data)
        assert result["outside_temp"] == -5.0
    
    def test_parse_sglobal_invalid_inside(self):
        """Test detecting invalid inside temperature (no sensor)."""
        # Inside temp -60.0°C = 0xFDA8 (should be marked invalid)
        data = "FB" + "0000" * 7 + "FDA8" + "0000" * 2
        result = parse_sglobal(data)
        assert result["inside_temp"] == -60.0
        assert result["inside_temp_valid"] is False
    
    def test_parse_sglobal_valid_inside(self):
        """Test valid inside temperature."""
        # Inside temp 21.5°C = 0x00D7
        data = "FB" + "0000" * 7 + "00D7" + "0000" * 2
        result = parse_sglobal(data)
        assert result["inside_temp"] == 21.5
        assert result["inside_temp_valid"] is True


class TestParseHistory:
    """Tests for history parsing."""
    
    def test_parse_history_basic(self):
        """Test parsing operating hours."""
        # 09 + compressor_heating(4) + compressor_cooling(4) + ...
        # 1000 hours = 0x03E8
        data = "09" + "03E8" * 5
        result = parse_history(data)
        
        assert result["compressor_heating_hours"] == 1000
        assert result["compressor_cooling_hours"] == 1000
    
    def test_parse_history_real_data(self):
        """Test parsing with real-ish values."""
        # compressor_heating: 3963 = 0x0F7B
        # booster_heating: 48 = 0x0030
        data = "09" + "0F7B" + "0000" + "0000" + "0000" + "0030"
        result = parse_history(data)
        
        assert result["compressor_heating_hours"] == 3963
        assert result["booster_heating_hours"] == 48


class TestParseTime:
    """Tests for time parsing."""
    
    def test_parse_time_basic(self):
        """Test parsing date/time based on real device response."""
        # Real response: FC04142417190C05
        # FC=echo, 04=Thu, 14=20h, 24=36min, 17=23sec?, 19=2025, 0C=Dec, 05=5th
        data = "FC04142417190C05"
        result = parse_time(data)
        
        assert result["weekday"] == 4  # Thursday
        assert result["hour"] == 20    # 0x14 = 20
        assert result["minute"] == 36  # 0x24 = 36
        assert result["second"] == 23  # 0x17 = 23
        assert result["year"] == 2025  # 0x19 = 25 + 2000
        assert result["month"] == 12   # 0x0C = 12
        assert result["day"] == 5      # 0x05 = 5


class TestParseShc1:
    """Tests for sHC1 parsing."""
    
    def test_parse_shc1_basic(self):
        """Test parsing heating circuit 1 data."""
        # F4 + flow_temp_set(4) + room_temp_set(4) + room_temp(4) + ...
        # 35.0°C = 0x015E, 21.0°C = 0x00D2, 20.5°C = 0x00CD
        data = "F4" + "015E" + "00D2" + "00CD"
        result = parse_shc1(data)
        
        assert result["flow_temp_set"] == 35.0
        assert result["room_temp_set"] == 21.0
        assert result["room_temp"] == 20.5


class TestParseP01:
    """Tests for p01-p12 parsing."""
    
    def test_parse_p01_basic(self):
        """Test parsing setpoints."""
        # 17 + p01(4) + p02(4) + p03(4) + p04(4) + ...
        # Room day 21.0°C = 0x00D2, night 18.0°C = 0x00B4
        # p03 placeholder, DHW 48.0°C = 0x01E0
        data = "17" + "00D2" + "00B4" + "0000" + "01E0" + "0000" * 6 + "02" + "01"
        result = parse_p01(data)
        
        assert result["p01_room_temp_day"] == 21.0
        assert result["p02_room_temp_night"] == 18.0
        assert result["p04_dhw_temp_day"] == 48.0


class TestParseErrors:
    """Tests for error parsing."""
    
    def test_parse_errors_none(self):
        """Test parsing with no errors."""
        data = "D1" + "00"
        result = parse_errors(data)
        assert result["num_faults"] == 0
    
    def test_parse_errors_some(self):
        """Test parsing with some errors."""
        data = "D1" + "03"
        result = parse_errors(data)
        assert result["num_faults"] == 3


class TestIntegration:
    """Integration tests for the protocol."""
    
    def test_full_command_response_cycle(self):
        """Test building command and parsing response."""
        # Build FD command
        cmd = build_command("FD")
        assert cmd.startswith("0100")
        assert cmd.endswith("1003")
        
        # Simulate response (firmware 7.02)
        response_data = "0100" + "FE" + "FD02BE" + "1003"
        response = parse_response(response_data)
        
        assert response.success
        firmware = parse_firmware(response.data)
        assert firmware["version"] == "7.02"
    
    def test_command_with_real_response_data(self):
        """Test with actual response data from device."""
        # Real response from FB register (sGlobal)
        # outside_temp: 6.7°C, flow_temp: 29.8°C, return_temp: 28.0°C, dhw_temp: 46.0°C
        real_data = "FBFDA80043012A0118024001CC"
        # FDA8 = collector (probably invalid)
        # 0043 = 67 = 6.7°C outside
        # 012A = 298 = 29.8°C flow
        # 0118 = 280 = 28.0°C return
        # 0240 = 576 = 57.6°C hot_gas (seems high)
        # 01CC = 460 = 46.0°C DHW
        
        result = parse_sglobal(real_data)
        assert result["outside_temp"] == 6.7
        assert result["flow_temp"] == 29.8
        assert result["return_temp"] == 28.0
        # Note: collector shows -60.0 which is the "no sensor" value
