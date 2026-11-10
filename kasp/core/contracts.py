"""
Shared input contracts and normalization helpers for KASP.

This module keeps design-input defaults, legacy alias handling, and
project-file serialization in one place so UI, API, and persistence
layers do not drift independently.
"""

from __future__ import annotations

import copy
import datetime
from typing import Any, Mapping


DESIGN_INPUT_DEFAULTS = {
    "project_name": "Yeni Kompresör Projesi",
    "notes": "",
    "p_in": "49.65",
    "p_in_unit": "bar(g)",
    "t_in": "19",
    "t_in_unit": "°C",
    "p_out": "75",
    "p_out_unit": "bar(a)",
    "flow": "1985000",
    "flow_unit": "Sm³/h",
    "num_units": 1,
    "num_stages": 1,
    "intercooler_dp_pct": 2.0,
    "intercooler_t": 40.0,
    "gas_comp": {},
    "eos_method": "pr",
    "method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    "poly_eff": 90.0,
    "therm_eff": 35.0,
    "mech_eff": 98.0,
    "lhv_source": "kasp",
    "use_consistency_iteration": False,
    "max_consistency_iter": 20,
    "consistency_tolerance": 0.1,
    "ambient_temp": 19.0,
    "ambient_pressure": 101.325,
    "altitude": 0,
    "humidity": 60,
    "enable_uncertainty": False,
}

LEGACY_INPUT_ALIASES = {
    "ambient_press": "ambient_pressure",
    "consistency_check": "use_consistency_iteration",
    "calc_method": "method",
    "eos_model": "eos_method",
}


def get_design_input_defaults() -> dict[str, Any]:
    """Return a deep-copied default design-input payload."""
    return copy.deepcopy(DESIGN_INPUT_DEFAULTS)


def normalize_design_inputs(inputs: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Merge incoming design inputs with shared defaults and legacy aliases.

    Unknown keys are preserved to avoid dropping incremental features such as
    uncertainty flags or newer experimental settings.
    """
    normalized = get_design_input_defaults()
    if not inputs:
        return normalized

    source = dict(inputs)

    # Ambient pressure: if entered as mbar/hPa (> 200), convert to kPa
    if "ambient_pressure" in source and source["ambient_pressure"] is not None:
        try:
            p_val = float(source["ambient_pressure"])
            source["ambient_pressure"] = p_val / 10.0 if p_val > 200 else p_val
        except (TypeError, ValueError):
            pass
    elif "ambient_press" in source:
        legacy_pressure = source.get("ambient_press", 1013)
        try:
            numeric_pressure = float(legacy_pressure)
        except (TypeError, ValueError):
            source["ambient_pressure"] = legacy_pressure
        else:
            source["ambient_pressure"] = numeric_pressure / 10.0 if numeric_pressure > 200 else numeric_pressure

    if "num_stages" in source and source["num_stages"] is not None:
        try:
            source["num_stages"] = max(1, int(source["num_stages"]))
        except (TypeError, ValueError):
            source["num_stages"] = 1

    if "num_units" in source and source["num_units"] is not None:
        try:
            source["num_units"] = max(1, int(source["num_units"]))
        except (TypeError, ValueError):
            source["num_units"] = 1

    if "use_consistency_iteration" not in source and "consistency_check" in source:
        source["use_consistency_iteration"] = source.get("consistency_check")

    # Map legacy & web UI aliases to canonical calculation keys.
    # ambient_press is handled above with its mbar -> kPa conversion; letting
    # the generic alias loop copy it again would overwrite the converted value.
    for alias_key, target_key in LEGACY_INPUT_ALIASES.items():
        if alias_key == "ambient_press":
            continue
        if alias_key in source and source[alias_key] is not None:
            source[target_key] = source[alias_key]

    for key, value in source.items():
        if key in LEGACY_INPUT_ALIASES and key not in ("calc_method", "eos_model"):
            continue
        if value is None:
            continue
        normalized[key] = copy.deepcopy(value)

    gas_comp = normalized.get("gas_comp") or {}
    normalized["gas_comp"] = dict(gas_comp)
    return normalized


def build_project_payload(
    inputs: Mapping[str, Any] | None,
    results: Any = None,
    *,
    version: str,
    timestamp: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Build a persisted project payload from normalized design inputs."""
    return {
        "version": version,
        "timestamp": (timestamp or datetime.datetime.now()).isoformat(),
        "inputs": normalize_design_inputs(inputs),
        "results": results if results else None,
    }
