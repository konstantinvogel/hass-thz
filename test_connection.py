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

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_connection.py <port> [baudrate]")
        print("Example: python3 test_connection.py /dev/ttyUSB0 115200")
        sys.exit(1)
    
    port = sys.argv[1]
    baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
    
    print(f"Testing connection to {port} at {baudrate} baud...")
    
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
        print(f"✓ Serial port opened successfully")
        
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Step 0: Send STX (0x02)
        print("\n--- Step 0: Sending STX (0x02) ---")
        ser.write(bytes.fromhex("02"))
        ser.flush()
        
        time.sleep(0.1)
        response = ser.read(ser.in_waiting) if ser.in_waiting else b''
        print(f"Response: {response.hex() if response else 'NONE'}")
        
        if response == b'\x10':
            print("✓ Received DLE (0x10) - handshake OK!")
        elif response == b'\x15':
            print("✗ Received NAK (0x15) - device busy?")
            return
        else:
            print(f"✗ Unexpected response: {response.hex() if response else 'NONE'}")
            print("  Expected: 10 (DLE)")
            return
        
        # Step 1: Send command to read firmware (FD)
        # Format: 0100 + checksum + FD + 1003
        # 
        # FHEM THZ_checksum calculates over: header + XX + cmd + footer
        # But EXCLUDES: position 4-5 (XX placeholder) AND last 4 chars (footer)
        # 
        # String: 0100XXFD1003
        # Positions: 01(0-1) 00(2-3) XX(4-5) FD(6-7) 10(8-9) 03(10-11)
        # Calculate: 01 + 00 + FD = 0x01 + 0x00 + 0xFD = 254 = 0xFE
        
        checksum = (0x01 + 0x00 + 0xFD) % 256  # = 0xFE
        cmd = f"0100{checksum:02X}FD1003"
        print(f"\n--- Step 1: Sending command: {cmd} ---")
        print(f"  (Checksum calculated: 0x{checksum:02X})")
        ser.write(bytes.fromhex(cmd))
        ser.flush()
        
        time.sleep(0.2)
        response = ser.read(ser.in_waiting) if ser.in_waiting else b''
        print(f"Response: {response.hex().upper() if response else 'NONE'}")
        
        # Expected: 10 02 (DLE STX) or just 02 (STX)
        if response in [b'\x10\x02', b'\x02', b'\x10']:
            if response == b'\x10':
                # Read the STX
                time.sleep(0.05)
                response2 = ser.read(1)
                print(f"  Additional byte: {response2.hex() if response2 else 'NONE'}")
            print("✓ Received DLE STX - command accepted!")
        elif response == b'\x15':
            print("✗ Received NAK - command rejected")
            return
        else:
            print(f"? Unexpected response, trying to continue...")
        
        # Step 2: Send DLE (0x10) to request data
        print(f"\n--- Step 2: Sending DLE (0x10) ---")
        ser.write(bytes.fromhex("10"))
        ser.flush()
        
        # Read response data
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
        
        print(f"Response data: {data.hex().upper() if data else 'NONE'}")
        
        if data:
            data_hex = data.hex().upper()
            
            # Send final DLE
            ser.write(bytes.fromhex("10"))
            ser.flush()
            
            if data_hex.startswith("0100"):
                print("✓ Valid response header!")
                
                # Unescape
                data_hex = data_hex.replace("1010", "10").replace("2B18", "2B")
                
                # Extract firmware (position 6-10, after header+checksum)
                if len(data_hex) >= 14:
                    fw_hex = data_hex[6:10]
                    fw_int = int(fw_hex, 16)
                    major = fw_int // 100
                    minor = fw_int % 100
                    print(f"✓ Firmware detected: {major}.{minor:02d}")
                else:
                    print(f"  Data too short to extract firmware: {data_hex}")
            else:
                print(f"✗ Invalid header: {data_hex[:4]}")
        else:
            print("✗ No data received")
        
        ser.close()
        print("\n✓ Test complete!")
        
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
