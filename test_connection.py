#!/usr/bin/env python3
"""
Test script for THZ heat pump connection.
Run this directly on the machine connected to the heat pump.

Usage:
    python3 test_connection.py /dev/ttyUSB0
    python3 test_connection.py /dev/ttyUSB0 115200
"""
import sys
import time
import serial

# Register definitions for testing
REGISTERS = {
    "FD": {"name": "Firmware", "parse": "firmware"},
    "FB": {"name": "sGlobal (Temperaturen)", "parse": "sglobal"},
    "F3": {"name": "sDHW (Warmwasser)", "parse": "raw"},
    "F4": {"name": "sHC1 (Heizkreis 1)", "parse": "raw"},
    "FC": {"name": "sTime (Zeit)", "parse": "time"},
    "17": {"name": "p01-p12 (Sollwerte)", "parse": "p01"},
    "09": {"name": "sHistory (Betriebsstunden)", "parse": "history"},
    "D1": {"name": "sLast (Fehler)", "parse": "errors"},
}


def calculate_checksum(cmd: str) -> int:
    """Calculate checksum for a command (FHEM style)."""
    header = "0100"
    footer = "1003"
    template = header + "XX" + cmd + footer
    
    checksum = 0
    data_without_footer = template[:-4]
    
    for i in range(0, len(data_without_footer), 2):
        if i == 4:  # Skip XX placeholder
            continue
        byte_hex = data_without_footer[i:i+2]
        if byte_hex != "XX":
            checksum += int(byte_hex, 16)
    
    return checksum % 256


def escape_data(data: str) -> str:
    """Apply escape sequences to data."""
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


def build_command(register: str) -> str:
    """Build a complete command for a register."""
    checksum = calculate_checksum(register)
    data_to_escape = f"{checksum:02X}" + register
    escaped = escape_data(data_to_escape)
    return "0100" + escaped + "1003"


def send_command(ser, register: str) -> str | None:
    """Send a command and return the response data."""
    cmd = build_command(register)
    
    # Clear buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    # Step 0: Send STX
    ser.write(bytes.fromhex("02"))
    ser.flush()
    time.sleep(0.1)
    
    response = ser.read(ser.in_waiting) if ser.in_waiting else b''
    if response != b'\x10':
        print(f"    ✗ Step 0 failed: expected 10, got {response.hex() if response else 'NONE'}")
        return None
    
    # Step 1: Send command
    ser.write(bytes.fromhex(cmd))
    ser.flush()
    time.sleep(0.2)
    
    response = ser.read(ser.in_waiting) if ser.in_waiting else b''
    if response not in [b'\x10\x02', b'\x02', b'\x10']:
        print(f"    ✗ Step 1 failed: expected 1002/02, got {response.hex() if response else 'NONE'}")
        return None
    
    if response == b'\x10':
        time.sleep(0.05)
        ser.read(1)  # Read the 02
    
    # Step 2: Send DLE
    ser.write(bytes.fromhex("10"))
    ser.flush()
    
    # Read response
    time.sleep(0.3)
    data = bytearray()
    start = time.time()
    while time.time() - start < 2.0:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            data.extend(chunk)
            data_hex = data.hex().upper()
            if data_hex.startswith("01") and data_hex.endswith("1003"):
                break
        time.sleep(0.01)
    
    # Send final DLE
    ser.write(bytes.fromhex("10"))
    ser.flush()
    
    if not data:
        print("    ✗ No response data")
        return None
    
    data_hex = data.hex().upper()
    
    # Unescape
    data_hex = data_hex.replace("1010", "10").replace("2B18", "2B")
    
    # Check header
    header = data_hex[:4]
    if header == "0100":
        # Extract data: 0100 + checksum(2) + data + 1003
        return data_hex[6:-4]  # Remove header+checksum and footer
    elif header == "0102":
        print(f"    ✗ CRC Error")
        return None
    elif header == "0103":
        print(f"    ✗ Unknown command")
        return None
    elif header == "0104":
        print(f"    ✗ Unknown register")
        return None
    else:
        print(f"    ✗ Unknown header: {header}")
        return None


def parse_sglobal(data_hex: str) -> dict:
    """Parse sGlobal (FB) register - main sensor data."""
    result = {}
    try:
        # Skip command echo (first 2 chars)
        d = data_hex[2:]
        
        if len(d) >= 8:
            result["outside_temp"] = int(d[4:8], 16) / 10
            if result["outside_temp"] > 3000:
                result["outside_temp"] = (int(d[4:8], 16) - 65536) / 10
        
        if len(d) >= 12:
            result["flow_temp"] = int(d[8:12], 16) / 10
        
        if len(d) >= 16:
            result["return_temp"] = int(d[12:16], 16) / 10
        
        if len(d) >= 24:
            result["dhw_temp"] = int(d[20:24], 16) / 10
        
        if len(d) >= 32:
            result["inside_temp"] = int(d[28:32], 16) / 10
            if result["inside_temp"] > 3000:
                result["inside_temp"] = (int(d[28:32], 16) - 65536) / 10
                
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_p01(data_hex: str) -> dict:
    """Parse p01-p12 register (17) - setpoints."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 8:
            result["p01_room_temp_day"] = int(d[0:4], 16) / 10
        if len(d) >= 12:
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


def parse_history(data_hex: str) -> dict:
    """Parse sHistory (09) register - operating hours."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 8:
            result["compressor_heating_hours"] = int(d[0:4], 16)
        if len(d) >= 12:
            result["compressor_cooling_hours"] = int(d[4:8], 16)
        if len(d) >= 16:
            result["compressor_dhw_hours"] = int(d[8:12], 16)
        if len(d) >= 20:
            result["booster_dhw_hours"] = int(d[12:16], 16)
        if len(d) >= 24:
            result["booster_heating_hours"] = int(d[16:20], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def parse_time(data_hex: str) -> dict:
    """Parse sTime (FC) register."""
    result = {}
    try:
        d = data_hex[2:]  # Skip command echo
        
        if len(d) >= 4:
            result["weekday"] = int(d[0:2], 16)
        if len(d) >= 6:
            result["hour"] = int(d[2:4], 16)
        if len(d) >= 8:
            result["minute"] = int(d[4:6], 16)
        if len(d) >= 10:
            result["second"] = int(d[6:8], 16)
        if len(d) >= 14:
            year = int(d[8:12], 16)
            result["year"] = year
        if len(d) >= 16:
            result["month"] = int(d[12:14], 16)
        if len(d) >= 18:
            result["day"] = int(d[14:16], 16)
            
    except (ValueError, IndexError) as e:
        result["parse_error"] = str(e)
    
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_connection.py <port> [baudrate]")
        print("Example: python3 test_connection.py /dev/ttyUSB0 115200")
        sys.exit(1)
    
    port = sys.argv[1]
    baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
    
    print(f"=" * 60)
    print(f"THZ Heat Pump Connection Test")
    print(f"=" * 60)
    print(f"Port: {port}")
    print(f"Baudrate: {baudrate}")
    print(f"=" * 60)
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=3.0,
            write_timeout=2.0,
        )
        print(f"✓ Serial port opened successfully\n")
        
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Test all registers
        for reg, info in REGISTERS.items():
            print(f"\n--- Testing Register {reg}: {info['name']} ---")
            
            data = send_command(ser, reg)
            
            if data:
                print(f"    Raw data: {data}")
                
                if info['parse'] == 'firmware':
                    if len(data) >= 6:
                        version_hex = data[2:6]
                        version_raw = int(version_hex, 16)
                        major = version_raw // 100
                        minor = version_raw % 100
                        print(f"    ✓ Firmware: {major}.{minor:02d}")
                
                elif info['parse'] == 'sglobal':
                    parsed = parse_sglobal(data)
                    for key, value in parsed.items():
                        print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'p01':
                    parsed = parse_p01(data)
                    for key, value in parsed.items():
                        print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'history':
                    parsed = parse_history(data)
                    for key, value in parsed.items():
                        print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'time':
                    parsed = parse_time(data)
                    if 'day' in parsed and 'month' in parsed and 'year' in parsed:
                        print(f"    ✓ Date: {parsed.get('day', '?')}.{parsed.get('month', '?')}.{parsed.get('year', '?')}")
                    if 'hour' in parsed and 'minute' in parsed:
                        print(f"    ✓ Time: {parsed.get('hour', '?'):02d}:{parsed.get('minute', '?'):02d}:{parsed.get('second', 0):02d}")
                
                elif info['parse'] == 'errors':
                    # Just show raw for now
                    if len(data) >= 4:
                        num_faults = int(data[2:4], 16)
                        print(f"    ✓ Number of faults: {num_faults}")
                
                elif info['parse'] == 'raw':
                    print(f"    ✓ Data length: {len(data)} hex chars ({len(data)//2} bytes)")
            
            time.sleep(0.3)  # Pause between registers
        
        ser.close()
        print(f"\n{'=' * 60}")
        print("✓ All tests complete!")
        print(f"{'=' * 60}")
        
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
