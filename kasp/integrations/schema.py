"""Schema versioning and migration for KASP integration module payloads.

Module responses from `kasp.integrations.base.module_response()` carry
`schema_version`. Project files created by older KASP builds may contain raw
module results without that envelope. This module upgrades both shapes to the
current version and preserves forward-compatible unknown fields.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

MODULE_SCHEMA_VERSION = "1.0"
_MODULE_SCHEMA_NUMBER = 1


def _version_tuple(value: Any) -> Tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return (0,)


def _is_newer(version: str) -> bool:
    current = _version_tuple(MODULE_SCHEMA_VERSION)
    incoming = _version_tuple(version)
    length = max(len(current), len(incoming))
    current += (0,) * (length - len(current))
    incoming += (0,) * (length - len(incoming))
    return incoming > current


def migrate_module_payload(module_id: str, payload: Any) -> Dict[str, Any]:
    """Upgrade a single module payload to MODULE_SCHEMA_VERSION."""
    if not isinstance(payload, dict):
        return {
            "schema_version": MODULE_SCHEMA_VERSION,
            "module_id": module_id,
            "module_version": "unknown",
            "success": True,
            "warnings": [f"Eski modül yükü ({module_id}) ham sonuç olarak sarıldı."],
            "provenance": {},
            "results": payload,
        }

    upgraded = dict(payload)
    upgraded.setdefault("module_id", module_id)
    version = str(upgraded.get("schema_version", "") or "").strip()

    if not version:
        # Legacy shape: either a raw result dict or a response without version.
        if "results" not in upgraded:
            upgraded["results"] = {
                key: value
                for key, value in payload.items()
                if key not in {"module_id", "module_version", "success", "warnings", "provenance"}
            }
        upgraded["schema_version"] = MODULE_SCHEMA_VERSION
        upgraded.setdefault("module_version", "unknown")
        upgraded.setdefault("success", True)
        upgraded.setdefault("warnings", [])
        upgraded.setdefault("provenance", {})
        warnings = upgraded["warnings"]
        if isinstance(warnings, list):
            warnings.append(f"Modül şeması {MODULE_SCHEMA_VERSION} sürümüne yükseltildi ({module_id}).")
        return upgraded

    if version == MODULE_SCHEMA_VERSION:
        return upgraded

    if _is_newer(version):
        warnings = upgraded.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(
                f"Modül şeması ({version}) KASP'ın desteklediğinden yeni; alanlar korunarak okundu."
            )
        return upgraded

    # Known older versions: 0.x -> 1.0 is a structural no-op; just bump.
    upgraded["schema_version"] = MODULE_SCHEMA_VERSION
    warnings = upgraded.setdefault("warnings", [])
    if isinstance(warnings, list):
        warnings.append(
            f"Modül şeması {version} -> {MODULE_SCHEMA_VERSION} yükseltildi ({module_id})."
        )
    return upgraded


def migrate_modules_payload(modules: Any) -> Dict[str, Any]:
    """Upgrade a dict of module_id -> module response."""
    if not isinstance(modules, dict):
        return {}
    migrated: Dict[str, Any] = {}
    for module_id, payload in modules.items():
        try:
            migrated[str(module_id)] = migrate_module_payload(str(module_id), payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Modül şeması yükseltilemedi (%s): %s", module_id, exc)
            migrated[str(module_id)] = payload
    return migrated


def migrate_results_payload(results: Any) -> Any:
    """Upgrade `results.module_results` inside a persisted result payload."""
    if not isinstance(results, dict):
        return results
    if "module_results" in results:
        results = dict(results)
        results["module_results"] = migrate_modules_payload(results.get("module_results"))
    return results
