#!/usr/bin/env python3
"""
Interactive test script for THZ heat pump connection.
Run this directly on the machine connected to the heat pump.

Usage:
    python3 test_connection.py /dev/ttyUSB0
    python3 test_connection.py /dev/ttyUSB0 115200
"""
import sys

from thz_protocol import (
    THZConnection,
    REGISTERS,
    parse_firmware,
    parse_sglobal,
    parse_shc1,
    parse_p01,
    parse_history,
    parse_time,
    parse_errors,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_connection.py <port> [baudrate]")
        print("Example: python3 test_connection.py /dev/ttyUSB0 115200")
        sys.exit(1)
    
    port = sys.argv[1]
    baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
    
    print("=" * 60)
    print("THZ Heat Pump Connection Test")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Baudrate: {baudrate}")
    print("=" * 60)
    
    try:
        with THZConnection(port, baudrate) as conn:
            print("✓ Serial port opened successfully\n")
            
            # Test all registers
            for reg, info in REGISTERS.items():
                print(f"\n--- Testing Register {reg}: {info['name']} ---")
                
                response = conn.send_command(reg)
                
                if not response.success:
                    print(f"    ✗ {response.error_message}")
                    continue
                
                print(f"    Raw data: {response.data}")
                
                if info['parse'] == 'firmware':
                    parsed = parse_firmware(response.data)
                    if 'version' in parsed:
                        print(f"    ✓ Firmware: {parsed['version']}")
                
                elif info['parse'] == 'sglobal':
                    parsed = parse_sglobal(response.data)
                    for key, value in parsed.items():
                        if key == "inside_temp_valid":
                            continue  # Skip the boolean flag
                        if key == "inside_temp" and not parsed.get("inside_temp_valid", True):
                            print(f"    ✓ {key}: {value} (no sensor?)")
                        else:
                            print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'shc1':
                    parsed = parse_shc1(response.data)
                    for key, value in parsed.items():
                        print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'p01':
                    parsed = parse_p01(response.data)
                    for key, value in parsed.items():
                        print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'history':
                    parsed = parse_history(response.data)
                    for key, value in parsed.items():
                        print(f"    ✓ {key}: {value}")
                
                elif info['parse'] == 'time':
                    parsed = parse_time(response.data)
                    if 'day' in parsed and 'month' in parsed and 'year' in parsed:
                        print(f"    ✓ Date: {parsed.get('day', '?')}.{parsed.get('month', '?')}.{parsed.get('year', '?')}")
                    if 'hour' in parsed and 'minute' in parsed:
                        print(f"    ✓ Time: {parsed.get('hour', '?'):02d}:{parsed.get('minute', '?'):02d}:{parsed.get('second', 0):02d}")
                
                elif info['parse'] == 'errors':
                    parsed = parse_errors(response.data)
                    if 'num_faults' in parsed:
                        print(f"    ✓ Number of faults: {parsed['num_faults']}")
                
                elif info['parse'] == 'raw':
                    print(f"    ✓ Data length: {len(response.data)} hex chars ({len(response.data)//2} bytes)")
        
        print(f"\n{'=' * 60}")
        print("✓ All tests complete!")
        print(f"{'=' * 60}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
