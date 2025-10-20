import sys
import logging
from copy import deepcopy
from typing import Dict, List, Tuple
from . import register_map_all, write_map_all
from . import register_map_206
from . import register_map_214

supported_firmwares = ["206, 214"]  # Add other supported firmware versions here
_LOGGER = logging.getLogger(__name__)

RegisterEntry = Tuple[str, int, int, str, int]  # (name, offset, length, type, factor, refresh dict)
RegisterEntry_Write = Tuple[str, bytes, int, int, str, int, str, str, str, str, str]  # (name, command, min, max, unit, step, type, device_class, icon, decode type)

class BaseRegisterMapManager:
    def __init__(
        self,
        firmware_version: str,
        base_map_name: str,
        command_map_name: str,
        map_attr: str,
        entry_type: type,
    ):
        self.firmware_version = firmware_version
        self._base_map = self._load_register_map(base_map_name, map_attr, entry_type)
        self._command_map = self._load_register_map(f"{command_map_name}_{firmware_version}", map_attr, entry_type)
        self._merged_map = self._merge_maps(self._base_map, self._command_map)

    def _load_register_map(self, module_name: str, map_attr: str, entry_type: type) -> Dict[str, any]:
        package_prefix = __package__
        full_module_name = f"{package_prefix}.{module_name}"
        mod = sys.modules.get(full_module_name)
        _LOGGER.debug(f"Loading register map from module: {module_name}, found: {mod is not None}")
        if mod is not None:
            full_map = deepcopy(getattr(mod, map_attr))
            # Filter: only keep items of the correct type (list or dict)
            return {k: v for k, v in full_map.items() if isinstance(v, entry_type)}
        else:
            return {}

    def _merge_maps(self, base: Dict, override: Dict) -> Dict:
        merged = deepcopy(base)
        for block, entries in override.items():
            if block in merged:
                override_names = {e[0] for e in entries}
                merged[block] = [e for e in merged[block] if e[0] not in override_names] + entries
            else:
                merged[block] = entries
        return merged

    def get_all_registers(self) -> Dict:
        return self._merged_map

    def get_registers_for_block(self, block: str) -> any:
        return self._merged_map.get(block, [])

    def get_firmware_version(self) -> str:
        return self.firmware_version

class RegisterMapManager(BaseRegisterMapManager):
    def __init__(self, firmware_version: str):
        super().__init__(
            firmware_version,
            base_map_name="register_map_all",
            command_map_name="register_map",
            map_attr="REGISTER_MAP",
            entry_type=list,
        )

class RegisterMapManager_Write(BaseRegisterMapManager):
    def __init__(self, firmware_version: str):
        super().__init__(
            firmware_version,
            base_map_name="write_map_all",
            command_map_name="write_map",
            map_attr="WRITE_MAP",
            entry_type=dict,
            )
    
    def _merge_maps(self, base: Dict, override: Dict) -> Dict:
        merged = deepcopy(base)
        merged.update(override)
        return merged
    
    #     $attrVal = "4.39" if (($cmd eq "del") and ($attrName eq "firmware"));
    # if ( $attrName eq "firmware" )  {  
    #     if ($attrVal eq "2.06") {
    #         %sets = %sets206;
    #         %gets = (%getsonly2xx, %getsonly206, %sets);
    #     }
    #     elsif ($attrVal eq "2.14") {
    #         %sets = (%sets206, %setsonly214);
    #         %gets = (%getsonly2xx, %getsonly214, %sets206);
    #     }
    #     elsif ($attrVal eq "2.14j") {
    #         %sets = (%sets206, %setsonly214);
    #         %gets = (%getsonly2xx, %getsonly214j, %sets206);
    #     }
    #     elsif ($attrVal eq "5.39") {
    #         %sets=(%sets439539common, %sets539only);
    #         %gets=(%getsonly539, %sets);
    #     }
    #     elsif ($attrVal eq "5.39technician") {
    #         %sets=(%sets439539common, %sets539only, %setsX39technician);
    #         %gets=(%getsonly539, %sets);
    #     }
    #     elsif ($attrVal eq "4.39technician") {
    #         %sets=(%sets439539common, %sets439only, %setsX39technician);
    #         %gets=(%getsonly439, %sets);
    #     }
    #     else { #in all other cases I assume $attrVal eq "4.39" cambiato nella v0140
    #         %sets=(%sets439539common, %sets439only);
    #         %gets=(%getsonly439, %sets);
    #     }