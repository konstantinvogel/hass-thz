#!/usr/bin/env python3
"""
Dump all THZ heat pump registers to a JSON file.

This script reads all available registers from the heat pump and saves
them as a JSON file for testing and development purposes.

Usage:
    python scripts/dump_registers.py [--port /dev/ttyUSB1] [--output registers.json]

The output file can be used in unit tests to verify parser implementations
with real device data.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "hass_thz"))

from thz_protocol import THZConnection, REGISTERS, PARSERS, parse_firmware


def dump_registers(port: str, baudrate: int = 115200) -> dict:
    """
    Read all registers from the heat pump.
    
    Returns a dict with:
    - metadata: timestamp, firmware, port
    - raw: raw hex data for each register
    - parsed: parsed data for each register
    """
    result = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "port": port,
            "baudrate": baudrate,
        },
        "raw": {},
        "parsed": {},
    }
    
    conn = THZConnection(port, baudrate)
    
    try:
        print(f"Connecting to {port} at {baudrate} baud...")
        conn.connect()
        print("Connected!\n")
        
        # Read firmware first - use send_command for raw data
        print("Reading firmware (FD)...")
        response = conn.send_command("FD")
        if response.success and response.data:
            result["raw"]["FD"] = response.data
            fw_data = parse_firmware(response.data)
            result["parsed"]["FD"] = fw_data
            result["metadata"]["firmware"] = fw_data.get("version", "unknown")
            print(f"  Firmware: {fw_data.get('version', 'unknown')}")
        else:
            print(f"  Failed: {response.error_message}")
        
        # Read all other registers
        for reg_id, reg_info in REGISTERS.items():
            if reg_id == "FD":
                continue  # Already read
                
            reg_name = reg_info.get("name", reg_id)
            print(f"Reading {reg_name} ({reg_id})...")
            
            # Use send_command to get raw THZResponse
            response = conn.send_command(reg_id)
            
            if response.success and response.data:
                result["raw"][reg_id] = response.data
                
                # Parse if parser available
                parser_name = reg_info.get("parse")
                if parser_name and parser_name in PARSERS:
                    try:
                        parsed = PARSERS[parser_name](response.data)
                        result["parsed"][reg_id] = parsed
                        print(f"  OK - {len(response.data)} hex chars, {len(parsed)} values")
                    except Exception as e:
                        print(f"  OK (raw) - parse error: {e}")
                        result["parsed"][reg_id] = {"error": str(e)}
                else:
                    print(f"  OK - {len(response.data)} hex chars (no parser)")
            else:
                print(f"  Failed: {response.error_message}")
                result["raw"][reg_id] = None
                result["parsed"][reg_id] = {"error": response.error_message}
        
        print("\nDone!")
        
    finally:
        conn.disconnect()
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Dump THZ heat pump registers to JSON file"
    )
    parser.add_argument(
        "--port", "-p",
        default="/dev/ttyUSB1",
        help="Serial port (default: /dev/ttyUSB1)"
    )
    parser.add_argument(
        "--baudrate", "-b",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file (default: tests/fixtures/registers_<timestamp>.json)"
    )
    
    args = parser.parse_args()
    
    # Generate output filename if not specified
    if args.output is None:
        fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = fixtures_dir / f"registers_{timestamp}.json"
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Dump registers
    try:
        data = dump_registers(args.port, args.baudrate)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    
    # Save to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to: {output_path}")
    print(f"Registers read: {len([r for r in data['raw'].values() if r])}")
    print(f"Registers failed: {len([r for r in data['raw'].values() if r is None])}")


if __name__ == "__main__":
    main()
