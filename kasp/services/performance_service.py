"""Pure-Python Performance (Off-Design / ASME PTC-10) Service for KASP.

Calculates actual compressor efficiency, shaft power, fuel consumption, and
ASME PTC-10 / ISO 5389 site correction factors from field measurements, comparing
them against design baseline values.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional

from kasp.core.constants import MOLAR_MASSES, R_UNIVERSAL_J_MOL_K, normalize_component
from kasp.core.thermo import ThermoEngine
from kasp.core.units import UnitSystem

logger = logging.getLogger(__name__)


_PERF_EOS_ALIASES = {
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


def _canonical_std_flow_unit(raw_unit: str) -> Optional[str]:
    u_low = raw_unit.strip().lower()
    if u_low in ("sm³/h", "sm3/h", "smâ³/h"):
        return "Sm³/h"
    if u_low in ("nm³/h", "nm3/h", "nmâ³/h"):
        return "Nm³/h"
    if u_low == "mmscfd":
        return "MMSCFD"
    if u_low == "mmscmd":
        return "MMSCMD"
    if u_low in ("kmol/h", "kgmol/h"):
        return "kmol/h"
    return None


def _estimate_mixture_mw_g_mol(gas_comp: Dict[str, Any]) -> float:
    total = 0.0
    weighted = 0.0
    for comp, val in (gas_comp or {}).items():
        try:
            frac = float(val)
        except (TypeError, ValueError):
            continue
        if frac <= 0:
            continue
        canon = normalize_component(comp)
        mw = MOLAR_MASSES.get(canon, MOLAR_MASSES.get(str(comp).upper(), 16.043))
        total += frac
        weighted += frac * mw
    return (weighted / total) if total > 0 else 16.043


def _pct_dev(actual_val: float, ref_val: float) -> float:
    if not math.isfinite(actual_val) or not math.isfinite(ref_val) or abs(ref_val) <= 1e-12:
        return 0.0
    return ((actual_val - ref_val) / ref_val) * 100.0


def _to_percent(val: Any, fallback_pct: float) -> float:
    try:
        v = float(val)
    except (TypeError, ValueError):
        return fallback_pct
    if not math.isfinite(v) or v <= 0:
        return fallback_pct
    return v * 100.0 if v <= 1.0 else v


def _stage_temperature_c(stage: Dict[str, Any], key_c: str, key_plain: str) -> Optional[float]:
    """Read a stage temperature in °C from the enriched or core stage contract."""
    for key in (key_c, key_plain):
        if key not in stage:
            continue
        try:
            value = float(stage[key])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _resolve_stage_index(raw_index: Any, stages: Any) -> Optional[int]:
    """Return a valid 0-based stage index or None when no explicit section is selected."""
    if raw_index is None or raw_index == "" or not isinstance(stages, list) or not stages:
        return None
    try:
        idx = int(raw_index)
    except (TypeError, ValueError):
        return None
    return idx if 0 <= idx < len(stages) else None


def _is_intercooled_train(stages: Any) -> bool:
    """Detect intercooled multi-section trains (stage N inlet colder than N-1 outlet)."""
    if not isinstance(stages, list) or len(stages) < 2:
        return False
    previous_outlet: Optional[float] = None
    for stage in stages:
        if not isinstance(stage, dict):
            return False
        inlet = _stage_temperature_c(stage, "t_in_c", "t_in")
        if previous_outlet is not None and inlet is not None and inlet < previous_outlet - 0.5:
            return True
        previous_outlet = _stage_temperature_c(stage, "t_out_c", "t_out")
    return False


def evaluate_field_performance(
    field_data: Dict[str, Any],
    design_reference: Optional[Dict[str, Any]] = None,
    engine: Optional[ThermoEngine] = None,
) -> Dict[str, Any]:
    """
    Evaluate actual compressor test data against ASME PTC 10 / API 617 standards.

    field_data supports:
    - p_in, p_in_unit (default: 'bar(a)')
    - p_out, p_out_unit (default: 'bar(a)')
    - t_in, t_in_unit (default: '°C')
    - t_out, t_out_unit (default: '°C')
    - flow, flow_unit ('kg/s', 'kg/h', 'Sm³/h', 'Nm³/h', 'MMSCFD', 'MMSCMD', 'm³/h')
    - gas_comp
    - eos_model / eos_method
    - mech_eff (default: 98.0), therm_eff (default: 35.0), fuel_flow_kgh (optional measured fuel)
    - ambient_temp / t_amb, ambient_pressure, humidity, altitude
    """
    engine = engine or ThermoEngine()
    design_reference = design_reference or {}

    # ASME PTC-10 evaluates an uncooled compressor section. A multi-stage train with
    # intercooling cannot be collapsed into one polytropic section: doing so compares a
    # single-section head/power against the whole-train design and falsely reports a
    # critical deviation. Require an explicit stage_index in that case.
    stages_list = design_reference.get("stages")
    if _is_intercooled_train(stages_list) and _resolve_stage_index(field_data.get("stage_index"), stages_list) is None:
        raise ValueError(
            "Ara soğutuculu çok kademeli kompresör treni tek bir politropik kesit olarak "
            "değerlendirilemez. ASME PTC-10 gereği her soğutulmuş bölüm ayrı doğrulanmalıdır; "
            "lütfen stage_index ile ilgili kademeyi seçin (0..N-1)."
        )

    p_in_u = str(field_data.get("p_in_unit", "bar(a)"))
    p_out_u = str(field_data.get("p_out_unit", "bar(a)"))
    t_in_u = str(field_data.get("t_in_unit", "°C"))
    t_out_u = str(field_data.get("t_out_unit", "°C"))
    flow_u = str(field_data.get("flow_unit", "kg/s")).strip()

    p1_pa = UnitSystem.convert_pressure(float(field_data.get("p_in", 1.0)), p_in_u, "Pa")
    p2_pa = UnitSystem.convert_pressure(float(field_data.get("p_out", 2.0)), p_out_u, "Pa")
    p1_bara = p1_pa / 1e5
    p2_bara = p2_pa / 1e5
    t1_k = UnitSystem.convert_temperature(float(field_data.get("t_in", 20.0)), t_in_u, "K")
    t2_k = UnitSystem.convert_temperature(float(field_data.get("t_out", 50.0)), t_out_u, "K")
    t1_c = UnitSystem.convert_temperature(t1_k, "K", "°C")
    t2_c = UnitSystem.convert_temperature(t2_k, "K", "°C")

    if p1_pa <= 0 or p2_pa <= p1_pa:
        raise ValueError("Çıkış mutlak basıncı giriş mutlak basıncından büyük ve pozitif olmalıdır (PR > 1.0).")

    raw_eos = str(
        field_data.get("eos_model")
        or field_data.get("eos_method")
        or design_reference.get("eos_model")
        or design_reference.get("eos_method")
        or "coolprop"
    ).strip().lower()
    eos_method = _PERF_EOS_ALIASES.get(raw_eos, "coolprop")
    gas_comp = field_data.get("gas_comp") or design_reference.get("gas_comp") or {"METHANE": 100.0}
    gas_obj = engine._create_gas_object(gas_comp, eos_method)

    # Real EOS / MW flow conversion to kg/s
    flow_raw = float(field_data.get("flow", 10.0))
    if flow_raw <= 0 or not math.isfinite(flow_raw):
        raise ValueError("Gaz debisi pozitif bir sayı olmalıdır.")

    u_low = flow_u.lower()
    std_canon = _canonical_std_flow_unit(flow_u)
    if u_low == "kg/s":
        flow_kgs = flow_raw
    elif u_low in ("kg/h", "kgh"):
        flow_kgs = flow_raw / 3600.0
    elif u_low in ("m³/h", "m3/h", "acmh"):
        inlet_state = engine.thermo_solver.get_properties(p1_pa, t1_k, gas_obj, eos_method)
        rho_in = float(getattr(inlet_state, "density", 0.0) or 0.0)
        if rho_in <= 0:
            mw_kg = _estimate_mixture_mw_g_mol(gas_comp) / 1000.0
            rho_in = (p1_pa * mw_kg) / (R_UNIVERSAL_J_MOL_K * max(t1_k, 1.0))
        flow_kgs = (flow_raw / 3600.0) * rho_in
    elif std_canon is not None:
        flow_kgs = float(engine.convert_flow_to_kgs(flow_raw, std_canon, gas_obj, eos_method))
    else:
        flow_kgs = flow_raw

    # Resolve turbine thermal efficiency or measured fuel mass flow (kg/h)
    design_hr = float(design_reference.get("heat_rate", 0.0) or 0.0)
    inferred_design_therm_eff = (3600.0 / design_hr * 100.0) if design_hr > 0 else 35.0
    expected_therm_eff = _to_percent(
        field_data.get("therm_eff", design_reference.get("therm_eff", inferred_design_therm_eff)),
        35.0,
    )

    measured_fuel = field_data.get("fuel_flow_kgh", field_data.get("fuel_flow"))
    raw_driver_mode = str(field_data.get("driver_mode", "")).strip().lower()
    if measured_fuel is not None and float(measured_fuel) > 0:
        driver_mode = "fuel_flow"
        driver_val = float(measured_fuel)
    elif raw_driver_mode in ("fuel_flow", "fuel_kgh") and field_data.get("driver_val") is not None:
        driver_mode = "fuel_flow"
        driver_val = float(field_data.get("driver_val"))
    else:
        driver_mode = "turb_eff"
        driver_val = (
            float(field_data["driver_val"])
            if (raw_driver_mode == "turb_eff" and field_data.get("driver_val") is not None)
            else expected_therm_eff
        )

    amb_temp = float(
        field_data.get(
            "ambient_temp",
            field_data.get("t_amb", design_reference.get("ambient_temp", 15.0)),
        )
    )
    amb_press = float(
        field_data.get(
            "ambient_pressure",
            design_reference.get("ambient_pressure", 101.325),
        )
    )
    humidity = float(
        field_data.get(
            "humidity",
            design_reference.get("humidity", 60.0),
        )
    )
    altitude = float(
        field_data.get(
            "altitude",
            design_reference.get("altitude", 0.0),
        )
    )

    perf_inputs = {
        "p1_pa": p1_pa,
        "t1_k": t1_k,
        "p2_pa": p2_pa,
        "t2_k": t2_k,
        "flow_kgs": flow_kgs,
        "gas_comp": gas_comp,
        "eos_method": eos_method,
        "mech_eff": float(field_data.get("mech_eff", design_reference.get("mech_eff", 98.0))),
        "driver_mode": driver_mode,
        "driver_val": driver_val,
        "fuel_gas_comp": field_data.get("fuel_gas_comp", gas_comp),
        "site_correction_inputs": {
            "ambient_temp_c": amb_temp,
            "ambient_pressure_kpa": amb_press,
            "relative_humidity_pct": humidity,
            "altitude_m": altitude,
        },
    }

    raw_results = engine.evaluate_performance(perf_inputs)

    comparison_items = []

    def _comp(param_name: str, test_val: float, design_val: float, unit: str, tol_warn: float = 2.0, tol_crit: float = 5.0) -> Dict[str, Any]:
        test_f = float(test_val) if test_val is not None else 0.0
        design_f = float(design_val) if design_val is not None else 0.0
        dev_pct = _pct_dev(test_f, design_f)
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

    # Resolve active design reference (either a specific uncooled ASME PTC-10 stage section or overall train)
    active_ref = dict(design_reference)
    stages_list = design_reference.get("stages")
    raw_stage_idx = field_data.get("stage_index")
    if raw_stage_idx is not None and raw_stage_idx != "" and isinstance(stages_list, list) and len(stages_list) > 0:
        try:
            s_idx = int(raw_stage_idx)
        except (TypeError, ValueError):
            s_idx = -1
        if 0 <= s_idx < len(stages_list) and isinstance(stages_list[s_idx], dict):
            stg = stages_list[s_idx]
            num_u = max(1, int(design_reference.get("num_units", 1) or 1))
            num_s = max(1, len(stages_list))
            mech_tot = float(design_reference.get("mech_loss_total_kw", 0.0) or 0.0)
            stg_gas_tot = float(stg.get("power_kw", stg.get("power_gas_kw", 0.0)) or 0.0) * num_u
            active_ref["p_in_bar"] = stg.get("p_in_bar", active_ref.get("p_in_bar"))
            active_ref["p_out_bar"] = stg.get("p_out_bar", active_ref.get("p_out_bar"))
            active_ref["t_out_c"] = stg.get("t_out_c", active_ref.get("t_out_c"))
            active_ref["head_kj_kg"] = stg.get("head_kj_kg", active_ref.get("head_kj_kg"))
            active_ref["power_shaft_total_kw"] = stg_gas_tot + (mech_tot / num_s)
            active_ref["actual_poly_efficiency"] = stg.get(
                "poly_eff_diagnostic",
                stg.get("poly_eff", active_ref.get("actual_poly_efficiency")),
            )

    # Resolve design reference values in consistent SI/engineering units: bar(a), °C, kg/s, kJ/kg, kW
    if "p_in_bar" in active_ref and active_ref.get("p_in_bar") is not None:
        design_p_in_bara = float(active_ref["p_in_bar"])
    elif "p_in" in active_ref and active_ref.get("p_in") is not None:
        ref_pin_u = str(active_ref.get("p_in_unit", "bar(a)"))
        design_p_in_bara = UnitSystem.convert_pressure(float(active_ref["p_in"]), ref_pin_u, "bar(a)")
    else:
        design_p_in_bara = p1_bara

    if "p_out_bar" in active_ref and active_ref.get("p_out_bar") is not None:
        design_p_out_bara = float(active_ref["p_out_bar"])
    elif "p_out" in active_ref and active_ref.get("p_out") is not None:
        ref_pout_u = str(active_ref.get("p_out_unit", "bar(a)"))
        design_p_out_bara = UnitSystem.convert_pressure(float(active_ref["p_out"]), ref_pout_u, "bar(a)")
    else:
        design_p_out_bara = p2_bara

    design_t_out_c = float(
        active_ref.get("t_out_c", active_ref.get("t_out", t2_c))
        if active_ref.get("t_out_c", active_ref.get("t_out")) is not None
        else t2_c
    )
    design_flow_kgs = float(
        active_ref.get("mass_flow_total_kgs", active_ref.get("flow_kgs", flow_kgs))
        if active_ref.get("mass_flow_total_kgs", active_ref.get("flow_kgs")) is not None
        else flow_kgs
    )

    actual_head = float(raw_results.get("poly_head_kj_kg", 0.0))
    design_head = float(
        active_ref.get("head_kj_kg", active_ref.get("poly_head_kj_kg", actual_head))
        if active_ref.get("head_kj_kg", active_ref.get("poly_head_kj_kg")) is not None
        else actual_head
    )

    actual_pwr = float(raw_results.get("shaft_power_kw", 0.0))
    design_pwr = float(
        active_ref.get(
            "power_shaft_total_kw",
            active_ref.get("power_shaft_per_unit_kw", active_ref.get("power_unit_total_kw", actual_pwr)),
        )
        if active_ref.get(
            "power_shaft_total_kw",
            active_ref.get("power_shaft_per_unit_kw", active_ref.get("power_unit_total_kw")),
        )
        is not None
        else actual_pwr
    )

    # 6-metric ASME PTC-10 comparison matrix (normalized units)
    comparison_items.append(_comp("Giriş Basıncı", p1_bara, design_p_in_bara, "bar(a)"))
    comparison_items.append(_comp("Çıkış Basıncı", p2_bara, design_p_out_bara, "bar(a)"))
    comparison_items.append(_comp("Çıkış Sıcaklığı", t2_c, design_t_out_c, "°C"))
    comparison_items.append(_comp("Gaz Debisi", flow_kgs, design_flow_kgs, "kg/s"))
    comparison_items.append(_comp("Politropik Yük (Head)", actual_head, design_head, "kJ/kg"))
    comparison_items.append(_comp("Mil Gücü", actual_pwr, design_pwr, "kW"))

    # Efficiency, heat-rate, and power deviations for PDF report & UI KPIs
    actual_poly_eff = float(raw_results.get("poly_eff", 0.0))
    design_poly_eff = _to_percent(
        active_ref.get(
            "actual_poly_efficiency",
            active_ref.get("design_poly_efficiency", active_ref.get("poly_eff")),
        ),
        actual_poly_eff,
    )
    dev_poly_eff = round(_pct_dev(actual_poly_eff, design_poly_eff), 2)

    actual_therm_eff = float(raw_results.get("turb_eff", expected_therm_eff))
    dev_therm_eff = round(_pct_dev(actual_therm_eff, expected_therm_eff), 2)

    actual_hr = float(raw_results.get("actual_heat_rate", 0.0))
    expected_hr = (
        design_hr
        if design_hr > 0
        else ((3600.0 / (expected_therm_eff / 100.0)) if expected_therm_eff > 0 else actual_hr)
    )
    dev_hr = round(_pct_dev(actual_hr, expected_hr), 2)
    dev_pwr = round(_pct_dev(actual_pwr, design_pwr), 2)

    statuses = {c["status"] for c in comparison_items}
    max_eff_or_pwr_dev = max(abs(dev_poly_eff), abs(dev_pwr))
    if "CRITICAL" in statuses or max_eff_or_pwr_dev > 5.0:
        perf_status = {
            "status": "KRİTİK",
            "color": "red",
            "description": "Saha performans verilerinde ASME PTC-10 ±%5 kritik tolerans sınırını aşan sapma tespit edildi.",
            "recommendation": "Kompresör iç sızdırmazlıkları, kirlenme (fouling) ve saha enstrümantasyon kalibrasyonu incelenmelidir.",
        }
    elif "WARNING" in statuses or max_eff_or_pwr_dev > 2.0:
        perf_status = {
            "status": "DİKKAT",
            "color": "orange",
            "description": "Saha performans verilerinde ±%2 uyarı eşiğini aşan sapma gözlendi.",
            "recommendation": "Performans trend izleme sıklığını artırın ve sınır koşullarını doğrulayın.",
        }
    else:
        perf_status = {
            "status": "UYGUN",
            "color": "green",
            "description": "Saha performans değerleri ASME PTC-10 ve tasarım tolerans sınırları içindedir.",
            "recommendation": "Rutin izlemeye devam edin.",
        }

    raw_results["comparison"] = comparison_items
    raw_results["eos_model"] = eos_method
    raw_results["flow_kgs"] = round(flow_kgs, 4)
    raw_results["p_in_bar"] = round(p1_bara, 3)
    raw_results["p_out_bar"] = round(p2_bara, 3)
    raw_results["t_in_c"] = round(t1_c, 2)
    raw_results["t_out_c"] = round(t2_c, 2)
    raw_results["corrected_power_kw"] = round(float(raw_results.get("corrected_power_kw", actual_pwr)), 1)

    # ReportGenerator.generate_performance_report contract fields
    raw_results["actual_poly_eff"] = round(actual_poly_eff, 2)
    raw_results["design_poly_eff"] = round(design_poly_eff, 2)
    raw_results["deviation_poly_eff"] = dev_poly_eff
    raw_results["actual_therm_eff"] = round(actual_therm_eff, 2)
    raw_results["expected_therm_eff"] = round(expected_therm_eff, 2)
    raw_results["deviation_therm_eff"] = dev_therm_eff
    raw_results["expected_heat_rate"] = round(expected_hr, 1)
    raw_results["deviation_heat_rate"] = dev_hr
    raw_results["actual_power"] = round(actual_pwr, 1)
    raw_results["expected_power"] = round(design_pwr, 1)
    raw_results["deviation_power"] = dev_pwr
    raw_results["performance_status"] = perf_status

    return raw_results


def evaluate_ptc10_performance(
    field_data: Optional[Dict[str, Any]] = None,
    design_reference: Optional[Dict[str, Any]] = None,
    *,
    test_data: Optional[Dict[str, Any]] = None,
    design_point: Optional[Dict[str, Any]] = None,
    engine: Optional[ThermoEngine] = None,
) -> Dict[str, Any]:
    """Web API & service adapter accepting both (field_data, design_reference) and (test_data=, design_point=)."""
    actual_field = field_data if field_data is not None else (test_data or {})
    actual_design = design_reference if design_reference is not None else design_point
    return evaluate_field_performance(actual_field, actual_design, engine=engine)
