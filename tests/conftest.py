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


class FakeSerial:
    """Simulierte Serial-Schnittstelle für Tests."""

    def __init__(self, responses: dict):
        """
        responses: dict mapping block_name -> bytes
        """
        self._responses = responses
        self.read_count = {key: 0 for key in responses}

    def write(self, data: bytes):
        """Schreibt Daten. Wird nur gezählt, kein Effekt."""
        pass

    def read(self, n: int) -> bytes:
        """
        Simuliert ein Lesevorgang. Gibt die nächsten n Bytes zurück.
        Hier werden einfach die kompletten Bytes des Blocks zurückgegeben.
        """
        # Optional: Erweiterung um Sequenznummern oder Lese-Counter
        # Für Tests reicht einfaches Zurückgeben
        raise NotImplementedError("Direktes Lesen über FakeSerial nicht unterstützt. Verwende read_block_by_name.")

    def read_block_by_name(self, block_name: str) -> bytes:
        """Gibt die vordefinierten Bytes für den Block zurück und zählt den Zugriff."""
        if block_name not in self._responses:
            raise KeyError(f"Block {block_name} nicht definiert in FakeSerial")
        self.read_count[block_name] += 1
        return self._responses[block_name]
    
