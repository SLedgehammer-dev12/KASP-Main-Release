"""Shared contracts for KASP integration modules.

Each module exposes a small, stable adapter instead of importing a foreign UI.
Adapters receive SI-unit payloads (bar, °C, kg/s) and return JSON-serializable
dicts with a `schema_version`, `warnings`, and `provenance` block.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


SCHEMA_VERSION = "1.0"


def to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy scalars, dataclasses and other objects to JSON-safe values."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(dataclasses.asdict(obj))
    # numpy scalar / array
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return to_jsonable(item())
        except Exception:
            pass
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return to_jsonable(to_dict())
        except Exception:
            pass
    return str(obj)


@dataclass(frozen=True)
class ModuleManifest:
    id: str
    name: str
    version: str
    description: str
    standards: List[str] = field(default_factory=list)
    source: str = ""
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "standards": list(self.standards),
            "source": self.source,
            "capabilities": list(self.capabilities),
        }


class IntegrationAdapter(Protocol):
    manifest: ModuleManifest

    def input_schema(self) -> Dict[str, Any]:
        ...

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...


def module_response(
    adapter: IntegrationAdapter,
    result: Dict[str, Any],
    warnings: List[str] | None = None,
    provenance: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": adapter.manifest.id,
        "module_version": adapter.manifest.version,
        "success": True,
        "warnings": to_jsonable(list(warnings or [])),
        "provenance": to_jsonable(provenance or {}),
        "results": to_jsonable(result),
    }
