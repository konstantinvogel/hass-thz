"""
Pytest configuration for THZ tests.
"""
import pytest


def pytest_addoption(parser):
    """Add command line options for live tests."""
    parser.addoption(
        "--port",
        action="store",
        default="/dev/ttyUSB1",
        help="Serial port for THZ heat pump (default: /dev/ttyUSB1)"
    )
    parser.addoption(
        "--baudrate",
        action="store",
        default="115200",
        help="Baudrate for serial connection (default: 115200)"
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "live: marks tests as requiring live hardware connection"
    )


def pytest_collection_modifyitems(config, items):
    """Skip live tests if --port is not explicitly provided or device not found."""
    # Check if we're running live tests
    run_live = False
    for item in items:
        if "live" in [marker.name for marker in item.iter_markers()]:
            run_live = True
            break
    
    if not run_live:
        return
    
    # Try to check if device exists (Unix-style check)
    port = config.getoption("--port")
    import os
    if not os.path.exists(port) and not port.startswith("COM"):
        skip_live = pytest.mark.skip(reason=f"Serial port {port} not found")
        for item in items:
            if "live" in [marker.name for marker in item.iter_markers()]:
                item.add_marker(skip_live)
