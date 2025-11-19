import pytest
from custom_components.thz.thz_device import THZDevice
from tests.conftest import FakeSerial
import sys

from pathlib import Path

import types

# locate repo root (folder that contains "custom_components") and add to sys.path
p = Path(__file__).resolve()
root = p
while root != root.parent and not (root / "custom_components").exists():
    root = root.parent
sys.path.insert(0, str(root))

# create minimal homeassistant stubs so importing the integration at module import time works
def _make_module(name, attrs=None):
    m = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(m, k, v)
    sys.modules[name] = m
    return m

_make_module("homeassistant")
_make_module("homeassistant.core", {"HomeAssistant": type("HomeAssistant", (), {})})
_make_module("homeassistant.config_entries", {"ConfigEntry": type("ConfigEntry", (), {})})
_make_module("homeassistant.helpers")
_make_module("homeassistant.helpers.entity", {"Entity": object})
_make_module("homeassistant.helpers.discovery", {"load_platform": lambda *a, **k: None})
_make_module("homeassistant.components.time", {"TimeEntity": object})
_make_module("homeassistant.components.number", {"NumberEntity": object})
_make_module("homeassistant.components.select", {"SelectEntity": object})
_make_module("homeassistant.components.sensor", {"SensorEntity": object})
_make_module("homeassistant.components.switch", {"SwitchEntity": object})

@pytest.fixture
def fake_device():
    """
    Create a THZDevice that uses a FakeSerial instance.
    FakeSerial should expose a mapping of block_name -> bytes and
    a read_count dict to assert how often a block was read.
    """
    responses = {
        "block1": b'\x02\x03\x02\x1A\x0B\x12\x34',
        "block2": b'\x02\x03\x02\x1C\x0C\x11\x22',
    }
    serial = FakeSerial(responses)
    device = THZDevice(serial_port=None)  # prevent real serial open
    device._serial = serial  # inject fake serial
    # ensure any internal caches are empty for deterministic tests
    if hasattr(device, "_cache"):
        device._cache.clear()
    return device


def test_read_block_cached_reads_once_per_block(fake_device):
    # First read should come from FakeSerial
    data1 = fake_device.read_block_cached(10, "block1")
    assert data1 == b'\x02\x03\x02\x1A\x0B\x12\x34'

    # Second read within cache period should return same data and not increment serial reads
    data2 = fake_device.read_block_cached(10, "block1")
    assert data2 == data1
    assert fake_device._serial.read_count["block1"] == 1


def test_reads_different_blocks_independently(fake_device):
    data1 = fake_device.read_block_cached(10, "block1")
    data2 = fake_device.read_block_cached(10, "block2")
    assert data1 != data2
    assert fake_device._serial.read_count["block1"] == 1
    assert fake_device._serial.read_count["block2"] == 1


def test_parse_block_returns_dict_and_numeric_values(fake_device):
    raw = fake_device.read_block_cached(10, "block1")
    parsed = fake_device.parse_block(raw, "block1")
    assert isinstance(parsed, dict)
    # at least one parsed value should be numeric (int/float)
    assert any(isinstance(v, (int, float)) for v in parsed.values()), "parsed values should include numeric entries"


def test_missing_block_raises_keyerror(fake_device):
    with pytest.raises(KeyError):
        fake_device.read_block_cached(10, "nonexistent_block")