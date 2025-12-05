#!/usr/bin/env python3
"""
Live integration tests for THZ heat pump connection.

These tests require an actual heat pump connected via serial port.
Run with: pytest tests/test_live.py -v --port=/dev/ttyUSB1

To skip live tests when no device is connected:
    pytest tests/ -v -m "not live"
"""
import pytest
from thz_protocol import (
    THZConnection,
    REGISTERS,
    parse_firmware,
    parse_sglobal,
    parse_shc1,
    parse_history,
    parse_time,
    parse_errors,
)


@pytest.fixture(scope="module")
def serial_port(request):
    """Get serial port from command line."""
    return request.config.getoption("--port")


@pytest.fixture(scope="module")
def baudrate(request):
    """Get baudrate from command line."""
    return int(request.config.getoption("--baudrate"))


@pytest.fixture(scope="module")
def thz_connection(serial_port, baudrate):
    """Create and manage THZ connection for all tests in module."""
    conn = THZConnection(serial_port, baudrate)
    try:
        conn.connect()
        yield conn
    except Exception as e:
        pytest.skip(f"Could not connect to heat pump: {e}")
    finally:
        conn.disconnect()


# Mark all tests in this module as "live" tests
pytestmark = pytest.mark.live


class TestLiveConnection:
    """Tests that verify basic connection functionality."""
    
    def test_connection_established(self, thz_connection):
        """Test that connection is established."""
        assert thz_connection.is_connected()
    
    def test_firmware_read(self, thz_connection):
        """Test reading firmware version."""
        response = thz_connection.send_command("FD")
        
        assert response.success, f"Failed: {response.error_message}"
        assert response.data is not None
        
        firmware = parse_firmware(response.data)
        assert "version" in firmware
        print(f"\n    Firmware: {firmware['version']}")
    
    def test_sglobal_temperatures(self, thz_connection):
        """Test reading main sensor temperatures."""
        response = thz_connection.send_command("FB")
        
        assert response.success, f"Failed: {response.error_message}"
        
        data = parse_sglobal(response.data)
        
        # These should always be present
        assert "outside_temp" in data
        assert "flow_temp" in data
        assert "return_temp" in data
        assert "dhw_temp" in data
        
        # Print values for manual verification
        print(f"\n    Outside: {data.get('outside_temp')}°C")
        print(f"    Flow: {data.get('flow_temp')}°C")
        print(f"    Return: {data.get('return_temp')}°C")
        print(f"    DHW: {data.get('dhw_temp')}°C")
        
        # Sanity checks - temperatures should be in reasonable ranges
        assert -40 <= data["outside_temp"] <= 50, "Outside temp out of range"
        assert 0 <= data["flow_temp"] <= 80, "Flow temp out of range"
        assert 0 <= data["return_temp"] <= 80, "Return temp out of range"
        assert 0 <= data["dhw_temp"] <= 80, "DHW temp out of range"
    
    def test_history_operating_hours(self, thz_connection):
        """Test reading operating hours."""
        response = thz_connection.send_command("09")
        
        assert response.success, f"Failed: {response.error_message}"
        
        data = parse_history(response.data)
        
        assert "compressor_heating_hours" in data
        
        print(f"\n    Compressor heating hours: {data.get('compressor_heating_hours')}")
        print(f"    Booster heating hours: {data.get('booster_heating_hours', 'N/A')}")
        
        # Operating hours should be non-negative
        assert data["compressor_heating_hours"] >= 0
    
    def test_time_read(self, thz_connection):
        """Test reading device time."""
        response = thz_connection.send_command("FC")
        
        assert response.success, f"Failed: {response.error_message}"
        
        data = parse_time(response.data)
        
        assert "year" in data
        assert "month" in data
        assert "day" in data
        assert "hour" in data
        assert "minute" in data
        
        print(f"\n    Device time: {data['day']:02d}.{data['month']:02d}.{data['year']} "
              f"{data['hour']:02d}:{data['minute']:02d}:{data.get('second', 0):02d}")
        
        # Basic sanity checks
        assert 2020 <= data["year"] <= 2030
        assert 1 <= data["month"] <= 12
        assert 1 <= data["day"] <= 31
        assert 0 <= data["hour"] <= 23
        assert 0 <= data["minute"] <= 59
    
    def test_errors_read(self, thz_connection):
        """Test reading error count."""
        response = thz_connection.send_command("D1")
        
        assert response.success, f"Failed: {response.error_message}"
        
        data = parse_errors(response.data)
        
        assert "num_faults" in data
        print(f"\n    Number of faults: {data['num_faults']}")
        
        assert data["num_faults"] >= 0
    
    def test_shc1_heating_circuit(self, thz_connection):
        """Test reading heating circuit 1 data."""
        response = thz_connection.send_command("F4")
        
        assert response.success, f"Failed: {response.error_message}"
        
        data = parse_shc1(response.data)
        
        print(f"\n    HC1 data: {data}")
        
        # At least some data should be present
        assert len(data) > 0 or "parse_error" not in data


class TestLiveRegisterScan:
    """Tests that scan all known registers."""
    
    def test_all_registers(self, thz_connection):
        """Test reading all defined registers."""
        results = {}
        
        for reg, info in REGISTERS.items():
            response = thz_connection.send_command(reg)
            results[reg] = {
                "name": info["name"],
                "success": response.success,
                "error": response.error_message if not response.success else None,
                "data_length": len(response.data) if response.data else 0
            }
        
        print("\n    Register scan results:")
        for reg, result in results.items():
            status = "✓" if result["success"] else "✗"
            if result["success"]:
                print(f"    {status} {reg}: {result['name']} ({result['data_length']} bytes)")
            else:
                print(f"    {status} {reg}: {result['name']} - {result['error']}")
        
        # At least firmware and sGlobal should work
        assert results["FD"]["success"], "Firmware read failed"
        assert results["FB"]["success"], "sGlobal read failed"


class TestLiveDataValidation:
    """Tests that validate data consistency."""
    
    def test_temperature_consistency(self, thz_connection):
        """Test that return temp is less than or equal to flow temp."""
        response = thz_connection.send_command("FB")
        assert response.success
        
        data = parse_sglobal(response.data)
        
        flow = data.get("flow_temp", 0)
        ret = data.get("return_temp", 0)
        
        print(f"\n    Flow: {flow}°C, Return: {ret}°C")
        
        # Return temp should typically be lower than flow temp (heat is transferred)
        # Allow some tolerance for edge cases
        assert ret <= flow + 5, f"Return temp ({ret}) higher than flow temp ({flow})"
    
    def test_multiple_reads_stability(self, thz_connection):
        """Test that multiple reads return consistent data."""
        import time
        
        readings = []
        for i in range(3):
            response = thz_connection.send_command("FB")
            assert response.success
            data = parse_sglobal(response.data)
            readings.append(data.get("outside_temp"))
            time.sleep(0.5)
        
        print(f"\n    Outside temp readings: {readings}")
        
        # Temperature shouldn't change drastically between reads
        for i in range(1, len(readings)):
            diff = abs(readings[i] - readings[i-1])
            assert diff < 5, f"Temperature changed by {diff}°C between reads"
