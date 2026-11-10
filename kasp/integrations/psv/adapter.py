"""PSV / relief valve integration adapter (API 520/521).

Vendored engine: PSV Sizing Suite core (MIT).
The adapter accepts KASP SI inputs (bar, °C, kg/s) and converts them to the
US-unit contract expected by the upstream API 520 engine.
"""

from __future__ import annotations

from typing import Any, Dict, List

from kasp.core.constants import SUPPORTED_GASES
from kasp.core.mixture import GasMixtureBuilder
from kasp.integrations.base import ModuleManifest, module_response
from kasp.integrations.psv.vendor.core.engine import ReliefCase, size_relief_case
from kasp.integrations.psv.vendor.core.engine import STANDARD_EDITION

BAR_TO_PSIA = 14.5037738
KGS_TO_LB_H = 7936.64144
ATM_PSIA = 14.6959488


def _as_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coolprop_composition(composition: Dict[str, Any]) -> Dict[str, float]:
    """Convert KASP canonical mol% composition to CoolProp names + mole fractions."""
    if not composition:
        return {}
    total = sum(max(0.0, _as_float(v, 0.0) or 0.0) for v in composition.values())
    if total <= 0:
        return {}
    result = {}
    for name, value in composition.items():
        fraction = max(0.0, _as_float(value, 0.0) or 0.0) / total
        if fraction <= 0:
            continue
        canonical = GasMixtureBuilder._canonicalize_composition({name: 1.0})
        key = next(iter(canonical.keys()))
        cp_name = SUPPORTED_GASES.get(key)
        if cp_name:
            result[cp_name] = result.get(cp_name, 0.0) + fraction
    return result


class PSVAdapter:
    manifest = ModuleManifest(
        id="psv",
        name="PSV / Relief Valve Sizing",
        version="2.4.0",
        description="API 520 Part I / API 521 preliminary relief valve sizing, fire case and thermal expansion screening.",
        standards=["API 520 Part I (2020)", "API 521 (2020)", "ASME Section XIII"],
        source="PSV Sizing Suite (MIT)",
        capabilities=["gas", "liquid", "steam", "fire_wetted", "fire_unwetted", "thermal_expansion", "two_phase"],
    )

    def input_schema(self) -> Dict[str, Any]:
        return {
            "service": "gas | liquid | steam | fire_wetted | fire_unwetted | thermal_expansion | two_phase",
            "p1_bar": "Relieving pressure, bar(a). If omitted, derived from set_pressure_bar and overpressure_pct.",
            "p2_bar": "Total back pressure, bar(a). Default 1.01325.",
            "set_pressure_bar": "Set pressure, bar(g). Optional.",
            "overpressure_pct": "Default 10.0",
            "mass_flow_kgs": "Gas/steam mass flow, kg/s",
            "t_c": "Relieving temperature, °C",
            "composition": "KASP gas composition, mol%",
            "z": "Optional Z override",
            "mw": "Optional MW override, g/mol",
            "k": "Optional Cp/Cv override",
            "valve_type": "conventional | balanced_bellows | pilot",
            "num_valves": "Default 1",
            "pipe_id_in": "Optional inlet pipe ID, inch (API 520 Part II check)",
            "pipe_length_ft": "Optional inlet pipe length, ft",
        }

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = str(payload.get("service", "gas")).strip().lower()
        p2_bar = _as_float(payload.get("p2_bar"), ATM_PSIA / BAR_TO_PSIA)
        overpressure = _as_float(payload.get("overpressure_pct"), 10.0)
        set_bar_g = _as_float(payload.get("set_pressure_bar"))
        p1_bar = _as_float(payload.get("p1_bar"))
        if p1_bar is None and set_bar_g is not None:
            p1_bar = (set_bar_g + ATM_PSIA / BAR_TO_PSIA) * (1.0 + overpressure / 100.0)
        if p1_bar is None:
            p1_bar = ATM_PSIA / BAR_TO_PSIA

        common = {
            "p1_psia": p1_bar * BAR_TO_PSIA,
            "p2_psia": p2_bar * BAR_TO_PSIA,
            "set_pressure_psig": set_bar_g,
            "overpressure_pct": overpressure,
            "num_valves": max(1, int(_as_float(payload.get("num_valves"), 1))),
            "valve_type": payload.get("valve_type", "conventional"),
            "capacity_certified": bool(payload.get("capacity_certified", True)),
        }

        case_fields: Dict[str, Any] = {"service": service, **common}
        composition = payload.get("composition") or {}
        cp_composition = _coolprop_composition(composition)
        if cp_composition:
            case_fields["composition"] = cp_composition
            case_fields["fraction_type"] = "mole"

        if service in ("gas", "steam"):
            mass_flow = _as_float(payload.get("mass_flow_kgs"))
            if mass_flow is not None:
                case_fields["w_lb_h"] = mass_flow * KGS_TO_LB_H
            t_c = _as_float(payload.get("t_c"), 15.0)
            case_fields["t_rankine"] = (t_c + 273.15) * 1.8
            if service == "steam":
                case_fields["use_napier"] = bool(payload.get("use_napier", True))
            else:
                case_fields["use_napier"] = False
                # Let the core auto-compute z/mw/k from composition when possible.
                if payload.get("z") is not None:
                    case_fields["z"] = _as_float(payload.get("z"))
                if payload.get("mw") is not None:
                    case_fields["mw"] = _as_float(payload.get("mw"))
                if payload.get("k") is not None:
                    case_fields["k"] = _as_float(payload.get("k"))
        elif service == "liquid":
            case_fields["q_gpm"] = _as_float(payload.get("q_gpm"))
            case_fields["g"] = _as_float(payload.get("g"))
            case_fields["mu_cp"] = _as_float(payload.get("mu_cp"), 1.0)
            if payload.get("kw") is not None:
                case_fields["kw"] = _as_float(payload.get("kw"))
        elif service == "fire_wetted":
            case_fields["a_wetted_sqft"] = _as_float(payload.get("a_wetted_sqft"))
            case_fields["heat_of_vap_btu_lb"] = _as_float(payload.get("heat_of_vap_btu_lb"))
            case_fields["t_rankine"] = (_as_float(payload.get("t_c"), 15.0) + 273.15) * 1.8
            case_fields["f_factor"] = _as_float(payload.get("f_factor"), 1.0)
            case_fields["adequate_drainage"] = bool(payload.get("adequate_drainage", False))
        elif service == "fire_unwetted":
            case_fields["a_exposed_sqft"] = _as_float(payload.get("a_exposed_sqft"))
            case_fields["t_gas_rankine"] = (_as_float(payload.get("t_gas_c"), 15.0) + 273.15) * 1.8
            case_fields["t_wall_rankine"] = (_as_float(payload.get("t_wall_c"), 200.0) + 273.15) * 1.8
            case_fields["k"] = _as_float(payload.get("k"), 1.3)
        elif service == "thermal_expansion":
            # The upstream model uses a simple hydraulic expansion load.
            case_fields["q_gpm"] = _as_float(payload.get("q_gpm"))
            case_fields["g"] = _as_float(payload.get("g"))
        elif service == "two_phase":
            case_fields["w_lb_h"] = (_as_float(payload.get("mass_flow_kgs"), 0.0) or 0.0) * KGS_TO_LB_H
            case_fields["p0_psia"] = common["p1_psia"]
            case_fields["p_back_psia"] = common["p2_psia"]
            case_fields["v0_ft3_lb"] = _as_float(payload.get("v0_ft3_lb"))
            case_fields["omega"] = _as_float(payload.get("omega"))
            if payload.get("v9_ft3_lb") is not None:
                case_fields["v9_ft3_lb"] = _as_float(payload.get("v9_ft3_lb"))
        else:
            raise ValueError(f"Desteklenmeyen PSV servisi: {service}")

        # Optional inlet piping screening (API 520 Part II)
        for key in ("pipe_id_in", "pipe_length_ft", "fittings_90deg", "fittings_45deg", "gate_valves", "roughness_in", "piping_density_lb_ft3", "piping_viscosity_cp", "remote_sensing"):
            if payload.get(key) is not None:
                case_fields[key] = payload[key]

        case = ReliefCase(**case_fields)
        raw = size_relief_case(case)
        warnings = list(raw.get("warnings", []) or [])
        if raw.get("Result_Meta", {}).get("Warnings"):
            warnings.extend(raw["Result_Meta"]["Warnings"])
        return module_response(
            self,
            raw,
            warnings=warnings,
            provenance={
                "standard": STANDARD_EDITION,
                "source": "PSV Sizing Suite core (MIT)",
                "units_in": "bar(a), °C, kg/s",
                "units_engine": "psia, °R, lb/h",
            },
        )
