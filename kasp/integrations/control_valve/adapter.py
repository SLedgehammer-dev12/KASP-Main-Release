"""Control Valve Sizing integration adapter (IEC 60534 / ISA).

Vendored engine: Control Valve Sizing core.
The adapter accepts KASP SI inputs and uses KASP real-gas properties for
Z/MW/k/viscosity and standard density.
"""

from __future__ import annotations

import os
import sys
from dataclasses import fields
from typing import Any, Dict, List

from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver
from kasp.integrations.base import ModuleManifest, module_response

_VENDOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "vendor"))
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

from valve_sizing import (  # noqa: E402
    GasSizingInput,
    LiquidSizingInput,
    size_gas_valve,
    size_liquid_valve,
)

_STANDARD_T_K = 288.15
_STANDARD_P_PA = 101325.0
BAR_TO_PSI = 14.5037738


def _f(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _result_dict(result) -> Dict[str, Any]:
    out = {}
    for field in fields(result):
        out[field.name] = getattr(result, field.name)
    out.update(getattr(result, "extra", {}) or {})
    return out


_EOS_ALIASES = {
    "coolprop": "coolprop",
    "heos": "coolprop",
    "pr": "pr",
    "peng-robinson": "pr",
    "bwrs": "gerg2008",
    "srk": "srk",
    "rk": "srk",
    "gerg2008": "gerg2008",
    "gerg-2008": "gerg2008",
    "aga8": "aga8",
    "thermopack": "thermopack",
    "ccp": "ccp",
    "dwsim": "dwsim",
    "neqsim": "neqsim",
}

_EOS_LABELS = {
    "coolprop": "KASP CoolProp (HEOS)",
    "pr": "KASP Peng-Robinson (PR)",
    "srk": "KASP SRK",
    "gerg2008": "KASP GERG-2008",
    "aga8": "KASP AGA8-DC92",
    "thermopack": "KASP ThermoPack",
    "ccp": "KASP CCP",
    "dwsim": "KASP DWSIM",
    "neqsim": "KASP NeqSim",
}


def _normalize_eos(raw_eos: Any) -> str:
    if raw_eos is None:
        return "gerg2008"
    cleaned = str(raw_eos).strip().lower()
    if not cleaned:
        return "gerg2008"
    return _EOS_ALIASES.get(cleaned, "pr")


def _build_gas_obj_for_eos(composition: Dict[str, Any], eos_method: str):
    comp_frac = GasMixtureBuilder.validate_and_normalize(composition)
    if eos_method == "coolprop":
        return GasMixtureBuilder.build_coolprop_string(comp_frac)
    if eos_method == "neqsim":
        return GasMixtureBuilder.build_neqsim_input(comp_frac)
    return GasMixtureBuilder.build_thermo_data(comp_frac)


class ControlValveAdapter:
    manifest = ModuleManifest(
        id="control_valve",
        name="Control Valve Sizing",
        version="3.5.2",
        description="IEC 60534 / ISA Cv/Kv sizing, valve selection, choked-flow check, noise and actuator screening.",
        standards=["IEC 60534-2-1", "ISA 75.01.01", "IEC 60534-8-4", "API RP 14E"],
        source="Control Valve Sizing core",
        capabilities=["gas", "liquid", "cv_kv", "valve_selection", "noise", "actuator", "choked_flow"],
    )

    def input_schema(self) -> Dict[str, Any]:
        return {
            "service": "gas | liquid",
            "composition": "KASP gas composition, mol% (gas service)",
            "eos_model": "Optional EOS model (pr, srk, coolprop, gerg2008, aga8, thermopack, neqsim)",
            "mass_flow_kgs": "Gas mass flow, kg/s",
            "flow_m3h": "Liquid volumetric flow, m3/h",
            "density_kg_m3": "Liquid density (liquid service)",
            "vapor_pressure_bar_a": "Liquid vapor pressure",
            "critical_pressure_bar_a": "Liquid critical pressure",
            "viscosity_pa_s": "Optional viscosity override",
            "p_in_bar": "Inlet pressure, bar(a)",
            "p_out_bar": "Outlet pressure, bar(a)",
            "t_c": "Temperature, °C",
            "design_margin_pct": "Default 0",
            "target_dn_mm": "Optional target valve DN, mm",
            "pipe_inlet_diameter_mm": "Optional pipe ID",
            "pipe_outlet_diameter_mm": "Optional pipe ID",
            "path": "Optional station path label (ASV/TCV/PCV)",
        }

    def _gas_properties(self, composition, p_in_bar, t_c, eos_model: str = "gerg2008"):
        solver = ThermodynamicSolver()
        eos_key = _normalize_eos(eos_model)
        gas_obj = _build_gas_obj_for_eos(composition, eos_key)
        state = solver.get_properties(p_in_bar * 1e5, t_c + 273.15, gas_obj, eos_key)
        std_obj = _build_gas_obj_for_eos(composition, eos_key)
        std_state = solver.get_properties(_STANDARD_P_PA, _STANDARD_T_K, std_obj, eos_key)
        return state, std_state, eos_key

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        service = str(payload.get("service", "gas")).strip().lower()
        p_in = _f(payload.get("p_in_bar"), 60.0)
        p_out = _f(payload.get("p_out_bar"), max(0.1, p_in - 5.0))
        t_c = _f(payload.get("t_c"), 40.0)
        design_margin = _f(payload.get("design_margin_pct"), 0.0)
        target_dn = _f(payload.get("target_dn_mm"))
        pipe_in = _f(payload.get("pipe_inlet_diameter_mm"))
        pipe_out = _f(payload.get("pipe_outlet_diameter_mm"))
        raw_eos = payload.get("eos_model") or payload.get("eos_method")
        eos_used = _normalize_eos(raw_eos)
        warnings: List[str] = []

        if service == "gas":
            composition = payload.get("composition") or {}
            if not composition:
                raise ValueError("Gaz vana boyutlandırması için composition gerekli.")
            state, std_state, eos_used = self._gas_properties(composition, p_in, t_c, eos_used)
            mass_flow = _f(payload.get("mass_flow_kgs"), _f(payload.get("mass_flow_kg_s"), 0.0)) or 0.0
            flow_nm3h = mass_flow / max(1e-9, std_state.density) * 3600.0
            data = GasSizingInput(
                flow_nm3h=flow_nm3h,
                inlet_pressure_bar_a=p_in,
                outlet_pressure_bar_a=p_out,
                temperature_c=t_c,
                molecular_weight=state.MW,
                specific_heat_ratio=state.k,
                viscosity_pa_s=_f(payload.get("viscosity_pa_s"), state.raw_props.get("mu", 1.1e-5)),
                z=state.Z,
                pipe_inlet_diameter_mm=pipe_in,
                pipe_outlet_diameter_mm=pipe_out,
            )
            result = size_gas_valve(
                data,
                design_margin_pct=design_margin,
                target_dn_mm=target_dn,
            )
        elif service == "liquid":
            data = LiquidSizingInput(
                flow_m3h=_f(payload.get("flow_m3h"), 0.0) or 0.0,
                density_kg_m3=_f(payload.get("density_kg_m3"), 1000.0),
                vapor_pressure_bar_a=_f(payload.get("vapor_pressure_bar_a"), 0.0),
                critical_pressure_bar_a=_f(payload.get("critical_pressure_bar_a"), 220.0),
                viscosity_pa_s=_f(payload.get("viscosity_pa_s"), 1e-3),
                inlet_pressure_bar_a=p_in,
                outlet_pressure_bar_a=p_out,
                temperature_c=t_c,
                pipe_inlet_diameter_mm=pipe_in,
                pipe_outlet_diameter_mm=pipe_out,
            )
            result = size_liquid_valve(
                data,
                design_margin_pct=design_margin,
                target_dn_mm=target_dn,
            )
        else:
            raise ValueError(f"Desteklenmeyen vana servisi: {service}")

        raw = _result_dict(result)
        gas_props_label = _EOS_LABELS.get(eos_used, f"KASP {eos_used.upper()}") if service == "gas" else "liquid inputs"
        normalized = {
            "service": raw.get("service"),
            "required_cv": raw.get("required_cv"),
            "required_kv": raw.get("required_kv"),
            "valve_dn_mm": raw.get("valve_dn_mm"),
            "valve_inch": raw.get("valve_inch"),
            "rated_cv": raw.get("rated_cv"),
            "rated_kv": raw.get("rated_kv"),
            "delta_p_bar": raw.get("delta_p_bar"),
            "is_choked": raw.get("is_choked"),
            "opening_percent": raw.get("opening_percent"),
            "rangeability_ok": raw.get("rangeability_ok"),
            "design_margin_pct": raw.get("design_margin_pct"),
            "valve_meta": raw.get("valve_meta"),
            "noise_db": raw.get("noise_db"),
            "actuator": raw.get("actuator"),
            "warning": raw.get("warning"),
            "path": payload.get("path"),
            "eos_model": eos_used if service == "gas" else None,
            "gas_properties_eos": gas_props_label,
            "detail": raw,
        }
        if raw.get("warning"):
            warnings.append(str(raw["warning"]))
        if raw.get("is_choked"):
            warnings.append("Vana choked (boğulmuş) akış bölgesinde; daha büyük vana veya farklı trim değerlendirilmeli.")
        if raw.get("rangeability_ok") is False:
            warnings.append("Vana rangeability dışında; daha küçük trim veya vana seçilmeli.")

        return module_response(
            self,
            normalized,
            warnings=warnings,
            provenance={
                "standard": "IEC 60534-2-1 / ISA 75.01.01 / IEC 60534-8-4",
                "source": "Control Valve Sizing core",
                "gas_properties": gas_props_label,
            },
        )
