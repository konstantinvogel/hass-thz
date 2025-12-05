# Test Fixtures

This directory contains real device data dumps for unit testing.

## Files

- `registers_YYYYMMDD_HHMMSS.json` - Register dumps from the heat pump

## Creating a new dump

Run the dump script on a machine connected to the heat pump:

```bash
python scripts/dump_registers.py --port /dev/ttyUSB1
```

The file will be saved to `tests/fixtures/registers_<timestamp>.json`.

## JSON Structure

```json
{
  "metadata": {
    "timestamp": "2025-12-05T21:30:00",
    "port": "/dev/ttyUSB1",
    "baudrate": 115200,
    "firmware": "7.02"
  },
  "raw": {
    "FD": "FD02BE",
    "FB": "FB...",
    ...
  },
  "parsed": {
    "FD": {"version": "7.02", "versionNum": 702},
    "FB": {"outsideTemp": 4.5, "flowTemp": 29.9, ...},
    ...
  }
}
```

## Using in tests

```python
import json
from pathlib import Path

@pytest.fixture
def real_register_data():
    fixture_path = Path(__file__).parent / "fixtures" / "registers_20251205_213000.json"
    with open(fixture_path) as f:
        return json.load(f)

def test_with_real_data(real_register_data):
    raw_fb = real_register_data["raw"]["FB"]
    result = parse_sglobal(raw_fb)
    assert "outsideTemp" in result
```
