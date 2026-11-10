"""Module registry for KASP integrations.

The registry keeps imports lazy so a missing optional dependency (for example
`pyaga8` or a vendored engine) does not prevent KASP from starting.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, List, Optional

from kasp.integrations.base import IntegrationAdapter

logger = logging.getLogger(__name__)

# module_id -> (module path, adapter class name)
_MODULE_PATHS = {
    "psv": ("kasp.integrations.psv.adapter", "PSVAdapter"),
    "api5l": ("kasp.integrations.api5l.adapter", "API5LAdapter"),
    "pipe_hydraulics": ("kasp.integrations.pipe_hydraulics.adapter", "PipeHydraulicsAdapter"),
    "air_cooler": ("kasp.integrations.air_cooler.adapter", "AirCoolerAdapter"),
    "control_valve": ("kasp.integrations.control_valve.adapter", "ControlValveAdapter"),
}

_CACHE: Dict[str, IntegrationAdapter] = {}


def get_adapter(module_id: str) -> Optional[IntegrationAdapter]:
    key = str(module_id or "").strip().lower()
    if key in _CACHE:
        return _CACHE[key]
    spec = _MODULE_PATHS.get(key)
    if not spec:
        return None
    module_path, class_name = spec
    try:
        module = importlib.import_module(module_path)
        adapter_cls = getattr(module, class_name)
        adapter = adapter_cls()
    except Exception as exc:  # pragma: no cover - surfaced via API error
        logger.warning("Integration module '%s' could not be loaded: %s", key, exc)
        return None
    _CACHE[key] = adapter
    return adapter


def list_modules() -> List[Dict[str, Any]]:
    modules = []
    for module_id in _MODULE_PATHS:
        adapter = get_adapter(module_id)
        if adapter is not None:
            modules.append(adapter.manifest.to_dict())
    return modules


def calculate_module(module_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    adapter = get_adapter(module_id)
    if adapter is None:
        raise KeyError(f"Bilinmeyen veya yüklenemeyen modül: {module_id}")
    return adapter.calculate(payload or {})
