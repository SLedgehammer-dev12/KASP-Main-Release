"""Calculation Orchestration Service for KASP.

Coordinates design calculations, multi-stage compression loops, consistency iterations,
API 617 power margin adjustments, and ISO 2314 industrial gas turbine selection.
Serves as the single source of truth (SSOT) for both Desktop and Web API calls.
"""

from __future__ import annotations

import logging
import datetime
import math
from typing import Dict, Any, Optional

from kasp.core.contracts import normalize_design_inputs
from kasp.core.thermo import ThermoEngine
from kasp.data.database import UnitDatabase
from kasp.services.validation_service import validate_design_inputs

logger = logging.getLogger(__name__)

SUPPORTED_CORE_EOS = (
    "coolprop",
    "pr",
    "srk",
    "gerg2008",
    "aga8",
    "thermopack",
    "neqsim",
    "ccp",
    "dwsim",
)

LEGACY_EOS_ALIASES = {
    "rk": "srk",
    "redlich-kwong": "srk",
    "vdw": "pr",
    "van_der_waals": "pr",
    "bwrs": "gerg2008",
    "peng-robinson": "pr",
    "gerg-2008": "gerg2008",
    "aga8-dc92": "aga8",
    "heos": "coolprop",
}


def resolve_supported_eos(raw_eos: Any) -> tuple[str, str, bool]:
    """Normalize an incoming EOS identifier and map legacy aliases safely.

    Returns:
        (requested_eos_clean, effective_target_eos, was_aliased)
    """
    requested = str(raw_eos or "pr").strip().lower()
    if not requested:
        requested = "pr"
    if requested in SUPPORTED_CORE_EOS:
        return requested, requested, False
    mapped = LEGACY_EOS_ALIASES.get(requested)
    if mapped:
        return requested, mapped, True
    return requested, requested, False


def resolve_supported_method(raw_method: Any) -> str:
    """Map legacy or shorthand compression path labels to canonical 6-method names."""
    from kasp.core.thermo_design_support import canonical_design_method_label

    return canonical_design_method_label(
        raw_method, default="Metot 6: Schultz 3-Üslü Gerçek Gaz"
    )


def serialize_turbine_recommendation(rec: Any, required_power_kw: float = 0.0) -> Dict[str, Any]:
    """Convert a TurbineRecommendation object or dict to a clean serializable dict."""
    if rec is None:
        return {}

    def _safe_float(val, default=0.0):
        if val is None:
            return default
        try:
            f = float(val)
            return f if math.isfinite(f) else default
        except (TypeError, ValueError):
            return default

    def _safe_opt_float(val):
        if val is None:
            return None
        try:
            f = float(val)
            return f if math.isfinite(f) else None
        except (TypeError, ValueError):
            return None

    if isinstance(rec, dict):
        d = dict(rec)
        avail = _safe_float(d.get("available_power_kw") or d.get("site_power_kw") or d.get("iso_power_kw"))
        margin_pct_raw = d.get("power_margin_percent")
        if margin_pct_raw is None:
            margin_pct_raw = d.get("power_margin_pct", d.get("power_margin"))
        margin_pct = _safe_float(margin_pct_raw)
        if margin_pct == 0.0 and required_power_kw > 0 and avail > 0:
            margin_pct = ((avail - required_power_kw) / required_power_kw) * 100.0
        d["power_margin_pct"] = round(margin_pct, 1)
        d["power_margin"] = round(margin_pct / 100.0, 4)

        surge_raw = d.get("surge_margin_percent")
        if surge_raw is None:
            surge_raw = d.get("surge_margin_pct")
        surge_opt = _safe_opt_float(surge_raw)
        d["surge_margin_pct"] = round(surge_opt, 1) if surge_opt is not None else None

        stonewall_raw = d.get("stonewall_margin_percent")
        if stonewall_raw is None:
            stonewall_raw = d.get("stonewall_margin_pct", d.get("choke_margin_pct"))
        stonewall_opt = _safe_opt_float(stonewall_raw)
        d["stonewall_margin_pct"] = round(stonewall_opt, 1) if stonewall_opt is not None else None
        if "meets_api617_surge" not in d and surge_opt is not None:
            d["meets_api617_surge"] = bool(surge_opt >= 10.0)
        iso_hr_d = _safe_float(d.get("iso_heat_rate_kj_kwh") or d.get("iso_heat_rate"))
        site_hr_d = _safe_float(d.get("site_heat_rate_kj_kwh") or d.get("site_heat_rate"))
        if "iso_thermal_efficiency_pct" not in d or d["iso_thermal_efficiency_pct"] is None:
            d["iso_thermal_efficiency_pct"] = round(360000.0 / iso_hr_d, 2) if iso_hr_d > 0 else None
        if "site_thermal_efficiency_pct" not in d or d["site_thermal_efficiency_pct"] is None:
            d["site_thermal_efficiency_pct"] = round(360000.0 / site_hr_d, 2) if site_hr_d > 0 else None
        return d

    avail_val = getattr(rec, "available_power_kw", None) or getattr(rec, "iso_power_kw", None)
    avail_power = round(_safe_float(avail_val), 1)
    iso_power = round(_safe_float(getattr(rec, "iso_power_kw", None)), 1)

    margin_val = getattr(rec, "power_margin_percent", None)
    if margin_val is None:
        margin_val = getattr(rec, "power_margin_pct", None)
    margin_pct = _safe_float(margin_val)
    if margin_pct == 0.0 and required_power_kw > 0 and avail_power > 0:
        margin_pct = ((avail_power - required_power_kw) / required_power_kw) * 100.0
    margin_pct = round(margin_pct, 1)

    surge_val = getattr(rec, "surge_margin_percent", None)
    if surge_val is None:
        surge_val = getattr(rec, "surge_margin_pct", None)
    surge_opt = _safe_opt_float(surge_val)
    surge_pct = round(surge_opt, 1) if surge_opt is not None else None

    stonewall_val = getattr(rec, "stonewall_margin_percent", None)
    if stonewall_val is None:
        stonewall_val = getattr(rec, "stonewall_margin_pct", None)
    stonewall_opt = _safe_opt_float(stonewall_val)
    stonewall_pct = round(stonewall_opt, 1) if stonewall_opt is not None else None

    meets_surge_raw = getattr(rec, "meets_api617_surge", None)
    meets_surge = bool(meets_surge_raw) if meets_surge_raw is not None else (bool(surge_pct >= 10.0) if surge_pct is not None else True)

    iso_hr_val = getattr(rec, "iso_heat_rate", None) or getattr(rec, "iso_heat_rate_kj_kwh", None)
    iso_hr = round(_safe_float(iso_hr_val), 1)

    site_hr_val = getattr(rec, "site_heat_rate", None) or getattr(rec, "site_heat_rate_kj_kwh", None)
    site_hr = round(_safe_float(site_hr_val), 1)

    name = getattr(rec, "turbine_name", None) or getattr(rec, "name", "")
    model = getattr(rec, "model", None) or name
    t_type = getattr(rec, "type_str", None) or getattr(rec, "type", "Industrial")
    score_val = getattr(rec, "selection_score", 0.0)
    score = round(_safe_float(score_val), 1)

    return {
        "name": name,
        "model": model,
        "manufacturer": getattr(rec, "manufacturer", "Genel"),
        "type": t_type,
        "iso_power_kw": iso_power,
        "available_power_kw": avail_power,
        "site_power_kw": avail_power,
        "iso_heat_rate_kj_kwh": iso_hr,
        "site_heat_rate_kj_kwh": site_hr,
        "iso_thermal_efficiency_pct": round(360000.0 / iso_hr, 2) if iso_hr > 0 else None,
        "site_thermal_efficiency_pct": round(360000.0 / site_hr, 2) if site_hr > 0 else None,
        "power_margin_pct": margin_pct,
        "power_margin": round(margin_pct / 100.0, 4),
        "surge_margin_pct": surge_pct,
        "stonewall_margin_pct": stonewall_pct,
        "meets_api617_surge": meets_surge,
        "efficiency_rating": str(getattr(rec, "efficiency_rating", "İyi")),
        "selection_score": score,
        "recommendation_level": str(getattr(rec, "recommendation_level", "Önerilen")),
        "status": "Uygun" if margin_pct >= 0 else "Yetersiz",
    }


def execute_design_calculation(
    inputs: Dict[str, Any],
    engine: Optional[ThermoEngine] = None,
    db: Optional[UnitDatabase] = None,
) -> Dict[str, Any]:
    """
    Execute full thermodynamic design calculation and gas turbine unit selection.
    
    1. Validates inputs
    2. Normalizes parameters and units
    3. Executes thermodynamic solver (multi-stage + consistency check)
    4. Applies API 617 un-margining before ISO derated turbine selection
    5. Returns unified result payload
    """
    start_time = datetime.datetime.now()
    engine = engine or ThermoEngine()
    db = db or UnitDatabase()

    # 1. Validation
    val_report = validate_design_inputs(inputs)
    if not val_report["is_valid"]:
        error_msgs = "; ".join(e["message"] for e in val_report["errors"])
        raise ValueError(f"Doğrulama hatası: {error_msgs}")

    # 2. Normalization
    norm_inputs = normalize_design_inputs(inputs)
    requested_eos, target_eos, eos_aliased = resolve_supported_eos(norm_inputs.get("eos_method"))
    norm_inputs["eos_method"] = target_eos
    if "eos_model" in norm_inputs:
        norm_inputs["eos_model"] = target_eos
    if norm_inputs.get("method"):
        norm_inputs["method"] = resolve_supported_method(norm_inputs.get("method"))
    use_consistency = bool(inputs.get("use_consistency_iteration", inputs.get("consistency_check", False)))
    norm_inputs["use_consistency_iteration"] = use_consistency

    # 3. Thermodynamic Calculation
    logger.info("Executing design thermodynamic calculation (mode=%s)...", "consistency" if use_consistency else "direct")
    results = engine.calculate_design_performance_with_mode(norm_inputs)
    if eos_aliased:
        results["requested_eos"] = requested_eos
        results.setdefault("warnings", []).append(
            f"İstenen eski EOS '{requested_eos}' doğrudan desteklenmediği için '{target_eos.upper()}' modeli kullanıldı."
        )

    # 4. Turbine Selection Orchestration
    # Pass un-margined motor power so API 617 4% margin is not double-counted
    raw_motor_power = results.get("power_motor_per_unit_kw")
    if raw_motor_power is not None:
        required_power_per_unit_kw = float(raw_motor_power)
    else:
        raw_unit_power = results.get("power_unit_kw", 0.0)
        required_power_per_unit_kw = (float(raw_unit_power) / 1.04) if raw_unit_power else 0.0

    site_conditions = {
        "ambient_temp": float(norm_inputs.get("ambient_temp", 15.0)),
        "altitude": float(norm_inputs.get("altitude", 0.0)),
        "ambient_pressure": float(norm_inputs.get("ambient_pressure", 101.325)),
        "humidity": float(norm_inputs.get("humidity", 60.0)),
        "flow": results.get("mass_flow_per_unit_kgs"),
    }

    try:
        if hasattr(db, "get_all_turbines_full_data"):
            all_turbines = db.get_all_turbines_full_data()
        elif hasattr(db, "get_turbines"):
            all_turbines = db.get_turbines()
        else:
            all_turbines = []
    except Exception as exc:
        logger.warning("Could not fetch turbines from database: %s", exc)
        all_turbines = []

    num_units = max(1, int(results.get("num_units", norm_inputs.get("num_units", 1))))
    selected_units = []
    if all_turbines and required_power_per_unit_kw > 0:
        try:
            recs = engine.select_units(
                required_power_per_unit_kw,
                site_conditions,
                all_turbines,
                limit=5
            )
            for r in recs:
                unit_dict = serialize_turbine_recommendation(r, required_power_per_unit_kw)
                unit_dict["required_power_per_unit_kw"] = round(required_power_per_unit_kw, 1)
                unit_dict["num_units"] = num_units
                avail_kw = float(unit_dict.get("available_power_kw") or unit_dict.get("iso_power_kw", 0.0))
                unit_dict["station_total_power_kw"] = round(avail_kw * num_units, 1)
                unit_dict["recommendation_basis"] = f"Tek Ünite Başına Sürücü ({num_units} Tren Toplam)"
                selected_units.append(unit_dict)
        except Exception as exc:
            logger.warning("Turbine selection failed: %s", exc)
            selected_units = []

    results["selected_units"] = selected_units

    # 5. Enrich top-level results with thermodynamic state properties for UI parity
    in_props = results.get("inlet_properties") or {}
    out_props = results.get("outlet_properties") or {}

    p_in_raw = float(norm_inputs.get("p_in", 20.0))
    p_out_raw = float(norm_inputs.get("p_out", 60.0))
    t_in_raw = float(norm_inputs.get("t_in", 25.0))
    t_out_val = float(results.get("t_out", 65.0))
    ambient_pressure_pa = norm_inputs.get("ambient_pressure_pa")
    altitude_m = norm_inputs.get("altitude_m")

    try:
        p_in_bar_abs = engine.convert_pressure_to_pa(
            p_in_raw,
            str(norm_inputs.get("p_in_unit", "bar(a)")),
            ambient_pressure_pa=ambient_pressure_pa,
            altitude_m=altitude_m,
        ) / 1e5
    except Exception:
        p_in_bar_abs = p_in_raw

    try:
        p_out_bar_abs = engine.convert_pressure_to_pa(
            p_out_raw,
            str(norm_inputs.get("p_out_unit", "bar(a)")),
            ambient_pressure_pa=ambient_pressure_pa,
            altitude_m=altitude_m,
        ) / 1e5
    except Exception:
        p_out_bar_abs = p_out_raw

    try:
        t_in_c_val = engine.convert_temperature_to_k(
            t_in_raw,
            str(norm_inputs.get("t_in_unit", "°C")),
        ) - 273.15
    except Exception:
        t_in_c_val = t_in_raw

    results["p_in_bar"] = round(p_in_bar_abs, 3)
    results["p_out_bar"] = round(p_out_bar_abs, 3)
    results["t_in_c"] = round(t_in_c_val, 2)
    results["t_out_c"] = round(t_out_val, 2)

    results["z_in"] = round(float(in_props.get("Z", 0.0)), 4) if in_props.get("Z") is not None else 0.0
    results["z_out"] = round(float(out_props.get("Z", 0.0)), 4) if out_props.get("Z") is not None else 0.0
    results["k_in"] = round(float(in_props.get("k", 0.0)), 3) if in_props.get("k") is not None else 0.0
    results["k_out"] = round(float(out_props.get("k", 0.0)), 3) if out_props.get("k") is not None else 0.0
    results["k_s_in"] = round(float(in_props.get("k_s", 0.0)), 3) if in_props.get("k_s") is not None else 0.0
    results["k_s_out"] = round(float(out_props.get("k_s", 0.0)), 3) if out_props.get("k_s") is not None else 0.0

    rho_in = float(in_props.get("rho", 0.0)) if in_props.get("rho") is not None else 0.0
    rho_out = float(out_props.get("rho", 0.0)) if out_props.get("rho") is not None else 0.0
    results["rho_in"] = round(rho_in, 3)
    results["rho_out"] = round(rho_out, 3)
    results["v_in"] = round(1.0 / rho_in, 5) if rho_in > 0 else 0.0
    results["v_out"] = round(1.0 / rho_out, 5) if rho_out > 0 else 0.0

    results["speed_of_sound_in"] = round(float(in_props.get("a", 0.0)), 1) if in_props.get("a") is not None else 0.0
    results["speed_of_sound_out"] = round(float(out_props.get("a", 0.0)), 1) if out_props.get("a") is not None else 0.0
    results["cp_in"] = round(float(in_props.get("Cp", 0.0)), 1) if in_props.get("Cp") is not None else 0.0
    results["cp_out"] = round(float(out_props.get("Cp", 0.0)), 1) if out_props.get("Cp") is not None else 0.0
    results["cv_in"] = round(float(in_props.get("Cv", 0.0)), 1) if in_props.get("Cv") is not None else 0.0
    results["cv_out"] = round(float(out_props.get("Cv", 0.0)), 1) if out_props.get("Cv") is not None else 0.0
    results["h_in"] = round(float(in_props.get("H", 0.0)), 1) if in_props.get("H") is not None else 0.0
    results["h_out"] = round(float(out_props.get("H", 0.0)), 1) if out_props.get("H") is not None else 0.0
    results["s_in"] = round(float(in_props.get("S", 0.0)), 1) if in_props.get("S") is not None else 0.0
    results["s_out"] = round(float(out_props.get("S", 0.0)), 1) if out_props.get("S") is not None else 0.0
    results["mu_in"] = float(in_props.get("mu", 0.0)) if in_props.get("mu") is not None else 0.0
    results["mu_out"] = float(out_props.get("mu", 0.0)) if out_props.get("mu") is not None else 0.0
    results["phase_in"] = str(in_props.get("phase", "Gaz"))
    results["phase_out"] = str(out_props.get("phase", "Gaz"))

    # Ensure stage dictionaries have stage-level power and *display* keys.
    # Canonical stage units from the thermodynamic core are Pa and K.
    # Web/desktop consumers expect p_in_bar/p_out_bar in bar(a) and t_in_c/t_out_c in °C.
    for stg in results.get("stages", []):
        if "power_kw" not in stg or stg["power_kw"] is None:
            stg["power_kw"] = stg.get("power_gas_kw", 0.0)

        p_in_raw = float(stg.get("p_in", 0.0) or 0.0)
        p_out_raw = float(stg.get("p_out", 0.0) or 0.0)
        t_in_raw = float(stg.get("t_in", 0.0) or 0.0)
        t_out_raw = float(stg.get("t_out", 0.0) or 0.0)

        # Pa -> bar(a) (defensive: already-bar values are preserved)
        stg["p_in_bar"] = round(p_in_raw / 1e5, 4) if abs(p_in_raw) > 1e4 else round(p_in_raw, 4)
        stg["p_out_bar"] = round(p_out_raw / 1e5, 4) if abs(p_out_raw) > 1e4 else round(p_out_raw, 4)

        # K -> °C (defensive: already-°C values are preserved)
        stg["t_in_c"] = round(t_in_raw - 273.15, 2) if t_in_raw > 200.0 else round(t_in_raw, 2)
        stg["t_out_c"] = round(t_out_raw - 273.15, 2) if t_out_raw > 200.0 else round(t_out_raw, 2)

    # 6. Attach calculation metadata
    elapsed_sec = (datetime.datetime.now() - start_time).total_seconds()
    results["calculation_time_sec"] = round(elapsed_sec, 3)
    results["validation_warnings"] = val_report.get("warnings", [])

    return results
