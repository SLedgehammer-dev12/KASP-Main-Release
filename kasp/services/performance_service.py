"""Pure-Python Performance (Off-Design / ASME PTC-10) Service for KASP.

Calculates actual compressor efficiency, shaft power, fuel consumption, and
ASME PTC-10 / ISO 5389 site correction factors from field measurements, comparing
them against design baseline values.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from kasp.core.units import UnitSystem
from kasp.core.thermo import ThermoEngine
from kasp.core.performance_corrections import calculate_site_correction_factors

logger = logging.getLogger(__name__)


def evaluate_field_performance(
    field_data: Dict[str, Any],
    design_reference: Optional[Dict[str, Any]] = None,
    engine: Optional[ThermoEngine] = None,
) -> Dict[str, Any]:
    """
    Evaluate actual compressor test data against ASME PTC 10 / API 617 standards.
    
    field_data expects:
    - p_in, p_in_unit
    - p_out, p_out_unit
    - t_in, t_in_unit
    - t_out, t_out_unit
    - flow, flow_unit
    - gas_comp
    - eos_method (default: 'coolprop')
    - mech_eff (default: 98.0)
    - ambient_temp, ambient_pressure, humidity
    """
    engine = engine or ThermoEngine()

    p_in_u = str(field_data.get("p_in_unit", "bar(g)"))
    p_out_u = str(field_data.get("p_out_unit", "bar(g)"))
    t_in_u = str(field_data.get("t_in_unit", "°C"))
    t_out_u = str(field_data.get("t_out_unit", "°C"))
    flow_u = str(field_data.get("flow_unit", "kg/s"))

    p1_pa = UnitSystem.convert_pressure(float(field_data.get("p_in", 1.0)), p_in_u, "Pa")
    p2_pa = UnitSystem.convert_pressure(float(field_data.get("p_out", 2.0)), p_out_u, "Pa")
    t1_k = UnitSystem.convert_temperature(float(field_data.get("t_in", 20.0)), t_in_u, "K")
    t2_k = UnitSystem.convert_temperature(float(field_data.get("t_out", 50.0)), t_out_u, "K")

    # Flow conversion to kg/s
    flow_raw = float(field_data.get("flow", 10.0))
    if flow_u in ["kg/s"]:
        flow_kgs = flow_raw
    elif flow_u in ["kg/h"]:
        flow_kgs = flow_raw / 3600.0
    else:
        # Standard volume or volumetric flow
        flow_kgs = flow_raw

    eos_method = field_data.get("eos_method", "coolprop")
    gas_comp = field_data.get("gas_comp") or {"METHANE": 100.0}

    perf_inputs = {
        "p1_pa": p1_pa,
        "t1_k": t1_k,
        "p2_pa": p2_pa,
        "t2_k": t2_k,
        "flow_kgs": flow_kgs,
        "gas_comp": gas_comp,
        "eos_method": eos_method,
        "mech_eff": float(field_data.get("mech_eff", 98.0)),
        "driver_mode": "gas_turbine",
        "driver_val": 1.0,
        "fuel_gas_comp": field_data.get("fuel_gas_comp", gas_comp),
        "site_correction_inputs": {
            "ambient_temp_c": float(field_data.get("ambient_temp", 15.0)),
            "ambient_pressure_kpa": float(field_data.get("ambient_pressure", 101.325)),
            "relative_humidity_pct": float(field_data.get("humidity", 60.0)),
            "altitude_m": float(field_data.get("altitude", 0.0)),
        }
    }

    raw_results = engine.evaluate_performance(perf_inputs)

    # Comparison matrix against design reference
    design_reference = design_reference or {}
    comparison_items = []

    def _comp(param_name, test_val, design_val, unit, tol_warn=2.0, tol_crit=5.0):
        test_f = float(test_val) if test_val is not None else 0.0
        design_f = float(design_val) if design_val is not None else 0.0
        dev_pct = ((test_f - design_f) / design_f * 100.0) if design_f != 0 else 0.0
        abs_dev = abs(dev_pct)
        if abs_dev <= tol_warn:
            status = "OK"
            badge = "✓ Uygun"
        elif abs_dev <= tol_crit:
            status = "WARNING"
            badge = "⚠ Dikkat"
        else:
            status = "CRITICAL"
            badge = "✗ Kritik"

        return {
            # Canonical / legacy descriptive names
            "parameter": param_name,
            "test_value": round(test_f, 2),
            "design_value": round(design_f, 2),
            "deviation_pct": round(dev_pct, 2),
            "tolerance_pct": tol_crit,
            # Web UI contract aliases (kept in sync with performanceTab.js)
            "name": param_name,
            "test_val": round(test_f, 2),
            "design_val": round(design_f, 2),
            "dev_pct": round(dev_pct, 2),
            "tol_crit": tol_crit,
            "unit": unit,
            "status": status,
            "badge": badge,
        }

    # 1. P_in
    design_p_in = design_reference.get("p_in_bar", design_reference.get("p_in", field_data.get("p_in")))
    comparison_items.append(_comp(
        "Giriş Basıncı",
        field_data.get("p_in"),
        design_p_in,
        p_in_u
    ))
    # 2. P_out
    design_p_out = design_reference.get("p_out_bar", design_reference.get("p_out", field_data.get("p_out")))
    comparison_items.append(_comp(
        "Çıkış Basıncı",
        field_data.get("p_out"),
        design_p_out,
        p_out_u
    ))
    # 3. T_out
    t_out_c = UnitSystem.convert_temperature(t2_k, "K", "°C")
    design_t_out = design_reference.get("t_out_c", design_reference.get("t_out", t_out_c))
    comparison_items.append(_comp("Çıkış Sıcaklığı", t_out_c, design_t_out, "°C"))
    # 4. Flow
    design_flow = design_reference.get("mass_flow_total_kgs", design_reference.get("flow", flow_raw))
    comparison_items.append(_comp("Gaz Debisi", flow_raw, design_flow, flow_u))
    # 5. Polytropic Head
    actual_head = raw_results.get("poly_head_kj_kg", 0.0)
    design_head = design_reference.get("head_kj_kg", design_reference.get("poly_head_kj_kg", actual_head))
    comparison_items.append(_comp("Politropik Yük (Head)", actual_head, design_head, "kJ/kg"))
    # 6. Shaft Power
    actual_pwr = raw_results.get("shaft_power_kw", 0.0)
    design_pwr = design_reference.get("power_shaft_total_kw", design_reference.get("power_unit_total_kw", actual_pwr))
    comparison_items.append(_comp("Mil Gücü", actual_pwr, design_pwr, "kW"))

    raw_results["comparison"] = comparison_items
    raw_results["t_out_c"] = round(t_out_c, 2)
    raw_results["corrected_power_kw"] = round(raw_results.get("corrected_power_kw", actual_pwr), 1)

    return raw_results


# Convenience alias for Web API
evaluate_ptc10_performance = evaluate_field_performance
