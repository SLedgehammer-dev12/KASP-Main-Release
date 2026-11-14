"""Compressor Station Modeling & Process Flow Service (station_service.py).

Implements rigorous process engineering sizing for natural gas compressor stations:
- Mainline Suction & Discharge Tie-ins with Pig Receiver and Pig Launcher
- Suction Header & Dynamic Parallel Cyclone Separators (Scrubbers)
- Dynamic Parallel Cartridge Coalescing / Dust Filters
- Compressor Shelter / Unit Building housing N Parallel Turbo-Compressor Trains
- Individual Hot Gas Anti-Surge Recycle Loops with Fast-Acting Valves
- Station-wide Main Recycle / Bypass Line (Discharge to Suction Header)
- Fin-Fan Gas Air Coolers (Cooling Heat Duty & Dynamic Bay Count)
- Overpressure & Emergency Depressurization (PSV & Blowdown Valves)
- Process Nodal Telemetry & Animated Flow Vector Velocities
"""

import logging
import math
from typing import Any, Dict, List, Optional
from kasp.core.constants import MOLAR_MASSES, R_UNIVERSAL_J_MOL_K, normalize_component
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.performance_corrections import ambient_pressure_from_altitude_kpa
from kasp.core.thermo import ThermoEngine
from kasp.core.units import UnitSystem
from kasp.services.pipe_sizing_service import PipeSizingService

logger = logging.getLogger(__name__)


def _has_explicit_value(inputs: Dict[str, Any], key: str) -> bool:
    if key not in inputs:
        return False
    val = inputs.get(key)
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    return True


def _resolve_site_ambient(
    inputs: Dict[str, Any],
    design_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve Design Tab atmospheric pressure (bar(a) & kPa), ambient temp (°C), and altitude (m)."""
    raw_alt = inputs.get("altitude_m", inputs.get("altitude"))
    try:
        altitude_m = float(raw_alt) if raw_alt not in (None, "") else 0.0
    except (TypeError, ValueError):
        altitude_m = 0.0
    if not math.isfinite(altitude_m):
        altitude_m = 0.0

    has_design_temp = (
        _has_explicit_value(inputs, "ambient_temp")
        or _has_explicit_value(inputs, "ambient_temp_c")
        or bool(design_results)
    )
    raw_amb_t = inputs.get("ambient_temp_c", inputs.get("ambient_temp"))
    try:
        ambient_temp_c = float(raw_amb_t) if raw_amb_t not in (None, "") else 15.0
    except (TypeError, ValueError):
        ambient_temp_c = 15.0
    if not math.isfinite(ambient_temp_c):
        ambient_temp_c = 15.0
    ambient_temp_c = max(-60.0, min(75.0, ambient_temp_c))

    has_design_p = (
        _has_explicit_value(inputs, "ambient_pressure")
        or _has_explicit_value(inputs, "ambient_pressure_kpa")
        or _has_explicit_value(inputs, "ambient_pressure_bar")
        or _has_explicit_value(inputs, "altitude")
        or _has_explicit_value(inputs, "altitude_m")
        or bool(design_results)
    )

    p_atm_bar: Optional[float] = None
    if _has_explicit_value(inputs, "ambient_pressure_bar"):
        try:
            cand = float(inputs["ambient_pressure_bar"])
            if math.isfinite(cand) and cand > 0.05:
                p_atm_bar = cand
        except (TypeError, ValueError):
            p_atm_bar = None

    if p_atm_bar is None:
        raw_p_amb = inputs.get("ambient_pressure_kpa", inputs.get("ambient_pressure"))
        if raw_p_amb not in (None, ""):
            try:
                val = float(raw_p_amb)
                if math.isfinite(val) and val > 0:
                    if 0.35 <= val <= 2.5:
                        p_atm_bar = val
                    elif val <= 250.0:
                        p_atm_bar = val / 100.0
                    else:
                        p_atm_bar = val / 1000.0
                    if altitude_m > 0 and abs(p_atm_bar * 100.0 - 101.325) < 1e-4:
                        p_atm_bar = ambient_pressure_from_altitude_kpa(altitude_m) / 100.0
            except (TypeError, ValueError):
                p_atm_bar = None

    if p_atm_bar is None:
        if altitude_m > 0:
            p_atm_bar = ambient_pressure_from_altitude_kpa(altitude_m) / 100.0
        else:
            p_atm_bar = 1.01325

    p_atm_bar = max(0.35, min(2.0, float(p_atm_bar)))
    return {
        "p_atm_bar": p_atm_bar,
        "ambient_pressure_kpa": round(p_atm_bar * 100.0, 4),
        "ambient_temp_c": ambient_temp_c,
        "altitude_m": altitude_m,
        "p_atm_source": "design_tab" if has_design_p else "fixed_default",
        "ambient_temp_source": "design_tab" if has_design_temp else "fixed_default",
    }


def _pressure_to_bar_a(raw_val: float, raw_unit: str, p_atm_bar: float = 1.01325) -> float:
    unit = str(raw_unit or "bar(a)").strip()
    u_low = unit.lower()
    if u_low == "bar(g)":
        return raw_val + p_atm_bar
    if u_low == "psig":
        return (raw_val / 14.5037738) + p_atm_bar
    if u_low == "kpa(g)":
        return (raw_val / 100.0) + p_atm_bar
    if u_low == "mpa(g)":
        return (raw_val * 10.0) + p_atm_bar
    try:
        return UnitSystem.convert_pressure(raw_val, unit, "bar(a)")
    except Exception:
        return raw_val

_STATION_EOS_ALIASES = {
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


def _normalize_station_eos(raw_eos: Any) -> str:
    if not raw_eos:
        return "pr"
    cleaned = str(raw_eos).strip().lower()
    return _STATION_EOS_ALIASES.get(cleaned, "pr")


def _canonical_flow_unit(raw_unit: Any) -> str:
    u = str(raw_unit or "kg/s").strip()
    u_low = u.lower()
    if u_low == "kg/s":
        return "kg/s"
    if u_low in ("kg/h", "kgh"):
        return "kg/h"
    if u_low in ("sm³/h", "sm3/h", "smâ³/h"):
        return "Sm³/h"
    if u_low in ("nm³/h", "nm3/h", "nmâ³/h"):
        return "Nm³/h"
    if u_low in ("m³/h", "m3/h", "acmh"):
        # Actual (inlet) volumetric flow — requires inlet P/T, never a standard-volume alias.
        return "m³/h"
    if u_low == "mmscfd":
        return "MMSCFD"
    if u_low == "mmscmd":
        return "MMSCMD"
    if u_low in ("kmol/h", "kgmol/h"):
        return "kmol/h"
    return u


def _actual_m3h_to_kgs(
    raw_flow: float,
    inputs: Dict[str, Any],
    engine: ThermoEngine,
    gas_obj: Any,
    eos_key: str,
    mw_g_mol: float,
    p_atm_bar: float = 1.01325,
) -> float:
    """Convert actual inlet m³/h (ACMH) to kg/s using real inlet density at test P/T."""
    try:
        p_bara = _pressure_to_bar_a(
            float(inputs.get("p_in", 25.0) or 25.0),
            str(inputs.get("p_in_unit", "bar(a)")),
            p_atm_bar,
        )
    except (TypeError, ValueError):
        p_bara = 25.0
    try:
        t_k = UnitSystem.convert_temperature(
            float(inputs.get("t_in", 20.0) or 20.0),
            str(inputs.get("t_in_unit", "°C")),
            "K",
        )
    except (TypeError, ValueError):
        t_k = 293.15
    rho_in = 0.0
    if gas_obj is not None:
        try:
            state = engine.thermo_solver.get_properties(p_bara * 1e5, t_k, gas_obj, eos_key)
            rho_in = float(getattr(state, "density", 0.0) or 0.0)
        except Exception:
            rho_in = 0.0
    if rho_in <= 0 or not math.isfinite(rho_in):
        mw_kg = max(1e-3, mw_g_mol / 1000.0)
        rho_in = (p_bara * 1e5 * mw_kg) / (R_UNIVERSAL_J_MOL_K * max(t_k, 1.0))
    return (raw_flow / 3600.0) * rho_in


def _fallback_convert_flow_with_mw(raw_flow: float, flow_unit: str, mw_g_mol: float) -> float:
    """Physical MW-based ideal-gas standard conversion fallback when EOS solver cannot run."""
    mw_kg_mol = max(1e-3, mw_g_mol / 1000.0)
    canon = _canonical_flow_unit(flow_unit)
    if canon == "kg/s":
        return raw_flow
    if canon == "kg/h":
        return raw_flow / 3600.0
    if canon in ("Sm³/h", "MMSCMD"):
        rho_std = (101325.0 * mw_kg_mol) / (R_UNIVERSAL_J_MOL_K * 288.15)
        if canon == "Sm³/h":
            return (raw_flow * rho_std) / 3600.0
        return (raw_flow * 1e6 / 86400.0) * rho_std
    if canon == "Nm³/h":
        rho_norm = (101325.0 * mw_kg_mol) / (R_UNIVERSAL_J_MOL_K * 273.15)
        return (raw_flow * rho_norm) / 3600.0
    if canon == "MMSCFD":
        rho_scfd = (101559.8 * mw_kg_mol) / (R_UNIVERSAL_J_MOL_K * 288.7056)
        return (raw_flow * 1e6 * 0.0283168466 / 86400.0) * rho_scfd
    if canon == "kmol/h":
        return (raw_flow * mw_g_mol) / 3600.0
    return raw_flow


_STANDARD_DN_MM = [50, 80, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000, 1050, 1200]

_API526_FLANGE_SIZES = {
    "D": ("1\"", "2\""),
    "E": ("1\"", "2\""),
    "F": ("1.5\"", "2\""),
    "G": ("1.5\"", "3\""),
    "H": ("2\"", "3\""),
    "J": ("3\"", "4\""),
    "K": ("3\"", "4\""),
    "L": ("4\"", "6\""),
    "M": ("4\"", "6\""),
    "N": ("4\"", "6\""),
    "P": ("4\"", "6\""),
    "Q": ("6\"", "8\""),
    "R": ("6\"", "10\""),
    "T": ("8\"", "10\""),
}


def _next_standard_dn(dn_mm: float) -> float:
    for nominal in _STANDARD_DN_MM:
        if nominal >= dn_mm:
            return float(nominal)
    return float(dn_mm)


def _size_esd_blowdown_section(
    path: str,
    piping_volume_m3: float,
    upstream_pressure_bar: float,
    upstream_temp_c: float,
    p_atm_bar: float,
    ambient_temp_c: float,
    depressurization_time_min: float,
    line_size_in: float,
    gas_density_kgm3: float,
    mw_g_mol: float,
    composition: Dict[str, Any],
    eos_model: str,
    allowable_dp_bar: float,
    valve_type: str,
    duty_count: int = 1,
) -> tuple[Optional[Dict[str, Any]], List[str]]:
    """Size an ESD / BDV depressurization valve bank from user piping volume & Design Tab atmospheric P/T.

    High-pressure section uses compressor outlet pressure (`p_out`) and `esd_hp_volume_m3`.
    Low-pressure section uses compressor inlet pressure (`p_in`) and `esd_lp_volume_m3`.
    """
    try:
        from kasp.integrations.control_valve.adapter import ControlValveAdapter

        duty = max(1, int(duty_count or 1))
        vol_m3 = max(0.5, float(piping_volume_m3))
        p_atm_val = max(0.35, float(p_atm_bar))
        p0_val = max(p_atm_val + 0.20, float(upstream_pressure_bar))
        tau_min = max(1.0, float(depressurization_time_min))
        tau_s = tau_min * 60.0

        # Target depressurization pressure tied to site atmospheric pressure (API 521 blowdown to atmospheric vent)
        p_target_bar = max(p_atm_val * 1.25, p_atm_val + 0.15)
        if p0_val <= p_target_bar:
            p_target_bar = 0.5 * (p0_val + p_atm_val)

        rho_0 = max(0.05, float(gas_density_kgm3))
        gas_inventory_kg = vol_m3 * rho_0
        log_ratio = math.log(max(1.02, p0_val / max(0.05, p_target_bar)))
        blowdown_mass_flow_total_kgs = max(0.005, (gas_inventory_kg / tau_s) * log_ratio)
        flow_per_valve = blowdown_mass_flow_total_kgs / duty

        # Effective mean BDV inlet gas temperature incorporating ambient wall heat transfer (API 521)
        t_bdv_eff_c = 0.65 * float(upstream_temp_c) + 0.35 * float(ambient_temp_c)
        line_dn_mm = max(25.0, float(line_size_in) * 25.4)

        res = ControlValveAdapter().calculate(
            {
                "service": "gas",
                "composition": composition,
                "eos_model": eos_model,
                "mass_flow_kgs": flow_per_valve,
                "p_in_bar": p0_val,
                "p_out_bar": p_atm_val,
                "t_c": max(-50.0, t_bdv_eff_c),
                "path": path,
            }
        )
        results = dict(res.get("results") or {})
        warnings = list(res.get("warnings", []) or [])
        calculated_dn = float(results.get("valve_dn_mm") or 0.0)
        calculated_size_in = round(calculated_dn / 25.4, 2) if calculated_dn > 0 else round(float(line_size_in), 2)
        selected_dn = _next_standard_dn(line_dn_mm)
        required_cv_per_valve = float(results.get("required_cv") or 0.0)
        required_cv_total = required_cv_per_valve * duty
        recommended_duty_count = max(1, math.ceil((calculated_dn * math.sqrt(duty)) / 400.0)) if calculated_dn > 0 else 1

        # Atmospheric vent tailpipe velocity at Design Tab (P_atm, T_amb)
        t_amb_k = max(180.0, min(500.0, float(ambient_temp_c) + 273.15))
        rho_atm = (p_atm_val * 1e5 * (max(2.0, float(mw_g_mol)) * 1e-3)) / (R_UNIVERSAL_J_MOL_K * t_amb_k)
        bdv_bore_m = max(0.025, (calculated_dn if calculated_dn > 0 else 100.0) / 1000.0)
        bdv_area_m2 = math.pi * (bdv_bore_m / 2.0) ** 2
        vent_exit_vel_ms = flow_per_valve / max(1e-6, rho_atm * bdv_area_m2)

        return (
            {
                "path": path,
                "valve_type": valve_type,
                "duty_count": duty,
                "piping_volume_m3": round(vol_m3, 2),
                "upstream_pressure_bar": round(p0_val, 2),
                "upstream_temp_c": round(float(upstream_temp_c), 1),
                "downstream_atm_pressure_bar": round(p_atm_val, 5),
                "ambient_temp_c": round(float(ambient_temp_c), 2),
                "effective_blowdown_temp_c": round(t_bdv_eff_c, 2),
                "depressurization_time_min": round(tau_min, 2),
                "gas_inventory_kg": round(gas_inventory_kg, 2),
                "blowdown_mass_flow_total_kgs": round(blowdown_mass_flow_total_kgs, 4),
                "flow_per_valve_kgs": round(flow_per_valve, 4),
                "line_size_in": round(float(line_size_in), 2),
                "line_dn_mm": round(line_dn_mm, 1),
                "allowable_dp_bar": round(float(allowable_dp_bar), 3),
                "required_cv": round(required_cv_per_valve, 4),
                "required_cv_total": round(required_cv_total, 4),
                "calculated_dn_mm": round(calculated_dn, 1) if calculated_dn > 0 else None,
                "calculated_size_in": calculated_size_in,
                "selected_dn_mm": round(selected_dn, 1),
                "selected_size_in": round(selected_dn / 25.4, 2),
                "vent_exit_velocity_ms": round(vent_exit_vel_ms, 2),
                "recommended_duty_count": recommended_duty_count,
                "opening_percent": results.get("opening_percent"),
                "is_choked": results.get("is_choked"),
                "standard": (res.get("provenance") or {}).get("standard"),
                "warnings": warnings,
            },
            warnings,
        )
    except BaseException as exc:
        return None, [f"{path} ESD/BDV vana boyutlandırma hatası: {exc}"]


def _size_mfs_cyclone_group(
    mass_flow_kgs: float,
    rho_in_kgm3: float,
    ambient_temp_c: float,
    user_cyclone_op: Any = None,
) -> Dict[str, Any]:
    """Dynamically size MFS multi-cyclone separators per PFD 4000, Özel §4.8.2, 5260 & 4500 §5.2."""
    if user_cyclone_op:
        try:
            cyclone_op_count = max(1, min(12, int(user_cyclone_op)))
            count_source = "user_input"
        except (TypeError, ValueError):
            cyclone_op_count = 2
            count_source = "station_3d_calc"
    else:
        # PFD 1-NGTL-0-CS-P-001-4000 & Özel Şartname §4.8.2: 3 units (2 duty + 1 standby, 50% each)
        cyclone_op_count = 2
        count_source = "station_3d_calc"

    cyclone_standby_count = 1
    cyclone_total_count = cyclone_op_count + cyclone_standby_count
    flow_per_cyclone = float(mass_flow_kgs) / cyclone_op_count
    unit_capacity_pct = round(100.0 / cyclone_op_count, 1)
    unit_design_capacity_kgs = round(flow_per_cyclone, 2)

    rho_safe = max(1.0, float(rho_in_kgm3))
    q_act_m3s = flow_per_cyclone / rho_safe

    # Vessel barrel ID sized from actual volumetric flux (always > 508 mm for ASME VIII > 20" manway)
    d_calc_mm = max(600.0, math.sqrt((4.0 * q_act_m3s) / (math.pi * 2.4)) * 1000.0)
    standard_barrels_mm = [600, 750, 900, 1050, 1200, 1350, 1500, 1650, 1800, 2000, 2200, 2400]
    vessel_diameter_mm = next((d for d in standard_barrels_mm if d >= d_calc_mm), int(math.ceil(d_calc_mm / 100.0) * 100))

    # Internal multi-cyclone elements (80 mm swirl tubes) sized to maintain clean ΔP <= 400 mbar
    a_tube_m2 = math.pi * (0.04 ** 2)
    v_tube_design = min(19.5, 14.0 / math.sqrt(max(8.0, rho_safe) / 25.0))
    q_tube_design = max(1e-4, a_tube_m2 * v_tube_design)
    raw_tubes = max(4, math.ceil(q_act_m3s / q_tube_design))
    # 80 mm cyclone tubes on 115 mm triangular pitch inside vessel up to 2400 mm max barrel (~220 tubes)
    internal_cyclone_elements = min(220, raw_tubes)
    v_tube_ms = q_act_m3s / (internal_cyclone_elements * a_tube_m2)

    # Euler clean ΔP loss (~12 dynamic heads across multi-cyclone bundle & nozzles)
    dp_cyclone_bar = round(max(0.05, min(0.85, 12.0 * 0.5 * rho_safe * (v_tube_ms ** 2) / 1e5)), 3)
    max_clean_dp_bar = 0.400
    dirty_alarm_dp_bar = 0.700

    # Spec 4500 §5.2 horizontal blow-flask directly below each MFS barrel
    bf_diam_mm = max(450, int(round((vessel_diameter_mm * 0.48) / 50.0) * 50))
    bf_len_mm = max(1400, int(round((bf_diam_mm * 3.0) / 100.0) * 100))
    bf_total_vol_m3 = round(math.pi * ((bf_diam_mm / 1000.0) / 2.0) ** 2 * (bf_len_mm / 1000.0), 3)
    bf_dump_vol_m3 = round(max(0.20, bf_total_vol_m3 * 0.55), 3)
    min_dump_tank_volume_m3 = round(max(3.0, 15.0 * bf_dump_vol_m3), 2)

    freeze_risk_active = bool(float(ambient_temp_c) < 2.0)
    warnings: List[str] = []
    if dp_cyclone_bar > max_clean_dp_bar:
        warnings.append(
            f"Temiz basınç kaybı ({dp_cyclone_bar:.3f} bar = {dp_cyclone_bar * 1000:.0f} mbar), "
            f"Spec 5260 sınırını (≤ 400 mbar) aşıyor; çalışan siklon sayısını artırın."
        )
    if freeze_risk_active:
        warnings.append(
            f"Ortam sıcaklığı ({float(ambient_temp_c):.1f} °C < 2 °C): Blow-flask ve yerüstü sıvı hatlarında "
            "≥ 2 °C elektrikli heat tracing & izolasyon zorunludur (Spec 4500 §5.2)."
        )

    return {
        "operating_count": cyclone_op_count,
        "standby_count": cyclone_standby_count,
        "installed_count": cyclone_total_count,
        "count_source": count_source,
        "unit_capacity_pct": unit_capacity_pct,
        "unit_design_capacity_kgs": unit_design_capacity_kgs,
        "flow_per_unit_kgs": round(flow_per_cyclone, 2),
        "actual_vol_flow_m3s_per_unit": round(q_act_m3s, 3),
        "pressure_drop_bar": dp_cyclone_bar,
        "clean_dp_mbar": round(dp_cyclone_bar * 1000.0, 1),
        "max_clean_dp_bar": max_clean_dp_bar,
        "dirty_alarm_dp_bar": dirty_alarm_dp_bar,
        "vessel_diameter_mm": vessel_diameter_mm,
        "internal_cyclone_elements": internal_cyclone_elements,
        "efficiency_8um_pct": 100.0,
        "efficiency_4um_pct": 90.0,
        "liquid_knockout_pct": 100.0,
        "corrosion_allowance_mm": 1.6,
        "head_type": "Spherical Fixed",
        "internal_bolts_material": "Stainless Steel",
        "design_code": "ASME BPVC Sec. VIII & IX",
        "has_manway": vessel_diameter_mm > 508,
        "blow_flask": {
            "orientation": "horizontal",
            "located_below_barrel": True,
            "diameter_mm": bf_diam_mm,
            "length_mm": bf_len_mm,
            "total_volume_m3": bf_total_vol_m3,
            "dump_volume_m3": bf_dump_vol_m3,
        },
        "level_instrumentation": {
            "bottles_count": 2,
            "online_isolatable": True,
            "instruments": ["LG (Seviye Göstergesi)", "LT (Seviye Transmiteri)", "LSH / LSL (Yüksek/Düşük Seviye Şalteri)", "PDI / PDT / PDSH"],
            "connection_note": "Seperatör–blow-flask nozulundan uzak ayrı üst/alt izolasyon vanalı 2 adet seviye şişesi",
        },
        "dump_system": {
            "auto_dump_header": "Ortak Otomatik Drenaj Headerı (blow-flask altı -> yalnızca sıvı)",
            "manual_dump_header": "Ortak Manuel Drenaj Headerı (seperatör/blow-flask bağlantısı hemen altı)",
            "atmospheric_cyclone_with_flame_arrestor": True,
            "inter_separator_purge_line": True,
            "min_dump_tank_volume_m3": min_dump_tank_volume_m3,
        },
        "heat_tracing": {
            "insulated": True,
            "electrical_traced": True,
            "min_temp_c": 2.0,
            "ambient_temp_c": round(float(ambient_temp_c), 1),
            "freeze_risk_active": freeze_risk_active,
        },
        "design_warnings": warnings,
    }


def _size_cfs_filter_group(
    mass_flow_kgs: float,
    rho_cfs_in_kgm3: float,
    ambient_temp_c: float,
    user_filter_op: Any = None,
) -> Dict[str, Any]:
    """Dynamically size CFS cartridge filter separators per PFD 4000, Ozel §4.8.2 & Spec 5210."""
    if user_filter_op:
        try:
            filter_op_count = max(1, min(12, int(user_filter_op)))
            count_source = "user_input"
        except (TypeError, ValueError):
            filter_op_count = 2
            count_source = "station_3d_calc"
    else:
        # PFD 1-NGTL-0-CS-P-001-4000 & Özel Şartname §4.8.2: 3 units (2 duty + 1 standby, 50% each)
        filter_op_count = 2
        count_source = "station_3d_calc"

    filter_standby_count = 1
    filter_total_count = filter_op_count + filter_standby_count
    flow_per_filter = float(mass_flow_kgs) / filter_op_count
    unit_capacity_pct = round(100.0 / filter_op_count, 1)
    unit_design_capacity_kgs = round(flow_per_filter, 2)

    rho_safe = max(1.0, float(rho_cfs_in_kgm3))
    q_act_m3s = flow_per_filter / rho_safe

    # Horizontal coalescing vessel ID & length sized dynamically from actual volumetric flow
    d_calc_mm = max(750.0, math.sqrt((4.0 * q_act_m3s) / (math.pi * 1.5)) * 1000.0)
    standard_barrels_mm = [750, 900, 1050, 1200, 1350, 1500, 1650, 1800, 2000, 2200, 2400, 2600]
    vessel_diameter_mm = next((d for d in standard_barrels_mm if d >= d_calc_mm), int(math.ceil(d_calc_mm / 100.0) * 100))
    vessel_length_mm = max(2800, int(round((vessel_diameter_mm * 3.5) / 100.0) * 100))

    # Cartridge elements sized dynamically so clean ΔP <= 140 mbar (Spec 5210 §4.3)
    q_cart_design = max(1e-4, 0.095 / math.sqrt(max(8.0, rho_safe) / 25.0))
    raw_cartridges = max(4, math.ceil(q_act_m3s / q_cart_design))
    cartridge_elements_count = min(220, raw_cartridges)
    loading_ratio = q_act_m3s / (cartridge_elements_count * q_cart_design)

    max_clean_dp_bar = 0.140
    dirty_changeout_dp_bar = 0.300
    element_burst_pressure_bar = 3.0
    dp_filter_bar = round(max(0.030, min(0.600, 0.105 * (loading_ratio ** 1.55))), 3)

    # Below-barrel horizontal Blow-Flask + heat tracing (Spec 5210 §4.1 & Özel §4.8.2)
    bf_diam_mm = max(450, int(round((vessel_diameter_mm * 0.42) / 50.0) * 50))
    bf_len_mm = max(1400, int(round((bf_diam_mm * 3.0) / 100.0) * 100))
    bf_total_vol_m3 = round(math.pi * ((bf_diam_mm / 1000.0) / 2.0) ** 2 * (bf_len_mm / 1000.0), 3)
    bf_dump_vol_m3 = round(max(0.20, bf_total_vol_m3 * 0.55), 3)

    freeze_risk_active = bool(float(ambient_temp_c) < 2.0)
    warnings: List[str] = []
    if dp_filter_bar > max_clean_dp_bar:
        warnings.append(
            f"Temiz filtre basınç kaybı ({dp_filter_bar:.3f} bar = {dp_filter_bar * 1000:.0f} mbar), "
            "Spec 5210 §4.3 sınırını (≤ 140 mbar) aşıyor; çalışan kartuş filtre sayısını artırın."
        )
    if freeze_risk_active:
        warnings.append(
            f"Ortam sıcaklığı ({float(ambient_temp_c):.1f} °C < 2 °C): CFS blow-flask ve enstrüman şişelerinde "
            "kendinden regüleli ≥ 2 °C elektrikli heat tracing & izolasyon aktif olmalıdır (Spec 5210 §4.1 / Özel §4.8.2)."
        )

    return {
        "operating_count": filter_op_count,
        "standby_count": filter_standby_count,
        "installed_count": filter_total_count,
        "count_source": count_source,
        "unit_capacity_pct": unit_capacity_pct,
        "unit_design_capacity_kgs": unit_design_capacity_kgs,
        "flow_per_unit_kgs": round(flow_per_filter, 2),
        "actual_vol_flow_m3s_per_unit": round(q_act_m3s, 3),
        "clean_dp_bar": dp_filter_bar,
        "clean_dp_mbar": round(dp_filter_bar * 1000.0, 1),
        "max_clean_dp_bar": max_clean_dp_bar,
        "dirty_changeout_dp_bar": dirty_changeout_dp_bar,
        "element_burst_pressure_bar": element_burst_pressure_bar,
        "efficiency_solid_3um_pct": 99.8,
        "efficiency_liquid_10um_pct": 99.8,
        "filter_efficiency_micron": "≥ 3 µm (%99.8 katı) · ≥ 10 µm (sıvı)",
        "vessel_diameter_mm": vessel_diameter_mm,
        "vessel_length_mm": vessel_length_mm,
        "cartridge_elements_count": cartridge_elements_count,
        "closure_type": "QOC (Quick Opening Closure) + Davit",
        "design_code": "ASME BPVC Sec. VIII Div. 1 & IX · CE",
        "hydro_test_factor": 1.5,
        "noise_limit": "ISO NR 80",
        "spare_sets_required": "3 set yedek filtre + 3 set QOC kapak contası",
        "blow_flask": {
            "orientation": "horizontal",
            "located_below_barrel": True,
            "diameter_mm": bf_diam_mm,
            "length_mm": bf_len_mm,
            "total_volume_m3": bf_total_vol_m3,
            "dump_volume_m3": bf_dump_vol_m3,
        },
        "instrumentation": {
            "differential_pressure": "PDT / PDI / PDSH (300 mbar değişim alarmı)",
            "level_controls": "LG / LT / LSH / LSL (enstrüman şişeleri) + LCV oto/man drenaj",
            "auxiliaries": "Restriction orifice + Vent (kör flanşlı) + Self-contained instrument gas",
        },
        "heat_tracing": {
            "insulated": True,
            "insulation_brackets_factory_installed": True,
            "electrical_traced": True,
            "self_regulating": True,
            "min_temp_c": 2.0,
            "ambient_temp_c": round(float(ambient_temp_c), 1),
            "freeze_risk_active": freeze_risk_active,
        },
        "design_warnings": warnings,
    }


def _size_compressor_auxiliaries(
    engine: ThermoEngine,
    gas_comp: Dict[str, float],
    comp_op_count: int,
    comp_total_count: int,
    flow_per_comp_kgs: float,
    power_per_unit_kw: float,
    total_power_kw: float,
    polytropic_eff_pct: float,
    mech_eff_pct: float,
    thermal_eff_pct: float,
    p_in_bar: float,
    p_out_bar: float,
    ambient_temp_c: float,
) -> Dict[str, Any]:
    """Size turbo-compressor unit auxiliaries per Spec 4500 §5.5-5.8, §6.x, §8.x & Ozel §4.8, §6.1."""
    warnings: List[str] = []

    # 1. Overhead crane scaled realistically to GT + API 617 compressor casing/bundle lift
    if power_per_unit_kw > 25000.0:
        crane_tons = 35.0
    elif power_per_unit_kw > 15000.0:
        crane_tons = 25.0
    elif power_per_unit_kw > 8000.0:
        crane_tons = 20.0
    else:
        crane_tons = 15.0

    # 2. ISO 6976:2016 real fuel gas thermodynamics & Spec 4500 §8.1-8.5 / Ozel §4.8.5 conditioning
    try:
        fuel_props = engine.calculate_fuel_gas_properties(gas_comp, source="iso6976") or {}
    except Exception:
        fuel_props = {}

    lhv_kj_kg = float(fuel_props.get("lhv_kj_kg") or 0.0)
    hhv_kj_kg = float(fuel_props.get("hhv_kj_kg") or 0.0)
    std_rho_kg_sm3 = float(fuel_props.get("standard_density_kg_sm3") or 0.772)
    wobbe_mj_sm3 = float(fuel_props.get("wobbe_index_mj_sm3") or 0.0)
    therm_frac = max(0.15, min(0.65, float(thermal_eff_pct) / 100.0))
    heat_rate_kj_kwh = round(3600.0 / therm_frac, 1)

    if lhv_kj_kg > 100.0:
        fuel_per_unit_kgh = round((power_per_unit_kw * heat_rate_kj_kwh) / lhv_kj_kg, 1)
        fuel_per_unit_sm3h = round(fuel_per_unit_kgh / max(0.05, std_rho_kg_sm3), 1)
    else:
        fuel_per_unit_kgh = 0.0
        fuel_per_unit_sm3h = 0.0
        warnings.append(
            "Yakıt gazı alt ısıl değeri (ISO 6976 LHV ≤ 100 kJ/kg) yetersiz/inert gaz; "
            "türbin yakıt debisi sıfırlandı (0 kg/h)."
        )

    total_fuel_kgh = round(fuel_per_unit_kgh * comp_op_count, 1)
    total_fuel_sm3h = round(fuel_per_unit_sm3h * comp_op_count, 1)
    design_fuel_per_unit_kgh = round(fuel_per_unit_kgh * 1.20, 1)
    design_total_fuel_kgh = round(total_fuel_kgh * 1.20, 1)

    # 3. Lube oil system sizing via physical shaft mechanical + GT bearing rejection heat balance (4500 §6.7)
    mech_loss_frac = max(0.005, 1.0 - max(50.0, min(99.5, float(mech_eff_pct))) / 100.0)
    bearing_heat_kw = power_per_unit_kw * mech_loss_frac + max(45.0, 0.012 * power_per_unit_kw)
    oil_cp_kj_kgk = 2.0
    oil_delta_t_k = 18.0
    oil_rho_kg_m3 = 870.0
    oil_mass_kgs = bearing_heat_kw / (oil_cp_kj_kgk * oil_delta_t_k)
    flow_lpm_per_unit = round(max(60.0, (oil_mass_kgs / oil_rho_kg_m3) * 60000.0), 1)
    min_working_vol_l = round(flow_lpm_per_unit * 5.0, 1)
    min_surface_area_cm2 = round(flow_lpm_per_unit * 51.0, 1)

    # 4. Operating envelope checks (Ozel §4.8 p.20 high suction overload & choke; §6.1.2 >= 85% poly eff)
    if p_in_bar >= 65.0:
        warnings.append(
            f"Yüksek Emiş Basıncı ({p_in_bar:.1f} bar ≥ 65 bar — Özel §4.8): Start-up overload torku "
            f"(%120 VFD elektrik marş motoru), yüksek debi (choke) sınırı ve DGS diferansiyel basınç "
            f"kararlılığı üretici haritasında doğrulanmalıdır."
        )
    if polytropic_eff_pct < 85.0:
        warnings.append(
            f"Kompresör politropik verimi (%{polytropic_eff_pct:.1f}), Özel §6.1.2 nominal işletme noktası "
            f"hedefi olan ≥ %85.0 değerinin altındadır."
        )
    if float(ambient_temp_c) < 2.0:
        warnings.append(
            f"Ortam sıcaklığı ({ambient_temp_c:.1f} °C < 2 °C): Yakıt gazı seperatörü blow-flask ve "
            f"regülatör pilot hatlarında ≥ 2 °C ısıtma (heat tracing) devrede olmalıdır (Spec 4500 §8.3 / Özel §4.8.5)."
        )

    return {
        "crane_capacity_tons": crane_tons,
        "unit_valves_and_strainer": {
            "suction_series_valves_count": 2,
            "discharge_series_valves_count": 2,
            "valve_type": "Tam Geçişli Ayrık Gövdeli Küresel Vana (Seri Çift Blok & Bleed · Spec 4500 §5.5)",
            "motor_actuator_stroke_max_s": 30.0,
            "manual_isolation_valve_series": True,
            "body_bleed_piped_to_purge": True,
            "fail_mode_signal_loss": "Fail-Close (Kontrol Sinyali Kaybında Kapanır)",
            "fail_mode_mcc_loss": "Last Position (MCC Güç Kaybında Son Konum)",
            "switches": "Open/Close Limit Switch + Torque Switch (Lokal MCC + Uzak SCADA)",
            "temporary_startup_strainer": True,
            "temporary_strainer_type": "Geçici Konik Devreye Alma Strainer (Flanşlar Arası + Çıkarılabilir Spacer)",
            "reducers_adjacent_to_nozzles": True,
            "discharge_non_slam_check_valve": True,
            "discharge_check_valve_type": "Flanşlı Nozzle Tip Non-Slam Çek Vana (Spec 4500 §5.7)",
            "asv_downstream_check_and_shutoff": True,
            "purge_volume_changes": 7,
            "purge_min_time_s": 15.0,
            "pressurize_window_s": "30-60",
            "vent_max_time_s": 60.0,
            "vent_silencer_condensate_pit": True,
        },
        "dry_gas_seal": {
            "standard": "API 692 Tandem Çift Yönlü Kuru Gaz Salmastrası (Dry Gas Seal)",
            "filtration_rating_um": 1.0,
            "duplex_redundant": True,
            "filter_config": "1 Aktif + 1 Yedek (Duplex 1 µm Kartuş Filtre)",
            "control_mode": "Fark Basınç Kontrollü Regülatör (PDCV — Sabit Orifis Kontrolü Yok)",
            "seal_gas_heater_included": True,
            "separation_seal": "Karbon Ringli Min. Hava Tüketimli Separation (Buffer) Seal",
            "vent_test_tee_with_blind": True,
            "spare_sets_required": "2 set yedek DGS filtresi + 1 adet sandıklı yedek çift yönlü DGS kartuşu + montaj/demontaj toolları",
        },
        "fuel_gas_system": {
            "takeoff_location": "Ana CFS Kartuş Filtre Çıkışı Sonrası / Gaz Soğutucu Girişi Öncesi (Özel §4.8.5 · P&ID 4005)",
            "takeoff_downstream_of_main_filters": True,
            "takeoff_upstream_of_gas_cooler": True,
            "thermal_efficiency_pct": round(therm_frac * 100.0, 2),
            "heat_rate_kj_kwh": heat_rate_kj_kwh,
            "lhv_kj_kg": round(lhv_kj_kg, 1),
            "hhv_kj_kg": round(hhv_kj_kg, 1),
            "standard_density_kg_sm3": round(std_rho_kg_sm3, 4),
            "wobbe_index_mj_sm3": round(wobbe_mj_sm3, 2),
            "fuel_per_unit_kgh": fuel_per_unit_kgh,
            "fuel_per_unit_sm3h": fuel_per_unit_sm3h,
            "total_fuel_kgh": total_fuel_kgh,
            "total_fuel_sm3h": total_fuel_sm3h,
            "design_factor_pct": 120.0,
            "design_fuel_per_unit_kgh": design_fuel_per_unit_kgh,
            "design_total_fuel_kgh": design_total_fuel_kgh,
            "separator_filtration_um": 1.0,
            "separator_efficiency_pct": 99.8,
            "separator_heat_tracing_min_c": 2.0,
            "heat_exchanger_redundancy": "1+1 (%100 + %100) Gaz/Glikol Eşanjör + Tüp Patlama PSV",
            "heat_exchanger_outlet_c": "20 °C (±5 °C)",
            "regulator_config": "2×100% Paralel Regülatör + Kısıtlayıcı Orifis + Isıtmalı Pilot (≥ 2 °C) + PSV (%110) + 40 Mesh Y-Strainer",
            "metering_type": "P/T Kompanzasyonlu Rotary / Türbin Sayaç + Konik Start-Up Screen",
            "pipe_material": "316 Paslanmaz Çelik (Yeraltı Kaplamalı + Katodik Korumalı)",
            "spare_sets_required": "2 set yedek yakıt gazı filtresi / istasyon",
        },
        "lube_oil_system": {
            "oil_type": "Ortak Mineral Yağlama Yağı (GG + Güç Türbini + API 617 Kompresör)",
            "flow_lpm_per_unit": flow_lpm_per_unit,
            "bearing_heat_rejection_kw": round(bearing_heat_kw, 1),
            "reservoir_min_retention_min": 5.0,
            "reservoir_min_working_volume_l": min_working_vol_l,
            "reservoir_min_surface_area_cm2": min_surface_area_cm2,
            "reservoir_surface_rule": "≥ 51 cm² / (L/min) (Spec 4500 §6.7)",
            "reservoir_heaters_thermostatic": True,
            "oil_demister_ups_backed": True,
            "filter_nominal_um": 10.0,
            "duplex_online_replaceable": True,
            "cold_oil_dp_design_temp_c": 20.0,
            "pumps": "Şaft/Ana AC Pompa + Yardımcı Ex-Proof AC Pompa + Acil DC/UPS Pompa + Bekleme Sirkülasyon",
            "ups_dc_emergency_pump": True,
            "aerial_cooler_fans": 2,
            "aerial_cooler_3way_bypass": True,
            "aerial_cooler_desc": "Bina Dışı Hava Soğutucu (2× Elektrik Motorlu Fan + 3 Yollu Termostatik Baypas)",
            "piping_material": "Paslanmaz Çelik Borulama + Alüminyum İzolasyon Kaplaması",
            "magnetic_chip_detectors": True,
            "spare_sets_required": "2 set yedek yağ filtresi + 2 set oil demister filtresi",
        },
        "air_intake_and_enclosure": {
            "driver_type": "Endüstriyel Ağır Hizmet Gaz Türbini (Aero-türev Hariç · Spec 4500 §6.1)",
            "compressor_type": "API 617 Santrifüj Kompresör (≥ 3.2 mm CA, 70–105% Sürekli Hız)",
            "starter_system": "Ex-Proof 380V VFD Elektrik Motorlu Soft-Starter (%120 Tork, Gazlı Başlatma Yok)",
            "air_intake_filter_type": "Kendini Temizleyen Ters Darbeli (Self-Cleaning) Filtre + Absorptif Susturucu + 316 SS Kanal",
            "air_intake_clean_dp_max_mbar": 8.0,
            "air_intake_dirty_dp_mbar": 7.5,
            "air_intake_fuel_calc_dp_mbar": 10.0,
            "air_intake_trip_dp_mbar": 12.5,
            "air_intake_collapse_dp_mbar": 37.5,
            "exhaust_max_dp_mbar": 10.0,
            "exhaust_max_surface_temp_c": 55.0,
            "enclosure_noise_limit": "≤ ISO NR 80 / 85 dBA @ 1m",
            "enclosure_max_temp_c": 80.0,
            "enclosure_ventilation_ups": True,
            "fire_and_gas": "%10 LEL Alarm / %20 LEL Trip + Alev/Isı Dedektörleri + Otomatik CO₂/İnert Söndürme",
            "spare_intake_sets_per_unit": 1,
        },
        "design_warnings": warnings,
    }


def _estimate_cooler_bundle_and_specs(
    mass_flow_kgs: float,
    cooler_bays_count: int,
    p_out_bar: float,
    t_inlet_c: float,
    t_outlet_c: float,
    cooler_air_temp_c: float,
    heat_duty_mw: float,
    rho_gas_kgm3: float,
    mu_gas_pas: float,
) -> Dict[str, Any]:
    """Compute Fin-Fan tube-bundle gas ΔP (Darcy-Haaland) and Spec 5234 / 4500 §5.14 / Özel §4.8.4 data."""
    bays = max(2, int(cooler_bays_count))
    flow_per_bay = max(0.1, float(mass_flow_kgs) / bays)
    rho_safe = max(1.0, float(rho_gas_kgm3))
    mu_safe = max(5e-6, float(mu_gas_pas))

    # Spec 5234 App. D / API 661 standard finned tube geometry (1" OD = 25.4 mm, 12 BWG = 2.77 mm wall)
    tube_od_m = 0.0254
    tube_wall_m = 0.00277
    tube_id_m = tube_od_m - 2.0 * tube_wall_m  # 19.86 mm ID
    tube_rows = 4
    tube_passes = 2
    tube_length_m = 6.0
    path_length_m = tube_length_m * tube_passes

    # Size parallel tubes per row per bay so gas inside-tube velocity stays near ~8-14 m/s
    q_bay_m3s = flow_per_bay / rho_safe
    target_v_ms = 10.5
    area_one_tube_m2 = math.pi * (tube_id_m ** 2) / 4.0
    tubes_per_pass_per_bay = max(24, min(480, math.ceil(q_bay_m3s / (target_v_ms * area_one_tube_m2))))
    total_tubes_per_bay = tubes_per_pass_per_bay * tube_passes
    tubes_per_row = max(12, math.ceil(total_tubes_per_bay / tube_rows))
    tubes_per_pass_actual = max(12, (tubes_per_row * tube_rows) // tube_passes)

    flow_area_m2 = tubes_per_pass_actual * area_one_tube_m2
    tube_velocity_ms = q_bay_m3s / max(1e-6, flow_area_m2)
    reynolds = (rho_safe * tube_velocity_ms * tube_id_m) / mu_safe
    rel_roughness = 0.000045 / tube_id_m
    if reynolds > 2300.0:
        inv_sqrt_f = -1.8 * math.log10((rel_roughness / 3.7) ** 1.11 + (6.9 / reynolds))
        f_darcy = 1.0 / max(1e-6, inv_sqrt_f ** 2)
    else:
        f_darcy = 64.0 / max(100.0, reynolds)

    k_header_return = 2.8  # nozzle entrance + U-turn pass bend + outlet box exit
    dp_pa = (f_darcy * (path_length_m / tube_id_m) + k_header_return) * 0.5 * rho_safe * (tube_velocity_ms ** 2)
    dp_cooler_bar = round(max(0.05, min(0.85, dp_pa / 1e5)), 3)
    allowable_dp_bar = 0.50

    warnings: List[str] = []
    if float(cooler_air_temp_c) > 40.0:
        warnings.append(
            f"Soğutma havası giriş sıcaklığı ({float(cooler_air_temp_c):.1f} °C), Spec 4500 §5.14 / Özel §4.8.4 "
            "azami referans ortam sınırı olan 40.0 °C değerini aşıyor."
        )
    if float(t_outlet_c) > 45.0:
        warnings.append(
            f"Gaz soğutucu çıkış sıcaklığı ({float(t_outlet_c):.1f} °C), Spec 4500 §5.14 / Özel §4.8.4 "
            "azami tasarım çıkış sınırı olan 45.0 °C üzerinde."
        )
    if dp_cooler_bar > allowable_dp_bar:
        warnings.append(
            f"Fin-Fan gaz tarafı basınç kaybı ({dp_cooler_bar:.3f} bar), Spec 5234 / API 661 "
            f"tavsiye edilen {allowable_dp_bar:.2f} bar sınırını aşıyor; paralel bay sayısını artırın."
        )

    return {
        "dp_cooler_bar": dp_cooler_bar,
        "allowable_dp_bar": allowable_dp_bar,
        "tube_velocity_ms": round(tube_velocity_ms, 2),
        "reynolds": round(reynolds, 0),
        "tubes_per_row": tubes_per_row,
        "tubes_per_bay": tubes_per_row * tube_rows,
        "tube_passes": tube_passes,
        "tube_length_m": tube_length_m,
        "tube_wall_bwg": "12 BWG",
        "nozzle_rating": "ANSI Class 600 RF",
        "draft_type": "Forced-Draft (API 661 / Spec 5234 §1.1.1)",
        "fan_blades_min": 4,
        "max_fan_tip_speed_ms": 50.0,
        "fan_motor_max_kw": 29.8,
        "noise_limit_150m_dba": 55.0,
        "design_reference_ambient_c": 40.0,
        "max_design_gas_outlet_c": 45.0,
        "vfd_drive_spec": "VFD (0–100% Hız · IEEE 519 Harmonik · ≥%95 Verim · Soft-Start + Baypaslı · Lokal & SCS 4–20 mA)",
        "vibration_switches": "Her fan motorunda Murphy tipi titreşim anahtarı (SCADA alarm + oto-stop · ≤2000 mm reset)",
        "louver_and_sunshade": "2.0 mm ekstrüde alüminyum manuel kumandalı panjurlu güneşlik (Özel §4.8.4 / Spec 5234 §5.2.15)",
        "isolation_and_drain": "Her bay giriş/çıkış kilitlenebilir manuel izolasyon vanası + 1\" vent/drenaj · 10 mm/m eğim (4500 §5.14)",
        "tcv_control_spec": "Termostatik ON/OFF Baypas · Gas-over-Oil Hidrolik Aktüatör · Sinyal Kaybında Fail-Open (4500 §5.14)",
        "warnings": warnings,
    }


def _size_station_utilities_and_relief(
    p_out_bar: float,
    p_in_bar: float,
    p_atm_bar: float,
    ambient_temp_c: float,
    cooler_inlet_temp_c: float,
    cooler_outlet_temp_c: float,
    mass_flow_kgs: float,
    comp_total_count: int,
    cooler_bays_count: int,
    bdv_depressurization_time_min: float,
    ultrasonic_meter_sizing: Dict[str, Any],
) -> Dict[str, Any]:
    """Size Station Utilities (§7 Power Gas, §9/Özel §4.8.6 Utility Gas, §10/Özel §4.8.7 Compressed Air, §11 Heating, §5.9-5.13)."""
    p_maop_g = max(75.0, float(p_out_bar) - float(p_atm_bar))
    pg_design_bar = round(p_maop_g * 1.10, 2)
    # Hammerschmidt hydrate suppression deltaT = 1297 * W / (M_MeOH * (100 - W)); target >= 10 °C margin
    methanol_wt_pct = 28.0 if float(ambient_temp_c) < 0.0 else 22.0
    hammerschmidt_dt_c = round((1297.0 * methanol_wt_pct) / (32.04 * (100.0 - methanol_wt_pct)), 2)

    # Utility Gas (§9 & Özel §4.8.6): Gas Cooler inlet takeoff, min 1485 Sm3/h design skid
    boiler_demand_sm3h = (55.0 + max(0.0, 20.0 - float(ambient_temp_c)) * 3.8 + comp_total_count * 18.0)
    preheater_demand_sm3h = max(120.0, float(mass_flow_kgs) * 0.45)
    calculated_util_demand_sm3h = round(max(1485.0, boiler_demand_sm3h + preheater_demand_sm3h + 1250.0), 1)
    psv_util_set_bar = round(max(12.0, p_maop_g * 0.16 * 1.10), 2)

    # Compressed Air (§10.1-10.4, Spec 4320/4330, Özel §4.8.7): usage factors + losses + 15% dryer + 10% overdesign
    base_inst_nm3h = (comp_total_count * 42.0) + (cooler_bays_count * 12.0) + 85.0
    continuous_nm3h = base_inst_nm3h * 1.00
    intermittent_nm3h = (base_inst_nm3h * 0.35) * 0.50
    emergency_nm3h = 30.0 * 0.10
    maint_nm3h = 45.0 * 0.05
    air_subtotal = continuous_nm3h + intermittent_nm3h + emergency_nm3h + maint_nm3h
    air_demand_nm3h = round(air_subtotal * 1.10 * 1.15 * 1.10, 1)  # +10% loss, +15% dryer regen, +10% margin
    # Receiver >= 25 m3 AND >= 10 min holdup without compressors (Özel §4.8.7 vs Spec 4500 1.0 m3)
    holdup_min_vol_m3 = (air_demand_nm3h / 60.0) * 10.0 / 6.5 * 1.2
    receiver_volume_m3 = round(max(25.0, holdup_min_vol_m3), 1)
    holdup_time_min = round((receiver_volume_m3 * 6.5 / 1.2) / max(0.1, air_demand_nm3h / 60.0), 1)

    # Heating System (§11.0): 90/70 °C 50/50 ethylene glycol-water, 2x70% boilers, 3x50% pumps
    winter_dt = max(5.0, 22.0 - float(ambient_temp_c))
    heat_load_kw = round(240.0 + winter_dt * 12.5 + comp_total_count * 65.0, 1)

    esd_60s_compliant = float(bdv_depressurization_time_min) <= 1.0
    warnings: List[str] = []
    if not esd_60s_compliant:
        warnings.append(
            f"Spec 4500 §5.11: İstasyon ESD blowdown vanası 1 barg basınca ≤ 60 s (1.0 dk) sürede düşürmelidir "
            f"(mevcut boşaltma süresi: {float(bdv_depressurization_time_min):.1f} dk API 521 modu)."
        )

    return {
        "power_gas": {
            "design_pressure_bar": pg_design_bar,
            "takeoff": "Ana hat çift blok vana baypas hattından çekvalfli çift bağlantı (4500 §7.1)",
            "methanol_dehydrator": {
                "included": True,
                "wt_pct": methanol_wt_pct,
                "hammerschmidt_depression_c": hammerschmidt_dt_c,
                "valving": "İzolasyon + baypas + memba çekvalf + cam seviye göstergesi + vent/drenaj (4500 §7.2)",
            },
            "distribution_piping": "1\" düşüş + F×F küresel vana + partikül filtresi + 1/2\" paslanmaz tubing → Gas-over-Oil aktüatörler",
        },
        "utility_gas": {
            "takeoff_location": "Gas Cooler Girişi (Özel §4.8.6) · Alternatif HP Hat (4500 §9.1)",
            "min_skid_capacity_sm3h": 1485.0,
            "calculated_demand_sm3h": calculated_util_demand_sm3h,
            "odorizer_included": True,
            "electric_heater_external_mcc": True,
            "preheat_dewpoint_margin_c": 12.0,
            "preheating": "Double-pipe eşanjör + harici MCC hücre beslemeli elektrikli ısıtıcı (≥ +10 °C çiy noktası marjı) + kokulandırma",
            "pressure_reduction": f"Çok kademeli regülasyon: 2×%100 paralel PRV + %110 PSV ({psv_util_set_bar} bar g) + ısıtmalı pilot hatlar",
            "metering": "Türbin / AGA-3 Orifis Sayaç + Hacim Düzeltici",
            "underground_distribution_material": "Yeraltı PE borulama (Binalar & Jeneratör besleme)",
        },
        "compressed_air": {
            "demand_nm3h": air_demand_nm3h,
            "compressor_configuration": "1+1 (%100 her biri) Yağsız Vidalı VFD · Eş-Yaşlandırma (Equal Aging) + Entegre Aftercooler + Vibrasyon Hortumu",
            "dryers": "1+1 (%100) Çift Kuleli Isısız Rejeneratif Desikant Kurutucu (Spec 4330 · 8.7/10.5 barg · Amicon)",
            "dewpoint_c": -40.0,
            "high_dewpoint_alarm_c": -20.0,
            "receiver_tank_spec": "Spec 4320 / Özel §4.8.7 ASME VIII Div 1 & CE Dik Tip Hava Tankı (10.35 bar g)",
            "receiver_volume_m3": receiver_volume_m3,
            "holdup_time_min": holdup_time_min,
            "piping_material": "≥ 304 Paslanmaz Çelik (Özel §4.8.7 · Yeraltı kaplamalı & Katodik Korumalı · 316 SS enstrüman tubing)",
        },
        "heating_glycol": {
            "medium": "90/70 °C (%50/%50 Etilen Glikol - Su)",
            "heat_load_kw": heat_load_kw,
            "boilers": "2 × %70 Kapasiteli Çok Geçişli Gaz Kazanı",
            "pumps": "3 × %50 İnline Sirkülasyon Pompası + Diyaframlı Genleşme Tankı",
        },
        "fire_water": {
            "tank_volume_m3": 300.0,
            "pumps": "NFPA 20: 1 Elektrikli + 1 Dizel Ana Yangın Pompası + 1 Jockey Pompası",
            "ring_main_hydrants": "Çevre Ring Hidrant Ağı + Bina İçi F&G (%20 LEL IR / UV-IR Alev Algılama)",
            "turbine_enclosure_suppression": "Otomatik CO2 / Temiz Gaz Söndürme Sistemi (4500 §14)",
        },
        "hvac": {
            "control_building": "Pozitif Basınçlı Ex-Proof HVAC İklimlendirme (4500 §12-13)",
            "compressor_building": "UPS Destekli Mekanik Havalandırma (≤ 80 °C Termal Sınır)",
        },
        "safety_and_bypass": {
            "usm_4500": {
                "tag": (ultrasonic_meter_sizing or {}).get("tag", "FT-401"),
                "paths_min": 4,
                "installed_paths": 8,
                "accuracy_pct": 0.5,
                "repeatability_pct": 0.1,
                "flanged_dry_calibrated": True,
                "zanker_conditioner_optional": True,
            },
            "psv_4500": {
                "min_distance_from_buildings_m": 35.0,
                "choke_flow_sized": True,
                "dual_outlet_flanged": True,
                "pilot_size_in": 2.0,
                "upstream_ball_valve_and_snubber": True,
                "field_test_connection": True,
            },
            "bdv_4500": {
                "min_distance_from_buildings_m": 35.0,
                "target_pressure_barg": 1.0,
                "max_blowdown_time_s": 60.0,
                "user_configured_time_min": round(float(bdv_depressurization_time_min), 2),
                "esd_60s_compliant": esd_60s_compliant,
                "valve_type": "Yağlamalı Flanşlı Plug Vana · Gas-over-Oil (1 sn/inç · Fail-Open · Manuel Reset)",
            },
            "loading_line": "4500 §5.12: Ünite Suction MOV baypası (küresel + pozisyon switch'li globe vana)",
            "station_bypass_check": "4500 §5.13: Ana hat çapında Suction–Discharge Non-Slam Piston/Nozul Çekvalf (Soğutucu sonrası, USM öncesi)",
        },
        "warnings": warnings,
    }


def calculate_station_process_model(
    inputs: Dict[str, Any],
    design_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculates comprehensive compressor station layout, sizing metrics, and nodal states.

    Args:
        inputs: Design inputs dict containing flow, p_in, p_out, t_in, gas_comp, etc.
        design_results: Optional design calculation results from calculation_service.

    Returns:
        Structured dictionary with station summary, dynamic equipment counts,
        nodal process states, and animated pipe flow velocity vectors.
    """
    # 0. Resolve Site Atmospheric Pressure & Ambient Temperature from Design Tab FIRST
    site_ambient = _resolve_site_ambient(inputs, design_results)
    p_atm_bar = site_ambient["p_atm_bar"]
    ambient_pressure_kpa = site_ambient["ambient_pressure_kpa"]
    ambient_temp_c = site_ambient["ambient_temp_c"]
    altitude_m = site_ambient["altitude_m"]

    # 0b. Parse Gas Composition, Molecular Weight, and Selected EOS
    raw_gas_comp = inputs.get("gas_comp")
    gas_comp: Dict[str, float] = {}
    if isinstance(raw_gas_comp, dict) and raw_gas_comp:
        for k, v in raw_gas_comp.items():
            try:
                fv = float(v)
                if math.isfinite(fv) and fv > 0:
                    gas_comp[k] = fv
            except (TypeError, ValueError):
                continue
    if not gas_comp:
        gas_comp = {"METHANE": 95.0, "ETHANE": 3.0, "NITROGEN": 2.0}

    norm_comp: Dict[str, float] = {}
    tot_mol = sum(gas_comp.values()) or 1.0
    for k, v in gas_comp.items():
        canon_k = normalize_component(k)
        norm_comp[canon_k] = norm_comp.get(canon_k, 0.0) + (v / tot_mol)

    mw = sum(norm_comp.get(g, 0.0) * MOLAR_MASSES.get(g, 16.04) for g in norm_comp)
    if not math.isfinite(mw) or mw <= 0.0:
        mw = 18.2

    eos_key = _normalize_station_eos(
        inputs.get("eos_model") or inputs.get("eos_method") or (design_results or {}).get("eos_method") or "pr"
    )
    engine = ThermoEngine()
    solver = engine.thermo_solver
    try:
        gas_obj = engine._create_gas_object(gas_comp, eos_key)
    except Exception:
        try:
            eos_key = "pr"
            gas_obj = GasMixtureBuilder.build_thermo_data(
                GasMixtureBuilder.validate_and_normalize(gas_comp)
            )
        except Exception:
            gas_obj = None

    # 1. Parse Baseline Process Inputs & Convert Volumetric/Molar Flow via Real EOS / MW
    raw_mass_flow = inputs.get("mass_flow")
    if raw_mass_flow is not None and str(raw_mass_flow).strip() != "":
        try:
            mass_flow_kgs = float(raw_mass_flow)
        except (TypeError, ValueError):
            mass_flow_kgs = 50.0
    else:
        try:
            raw_flow = float(inputs.get("flow", 50.0) or 50.0)
        except (TypeError, ValueError):
            raw_flow = 50.0
        canon_unit = _canonical_flow_unit(inputs.get("flow_unit", "kg/s"))
        if not math.isfinite(raw_flow) or raw_flow <= 0:
            mass_flow_kgs = 50.0
        elif canon_unit == "kg/s":
            mass_flow_kgs = raw_flow
        elif canon_unit == "kg/h":
            mass_flow_kgs = raw_flow / 3600.0
        elif canon_unit == "m³/h":
            mass_flow_kgs = _actual_m3h_to_kgs(raw_flow, inputs, engine, gas_obj, eos_key, mw, p_atm_bar=p_atm_bar)
        elif gas_obj is not None and canon_unit in ("Sm³/h", "Nm³/h", "MMSCFD", "MMSCMD", "kmol/h"):
            try:
                mass_flow_kgs = engine.convert_flow_to_kgs(raw_flow, canon_unit, gas_obj, eos_key)
            except Exception:
                mass_flow_kgs = _fallback_convert_flow_with_mw(raw_flow, canon_unit, mw)
        else:
            mass_flow_kgs = _fallback_convert_flow_with_mw(raw_flow, canon_unit, mw)

    if not math.isfinite(mass_flow_kgs) or mass_flow_kgs <= 0:
        mass_flow_kgs = 50.0
    else:
        mass_flow_kgs = max(0.5, mass_flow_kgs)

    # Pressures in bar(a) — gauge units respect site atmospheric pressure from Design Tab
    p_in_unit = str(inputs.get("p_in_unit", "bar(a)"))
    p_out_unit = str(inputs.get("p_out_unit", "bar(a)"))
    try:
        raw_p_in = float(inputs.get("p_in", 25.0) or 25.0)
    except (TypeError, ValueError):
        raw_p_in = 25.0
    try:
        raw_p_out = float(inputs.get("p_out", 75.0) or 75.0)
    except (TypeError, ValueError):
        raw_p_out = 75.0

    p_in = _pressure_to_bar_a(raw_p_in, p_in_unit, p_atm_bar)
    p_out = _pressure_to_bar_a(raw_p_out, p_out_unit, p_atm_bar)

    if not math.isfinite(p_in) or p_in < 0.5:
        p_in = 0.5

    # Ensure pressure ratio >= 1.05
    if not math.isfinite(p_out) or p_out <= p_in * 1.02:
        p_out = p_in * 2.5

    # Temperature in °C (supports °C / K / °F inputs from the UI)
    try:
        raw_t_in = float(inputs.get("t_in", 20.0) or 20.0)
    except (TypeError, ValueError):
        raw_t_in = 20.0

    try:
        t_in = UnitSystem.convert_temperature(
            raw_t_in,
            str(inputs.get("t_in_unit", "°C")),
            "°C",
        )
    except Exception:
        t_in = raw_t_in
    if not math.isfinite(t_in):
        t_in = 20.0
    t_in = max(-100.0, min(250.0, t_in))

    R_gas = R_UNIVERSAL_J_MOL_K / (mw * 1e-3)  # J/(kg*K)
    T_in_K = t_in + 273.15

    def _safe_eos_state(p_bar_val: float, t_c_val: float):
        if gas_obj is None:
            return None
        try:
            p_pa = max(0.5e5, float(p_bar_val) * 1e5)
            t_k = max(120.0, min(800.0, float(t_c_val) + 273.15))
            return solver.get_properties(p_pa, t_k, gas_obj, eos_key)
        except Exception:
            return None

    inlet_state = _safe_eos_state(p_in, t_in)
    std_state = _safe_eos_state(1.01325, 15.0)

    if std_state is not None and std_state.density and math.isfinite(std_state.density) and std_state.density > 0:
        rho_std = float(std_state.density)
    else:
        rho_std = 1.01325e5 / (R_gas * 288.15)
    vol_flow_mmscmd = (mass_flow_kgs * 86400.0) / (rho_std * 1e6)

    # 2. Dynamic MFS Cyclone Separator Sizing (PFD 4000 2+1 %50, Spec 5260 & 4500 §5.2)
    rho_mfs_in = (
        float(inlet_state.density)
        if (inlet_state is not None and inlet_state.density and math.isfinite(inlet_state.density) and inlet_state.density > 0)
        else max(0.05, (p_in * 1e5) / (R_gas * max(120.0, T_in_K)))
    )
    user_cyclone_op = inputs.get("cyclone_op_count") or inputs.get("cyclones_count")
    mfs_sizing = _size_mfs_cyclone_group(mass_flow_kgs, rho_mfs_in, ambient_temp_c, user_cyclone_op)
    cyclone_op_count = mfs_sizing["operating_count"]
    cyclone_total_count = mfs_sizing["installed_count"]
    flow_per_cyclone = mfs_sizing["flow_per_unit_kgs"]
    dp_cyclone = mfs_sizing["pressure_drop_bar"]
    p_post_cyclone = round(max(0.5, p_in - dp_cyclone), 2)

    # 3. Dynamic CFS Cartridge Coalescing Filter Sizing (PFD 4000 2+1 %50, Spec 5210 & Özel §4.8.2)
    rho_cfs_in = max(1.0, rho_mfs_in * (p_post_cyclone / max(0.5, p_in)))
    user_filter_op = inputs.get("filter_op_count") or inputs.get("filters_count")
    cfs_sizing = _size_cfs_filter_group(mass_flow_kgs, rho_cfs_in, ambient_temp_c, user_filter_op)
    filter_op_count = cfs_sizing["operating_count"]
    filter_total_count = cfs_sizing["installed_count"]
    flow_per_filter = cfs_sizing["flow_per_unit_kgs"]
    dp_filter = cfs_sizing["clean_dp_bar"]
    p_comp_inlet = round(max(0.5, p_post_cyclone - dp_filter), 2)

    # 4. Dynamic Turbo-Compressor Train Sizing & Real ThermoEngine Coupling
    dr = design_results or {}
    summ = dr.get("summary") or {}

    def _first_number(*values):
        for value in values:
            if value is None:
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(num):
                return num
        return None

    design_unit_cap = _first_number(
        dr.get("mass_flow_per_unit_kgs"),
        summ.get("mass_flow"),
    )

    design_power_total = _first_number(
        dr.get("power_shaft_total_kw"),
        dr.get("power_total_kw"),
        summ.get("power"),
        summ.get("gas_power"),
    )
    design_num_units = max(1, int(_first_number(dr.get("num_units"), inputs.get("num_units")) or 1))
    design_power_per_unit = _first_number(
        dr.get("power_shaft_per_unit_kw"),
        dr.get("power_unit_kw"),
        (design_power_total / design_num_units) if design_power_total else None,
    )

    design_t_discharge = _first_number(dr.get("t_out_c"), dr.get("t_out"), summ.get("t_out"), summ.get("t2"))
    if design_t_discharge is not None and design_t_discharge > 200.0:
        design_t_discharge -= 273.15

    design_head = _first_number(
        dr.get("head_kj_kg"),
        dr.get("head_total_kj_kg"),
        (float(dr["head_polytropic"]) / 1000.0) if _first_number(dr.get("head_polytropic")) else None,
        summ.get("head"),
        summ.get("polytropic_head"),
    )

    design_eff = _first_number(
        dr.get("actual_poly_efficiency"),
        summ.get("eff"),
        summ.get("polytropic_efficiency"),
    )
    if design_eff is not None and 0.0 < design_eff <= 1.0:
        design_eff *= 100.0

    design_pr = _first_number(dr.get("compression_ratio"))
    design_t_in_c = _first_number(dr.get("t_in_c"))
    current_pr = p_out / p_in if p_in > 0 else 1.0
    pr_shifted = bool(design_pr and design_pr > 0 and abs(current_pr - design_pr) / design_pr > 0.01)
    temp_shifted = bool(design_t_in_c is not None and abs(t_in - design_t_in_c) > 0.5)
    if pr_shifted or temp_shifted:
        design_power_per_unit = None
        design_head = None
        design_t_discharge = None

    dr_rho_in = _first_number(dr.get("rho_in")) if not (pr_shifted or temp_shifted) else None
    dr_z_in = _first_number(dr.get("z_in")) if not (pr_shifted or temp_shifted) else None
    if dr_rho_in and dr_rho_in > 0:
        rho_suction = dr_rho_in
        z_in_real = dr_z_in if (dr_z_in and dr_z_in > 0) else ((p_in * 1e5) / (rho_suction * R_gas * max(120.0, T_in_K)))
    elif inlet_state is not None and inlet_state.density and math.isfinite(inlet_state.density) and inlet_state.density > 0:
        rho_suction = float(inlet_state.density)
        z_in_real = float(inlet_state.Z) if (inlet_state.Z and math.isfinite(inlet_state.Z) and inlet_state.Z > 0) else 1.0
    else:
        z_in_real = 1.0
        rho_suction = max(0.05, (p_in * 1e5) / (z_in_real * R_gas * max(120.0, T_in_K)))

    design_total_flow = _first_number(dr.get("mass_flow_total_kgs"))
    design_flow_per_unit = (
        design_total_flow / design_num_units
        if design_total_flow and design_total_flow > 0
        else None
    )

    pr_safe_pre = max(1.001, p_out / max(0.5, p_in))
    k_pre = (
        float(inlet_state.k)
        if (inlet_state is not None and getattr(inlet_state, "k", 0) and math.isfinite(inlet_state.k) and inlet_state.k > 1.01)
        else 1.28
    )
    n_pre = ((k_pre - 1.0) / k_pre) / 0.85
    est_head_kj = max(
        1.0,
        (z_in_real * R_gas * max(120.0, T_in_K) * ((pr_safe_pre ** n_pre) - 1.0) / max(1e-4, n_pre)) / 1000.0,
    )
    est_total_power_kw = design_power_total or ((mass_flow_kgs * est_head_kj) / (0.85 * 0.98))
    aero_unit_cap_kgs = max(45.0, min(95.0, 2.2 * rho_suction))

    user_comp_op = inputs.get("comp_op_count") or inputs.get("operating_trains") or inputs.get("num_units")
    if user_comp_op:
        try:
            comp_op_count = max(1, min(8, int(user_comp_op)))
        except (TypeError, ValueError):
            comp_op_count = max(
                1,
                min(6, max(math.ceil(est_total_power_kw / 12500.0), math.ceil(mass_flow_kgs / aero_unit_cap_kgs))),
            )
    elif design_unit_cap and design_unit_cap > 0:
        comp_op_count = max(1, min(6, math.ceil(mass_flow_kgs / design_unit_cap)))
    else:
        comp_op_count = max(
            1,
            min(6, max(math.ceil(est_total_power_kw / 12500.0), math.ceil(mass_flow_kgs / aero_unit_cap_kgs))),
        )
    comp_total_count = comp_op_count + 1
    flow_per_comp = round(mass_flow_kgs / comp_op_count, 2)

    mech_eff_pct = _first_number(inputs.get("mech_eff"), dr.get("mech_eff"), 98.0) or 98.0
    if mech_eff_pct <= 1.0:
        mech_eff_pct *= 100.0
    mech_eff_pct = max(50.0, min(100.0, mech_eff_pct))

    therm_eff_pct = _first_number(
        inputs.get("therm_eff"),
        inputs.get("thermal_eff"),
        dr.get("driver_thermal_efficiency_pct"),
        dr.get("therm_eff"),
        35.0,
    ) or 35.0
    if therm_eff_pct <= 1.0:
        therm_eff_pct *= 100.0
    therm_eff_pct = max(15.0, min(65.0, therm_eff_pct))

    thermo_warnings: List[str] = []
    if (design_head is None or design_t_discharge is None or design_power_per_unit is None) and gas_obj is not None:
        raw_poly_eff = _first_number(inputs.get("poly_eff"), design_eff, 82.5) or 82.5
        if raw_poly_eff <= 0:
            raw_poly_eff = 82.5
        elif raw_poly_eff <= 1.0:
            raw_poly_eff *= 100.0
        raw_poly_eff = max(25.0, min(95.0, raw_poly_eff))

        raw_mech_eff = _first_number(inputs.get("mech_eff"), 98.0) or 98.0
        if raw_mech_eff <= 1.0:
            raw_mech_eff *= 100.0
        raw_mech_eff = max(50.0, min(100.0, raw_mech_eff))

        try:
            live_calc_inputs = {
                "p_in": p_in,
                "p_in_unit": "bar(a)",
                "p_out": p_out,
                "p_out_unit": "bar(a)",
                "t_in": t_in,
                "t_in_unit": "°C",
                "flow": mass_flow_kgs,
                "flow_unit": "kg/s",
                "gas_comp": gas_comp,
                "eos_method": eos_key,
                "method": str(
                    inputs.get("calc_method")
                    or inputs.get("method")
                    or dr.get("method")
                    or "Metot 6: Schultz 3-Üslü Gerçek Gaz"
                ),
                "poly_eff": raw_poly_eff,
                "mech_eff": raw_mech_eff,
                "num_units": comp_op_count,
                "num_stages": max(1, int(_first_number(inputs.get("num_stages"), dr.get("num_stages"), 1) or 1)),
                "intercooler_t": float(_first_number(inputs.get("intercooler_t"), 40.0) or 40.0),
                "intercooler_dp_pct": float(_first_number(inputs.get("intercooler_dp_pct"), 2.0) or 2.0),
                "use_consistency_iteration": False,
            }
            live_thermo_res = engine.calculate_design_performance_with_mode(live_calc_inputs)
            if live_thermo_res:
                live_head_j = _first_number(live_thermo_res.get("head_polytropic"))
                if design_head is None and live_head_j and live_head_j > 0:
                    design_head = live_head_j / 1000.0
                live_eff_val = _first_number(live_thermo_res.get("actual_poly_efficiency"), raw_poly_eff)
                if live_eff_val is not None and 0.0 < live_eff_val <= 1.0:
                    live_eff_val *= 100.0
                if design_eff is None or design_eff <= 0:
                    design_eff = live_eff_val
                live_tout = _first_number(live_thermo_res.get("t_out_c"), live_thermo_res.get("t_out"))
                if live_tout is not None and live_tout > 200.0:
                    live_tout -= 273.15
                if design_t_discharge is None and live_tout is not None:
                    design_t_discharge = live_tout
                live_p_unit = _first_number(
                    live_thermo_res.get("power_shaft_per_unit_kw"),
                    live_thermo_res.get("power_unit_kw"),
                )
                if design_power_per_unit is None and live_p_unit and live_p_unit > 0:
                    design_power_per_unit = live_p_unit
                    design_flow_per_unit = mass_flow_kgs / comp_op_count
                for w_msg in (live_thermo_res.get("warnings") or []):
                    if w_msg:
                        thermo_warnings.append(str(w_msg))
        except Exception as exc:
            logger.debug("Station live ThermoEngine fallback triggered: %s", exc)

    pr_safe = max(1.001, p_out / max(0.5, p_in))

    if design_eff and design_eff > 0:
        polytropic_eff = round(design_eff, 2)
    else:
        polytropic_eff = 82.5
    polytropic_eff = max(10.0, min(95.0, polytropic_eff))

    k_in_real = (
        float(inlet_state.k)
        if (inlet_state is not None and getattr(inlet_state, "k", 0) and math.isfinite(inlet_state.k) and inlet_state.k > 1.01)
        else 1.28
    )

    if design_head and design_head > 0:
        polytropic_head_kj = round(design_head, 2)
    else:
        n_exp = ((k_in_real - 1.0) / k_in_real) / (polytropic_eff / 100.0)
        head_j_est = z_in_real * R_gas * max(120.0, T_in_K) * ((pr_safe ** n_exp) - 1.0) / max(1e-4, n_exp)
        polytropic_head_kj = round(max(1.0, head_j_est / 1000.0), 2)

    if design_t_discharge is not None:
        t_discharge_hot = round(design_t_discharge, 1)
    else:
        n_exp = ((k_in_real - 1.0) / k_in_real) / (polytropic_eff / 100.0)
        t_discharge_hot = round(max(120.0, T_in_K) * (pr_safe ** n_exp) - 273.15, 1)
    t_discharge_hot = round(max(t_in, min(350.0, t_discharge_hot)), 1)
    # Verified exact coupling: Compressor Outlet Temp == Unit Discharge Header Temp == Gas Cooler Inlet Temp
    t_cooler_inlet_c = t_discharge_hot

    if design_power_per_unit is not None and design_power_per_unit > 0:
        scaled_power_per_unit = design_power_per_unit
        if design_flow_per_unit and design_flow_per_unit > 0:
            scaled_power_per_unit *= (mass_flow_kgs / comp_op_count) / design_flow_per_unit
        power_per_unit_kw = round(scaled_power_per_unit, 1)
        total_power_kw = round(power_per_unit_kw * comp_op_count, 1)
    else:
        total_power_kw = round(
            (mass_flow_kgs * polytropic_head_kj) / (polytropic_eff / 100.0 * 0.98),
            1,
        )
        power_per_unit_kw = round(total_power_kw / comp_op_count, 1)

    shelter_width_m = 24.0
    shelter_length_m = round(14.0 * comp_total_count + 8.0, 1)
    shelter_height_m = 12.5

    fuel_comp_for_aux = inputs.get("fuel_gas_comp") or gas_comp
    comp_aux = _size_compressor_auxiliaries(
        engine=engine,
        gas_comp=fuel_comp_for_aux,
        comp_op_count=comp_op_count,
        comp_total_count=comp_total_count,
        flow_per_comp_kgs=flow_per_comp,
        power_per_unit_kw=power_per_unit_kw,
        total_power_kw=total_power_kw,
        polytropic_eff_pct=polytropic_eff,
        mech_eff_pct=mech_eff_pct,
        thermal_eff_pct=therm_eff_pct,
        p_in_bar=p_in,
        p_out_bar=p_out,
        ambient_temp_c=ambient_temp_c,
    )

    # 5. Anti-Surge & Recycle Lines Sizing (with selected eos_model)
    surge_flow_limit = round(0.68 * flow_per_comp, 2)
    asv_valve_size_in = 8 if flow_per_comp < 30.0 else (12 if flow_per_comp < 60.0 else 16)
    asv_stroke_time_s = 0.8
    station_recycle_capacity_kgs = round(mass_flow_kgs * 1.0, 1)

    def _size_control_valve(path, flow_kgs, p_in_bar, p_out_bar, t_c):
        try:
            from kasp.integrations.control_valve.adapter import ControlValveAdapter

            p_in_val = max(0.5, float(p_in_bar))
            p_out_val = max(0.1, float(p_out_bar))
            if p_in_val <= p_out_val:
                p_out_val = p_in_val * 0.8

            res = ControlValveAdapter().calculate(
                {
                    "service": "gas",
                    "composition": gas_comp,
                    "eos_model": eos_key,
                    "mass_flow_kgs": max(0.001, float(flow_kgs)),
                    "p_in_bar": p_in_val,
                    "p_out_bar": p_out_val,
                    "t_c": max(-50.0, float(t_c)),
                    "path": path,
                }
            )
            res_dict = dict(res.get("results") or {})
            res_dict["provenance"] = res.get("provenance", {})
            return res_dict, list(res.get("warnings", []) or [])
        except BaseException as exc:
            return None, [f"{path} vana boyutlandırma hatası: {exc}"]

    asv_sizing, asv_warnings = _size_control_valve(
        "ASV", surge_flow_limit, p_out, max(p_in, p_comp_inlet), t_cooler_inlet_c
    )
    pcv_sizing, pcv_warnings = _size_control_valve(
        "PCV", station_recycle_capacity_kgs, p_out, max(p_in, p_comp_inlet), t_cooler_inlet_c
    )

    def _user_float(key: str, default: float) -> float:
        if not _has_explicit_value(inputs, key):
            return default
        try:
            value = float(inputs.get(key))
        except (TypeError, ValueError):
            return default
        return value if math.isfinite(value) else default

    # 6. Fin-Fan Gas Air Coolers Sizing (User Air Temp + Max Gas Outlet Temp + Real EOS Enthalpy Δh)
    cooler_air_user_override = _has_explicit_value(inputs, "cooler_air_temp_c")
    cooler_max_out_user_override = _has_explicit_value(inputs, "cooler_max_outlet_temp_c")
    cooler_air_temp_c = max(-50.0, min(65.0, _user_float("cooler_air_temp_c", ambient_temp_c)))
    cooler_max_outlet_temp_c = max(-30.0, min(180.0, _user_float("cooler_max_outlet_temp_c", 45.0)))

    air_cooler_warnings: List[str] = []
    if cooler_max_outlet_temp_c <= cooler_air_temp_c + 3.0:
        t_target_pipeline = round(cooler_air_temp_c + 5.0, 1)
        air_cooler_warnings.append(
            f"Gaz soğutucu maksimum gaz çıkış sıcaklığı ({cooler_max_outlet_temp_c:.1f} °C), "
            f"soğutma havası giriş sıcaklığına ({cooler_air_temp_c:.1f} °C) göre fiziksel yaklaşım sınırının "
            f"(min. ΔT ≥ 3 °C) altındadır; soğutucu çıkış sıcaklığı {t_target_pipeline:.1f} °C olarak sınırlandırıldı."
        )
    elif t_cooler_inlet_c <= cooler_max_outlet_temp_c:
        t_target_pipeline = round(t_cooler_inlet_c, 1)
    else:
        t_target_pipeline = round(cooler_max_outlet_temp_c, 1)

    dp_cooler = 0.40  # bar
    p_post_cooler = round(max(0.5, p_out - dp_cooler), 2)

    hot_state = _safe_eos_state(p_out, t_cooler_inlet_c)
    cooled_state = _safe_eos_state(p_post_cooler, t_target_pipeline)

    if t_cooler_inlet_c > t_target_pipeline:
        delta_h_kj_kg: Optional[float] = None
        if (
            hot_state is not None
            and cooled_state is not None
            and math.isfinite(hot_state.H)
            and math.isfinite(cooled_state.H)
            and hot_state.H > cooled_state.H
        ):
            delta_h_kj_kg = (hot_state.H - cooled_state.H) / 1000.0
        if delta_h_kj_kg is None or delta_h_kj_kg <= 0:
            cp_hot = (hot_state.Cp / 1000.0) if (hot_state is not None and hot_state.Cp and hot_state.Cp > 0) else None
            cp_cold = (cooled_state.Cp / 1000.0) if (cooled_state is not None and cooled_state.Cp and cooled_state.Cp > 0) else None
            if cp_hot and cp_cold:
                cp_real = 0.5 * (cp_hot + cp_cold)
            elif cp_hot:
                cp_real = cp_hot
            elif inlet_state is not None and inlet_state.Cp and inlet_state.Cp > 0:
                cp_real = inlet_state.Cp / 1000.0
            else:
                cp_real = (k_in_real * R_gas / max(0.05, k_in_real - 1.0)) / 1000.0
            delta_h_kj_kg = cp_real * (t_cooler_inlet_c - t_target_pipeline)
        heat_duty_mw = round(max(0.0, (mass_flow_kgs * delta_h_kj_kg) / 1000.0), 3)
    else:
        heat_duty_mw = 0.0

    if heat_duty_mw > 0:
        air_rise_c = min(22.0, max(8.0, 0.45 * max(4.0, t_cooler_inlet_c - cooler_air_temp_c)))
        cooler_air_out_c = min(max(cooler_air_temp_c + 1.5, t_cooler_inlet_c - 2.0), cooler_air_temp_c + air_rise_c)
        dt_hot = max(1.0, t_cooler_inlet_c - cooler_air_out_c)
        dt_cold = max(1.0, t_target_pipeline - cooler_air_temp_c)
        if abs(dt_hot - dt_cold) < 0.05:
            cooler_lmtd_c = dt_hot
        else:
            cooler_lmtd_c = (dt_hot - dt_cold) / math.log(dt_hot / dt_cold)
    else:
        cooler_air_out_c = cooler_air_temp_c
        cooler_lmtd_c = max(0.0, t_cooler_inlet_c - cooler_air_temp_c)

    # Scale standard bay thermal capacity (3.2 MW @ ISO LMTD ~37.86°C) by actual counter-current LMTD
    cooler_bay_capacity_mw = 3.2 * max(0.20, min(1.60, (cooler_lmtd_c / 37.86) if cooler_lmtd_c > 0 else 1.0))
    user_cooler_bays = inputs.get("cooler_bays_count")
    if user_cooler_bays not in (None, ""):
        cooler_bays_count = max(2, min(16, int(float(user_cooler_bays))))
    else:
        cooler_bays_count = max(2, min(16, math.ceil(heat_duty_mw / max(0.3, cooler_bay_capacity_mw)))) if heat_duty_mw > 0 else 2

    rho_cooler_avg = 45.0
    mu_cooler_avg = 1.35e-5
    _rho_vals = [
        float(getattr(st, "density", 0.0))
        for st in (hot_state, cooled_state)
        if st is not None and getattr(st, "density", None) and math.isfinite(st.density) and st.density > 0
    ]
    if _rho_vals:
        rho_cooler_avg = sum(_rho_vals) / len(_rho_vals)
    else:
        t_cooler_avg_k = max(120.0, ((t_cooler_inlet_c + t_target_pipeline) * 0.5) + 273.15)
        rho_cooler_avg = max(1.0, (p_out * 1e5) / (max(0.1, z_in_real) * R_gas * t_cooler_avg_k))
    _mu_vals = [
        float(getattr(st, "viscosity", 0.0))
        for st in (hot_state, cooled_state)
        if st is not None and getattr(st, "viscosity", None) and math.isfinite(st.viscosity) and st.viscosity > 0
    ]
    if _mu_vals:
        mu_cooler_avg = sum(_mu_vals) / len(_mu_vals)

    cooler_bundle_spec = _estimate_cooler_bundle_and_specs(
        mass_flow_kgs=mass_flow_kgs,
        cooler_bays_count=cooler_bays_count,
        p_out_bar=p_out,
        t_inlet_c=t_cooler_inlet_c,
        t_outlet_c=t_target_pipeline,
        cooler_air_temp_c=cooler_air_temp_c,
        heat_duty_mw=heat_duty_mw,
        rho_gas_kgm3=rho_cooler_avg,
        mu_gas_pas=mu_cooler_avg,
    )
    dp_cooler = cooler_bundle_spec["dp_cooler_bar"]
    p_post_cooler = round(max(0.5, p_out - dp_cooler), 2)
    for _cw in cooler_bundle_spec["warnings"]:
        if _cw not in air_cooler_warnings:
            air_cooler_warnings.append(_cw)

    air_cooler_design = None
    include_air_cooler_design = bool(inputs.get("include_air_cooler_design", False))
    if include_air_cooler_design and t_cooler_inlet_c > t_target_pipeline + 1.0:
        try:
            from kasp.integrations.air_cooler.adapter import AirCoolerAdapter

            cooler_eos_map = {"pr": "PR", "srk": "SRK"}
            cooler_eos = cooler_eos_map.get(eos_key, "HEOS")
            design = AirCoolerAdapter().calculate(
                {
                    "composition": gas_comp,
                    "eos": cooler_eos,
                    "mass_flow_kgs": mass_flow_kgs,
                    "p_in_bar": p_out,
                    "p_out_bar": p_post_cooler,
                    "t_in_c": t_cooler_inlet_c,
                    "t_out_c": t_target_pipeline,
                    "air_in_c": cooler_air_temp_c,
                    "air_out_c": round(cooler_air_out_c, 2),
                    "auto_size": True,
                }
            )
            air_cooler_design = design.get("results")
            air_cooler_warnings.extend(list(design.get("warnings", []) or []))
        except BaseException as exc:
            air_cooler_warnings.append(f"Detaylı hava soğutucu tasarımı yapılamadı: {exc}")

    tcv_sizing, tcv_warnings = _size_control_valve(
        "TCV", mass_flow_kgs * 0.35, p_out, p_post_cooler, t_cooler_inlet_c
    )

    # 7. Safety & Depressurization (PSV & Blowdown) coupled to Design Tab Atmospheric P & T
    def _safety_float(key: str, default: float) -> float:
        return _user_float(key, default)

    p_out_barg = max(0.20, p_out - p_atm_bar)
    default_psv_set_barg = round(max(p_out_barg * 1.10, p_out * 1.02 if p_out > 15.0 else p_out_barg * 1.10), 2)
    psv_set_pressure_bar = round(_safety_float("psv_set_pressure_bar", default_psv_set_barg), 2)
    if psv_set_pressure_bar <= p_out_barg:
        psv_set_pressure_bar = default_psv_set_barg
    psv_overpressure_pct = min(25.0, max(1.0, _safety_float("psv_overpressure_pct", 10.0)))
    psv_back_user_override = _has_explicit_value(inputs, "psv_back_pressure_bar")
    psv_back_pressure_bar = round(max(0.35, _safety_float("psv_back_pressure_bar", p_atm_bar)), 5)
    psv_valve_type = str(inputs.get("psv_valve_type") or "conventional").strip().lower()
    if psv_valve_type not in ("conventional", "balanced_bellows", "pilot"):
        psv_valve_type = "conventional"
    psv_count = max(1, min(4, int(_safety_float("psv_count", 2.0))))
    psv_duty_count = max(1, min(psv_count, int(_safety_float("psv_duty_count", 1.0))))
    bdv_depressurization_time_min = max(1.0, _safety_float("bdv_depressurization_time_min", 15.0))

    psv_input_contract = [
        {"key": "psv_set_pressure_bar", "label": "PSV ayar basıncı (bar(g))", "value": psv_set_pressure_bar, "source": "user" if _has_explicit_value(inputs, "psv_set_pressure_bar") else "derived"},
        {"key": "psv_overpressure_pct", "label": "PSV aşırı basınç oranı (%)", "value": psv_overpressure_pct, "source": "user" if _has_explicit_value(inputs, "psv_overpressure_pct") else "derived"},
        {"key": "psv_back_pressure_bar", "label": "PSV karşı basınç (bar(a))", "value": psv_back_pressure_bar, "source": "user" if psv_back_user_override else "design_tab"},
        {"key": "psv_valve_type", "label": "PSV tipi", "value": psv_valve_type, "source": "user" if _has_explicit_value(inputs, "psv_valve_type") else "derived"},
        {"key": "psv_count", "label": "PSV adedi (duty + standby)", "value": psv_count, "source": "user" if _has_explicit_value(inputs, "psv_count") else "derived"},
        {"key": "psv_duty_count", "label": "Eşzamanlı (duty) PSV adedi", "value": psv_duty_count, "source": "user" if _has_explicit_value(inputs, "psv_duty_count") else "derived"},
    ]
    psv_missing_inputs = [item["key"] for item in psv_input_contract if item["source"] == "derived"]

    psv_sizing = None
    psv_sizing_warnings = []
    try:
        from kasp.integrations.psv.adapter import PSVAdapter

        p_relieve_bar = psv_set_pressure_bar * (1.0 + psv_overpressure_pct / 100.0) + p_atm_bar
        relieve_state = _safe_eos_state(p_relieve_bar, t_cooler_inlet_c) or hot_state
        psv_payload: Dict[str, Any] = {
            "service": "gas",
            "p1_bar": p_relieve_bar,
            "p2_bar": psv_back_pressure_bar,
            "p_atm_bar": p_atm_bar,
            "ambient_temp_c": ambient_temp_c,
            "set_pressure_bar": psv_set_pressure_bar,
            "overpressure_pct": psv_overpressure_pct,
            "t_c": t_cooler_inlet_c,
            "mass_flow_kgs": mass_flow_kgs,
            "valve_type": psv_valve_type,
            "num_valves": psv_duty_count,
        }
        has_full_eos_props = False
        if relieve_state is not None:
            z_ok = bool(relieve_state.Z and math.isfinite(relieve_state.Z) and 0.05 < relieve_state.Z <= 2.0)
            mw_ok = bool(relieve_state.MW and math.isfinite(relieve_state.MW) and relieve_state.MW > 0)
            k_ok = bool(relieve_state.k and math.isfinite(relieve_state.k) and 1.0 < relieve_state.k <= 2.5)
            if z_ok:
                psv_payload["z"] = round(float(relieve_state.Z), 4)
            if mw_ok:
                psv_payload["mw"] = round(float(relieve_state.MW), 3)
            if k_ok:
                psv_payload["k"] = round(float(relieve_state.k), 4)
            has_full_eos_props = z_ok and mw_ok and k_ok
        if not has_full_eos_props:
            psv_payload["composition"] = gas_comp

        psv_result = PSVAdapter().calculate(psv_payload)
        raw_psv_res = psv_result.get("results", {})
        psv_sizing = raw_psv_res
        psv_sizing_warnings = list(psv_result.get("warnings", []) or [])
        if raw_psv_res.get("Selected_Orifice_Letter") == "Multiple Valves Required":
            multi_msg = "Tek PSV orifisi (API 526 T) kapasitesi aşıldı; çoklu paralel PSV seçimi gereklidir."
            if multi_msg not in psv_sizing_warnings:
                psv_sizing_warnings.append(multi_msg)
        if raw_psv_res.get("Required_Area_sqin") is not None:
            required_area = float(raw_psv_res.get("Required_Area_sqin") or 0.0)
            selected_area = float(raw_psv_res.get("Selected_Orifice_Area_sqin") or 0.0)
            orifice_letter = str(raw_psv_res.get("Selected_Orifice_Letter") or "-")
            inlet_flange, outlet_flange = _API526_FLANGE_SIZES.get(orifice_letter, ("8\"", "10\""))
            total_required_area = required_area * max(1, psv_duty_count)
            recommended_duty_count = max(1, math.ceil(total_required_area / 26.0))
            psv_sizing = {
                "required_area_sqin": required_area,
                "required_area_total_sqin": round(total_required_area, 3),
                "required_diameter_in": round(math.sqrt(4.0 * max(0.0, required_area) / math.pi), 3),
                "selected_orifice": orifice_letter,
                "selected_orifice_area_sqin": selected_area,
                "selected_orifice_diameter_in": round(math.sqrt(4.0 * max(0.0, selected_area) / math.pi), 3),
                "inlet_flange_in": inlet_flange,
                "outlet_flange_in": outlet_flange,
                "recommended_duty_count": recommended_duty_count,
                "recommended_total_count": recommended_duty_count + 1,
                "orifice_loading_pct": raw_psv_res.get("Orifice_Loading_Pct"),
                "flow_type": raw_psv_res.get("Flow_Type"),
                "p_atm_bar": raw_psv_res.get("p_atm_bar", round(p_atm_bar, 5)),
                "ambient_temp_c": raw_psv_res.get("ambient_temp_c", round(ambient_temp_c, 2)),
                "atm_gas_density_kgm3": raw_psv_res.get("atm_gas_density_kgm3"),
                "vent_exit_velocity_ms": raw_psv_res.get("vent_exit_velocity_ms"),
                "z_used": psv_payload.get("z"),
                "mw_used": psv_payload.get("mw"),
                "k_used": psv_payload.get("k"),
                "standard": (psv_result.get("provenance") or {}).get("standard"),
                "warnings": psv_sizing_warnings,
            }
    except BaseException as exc:
        psv_sizing_warnings.append(f"PSV ön boyutlandırma yapılamadı: {exc}")

    psv_auto_inputs = {
        "gas_comp": gas_comp,
        "eos_model": eos_key,
        "mw": round(mw, 3),
        "z": psv_sizing.get("z_used") if isinstance(psv_sizing, dict) else round(z_in_real, 4),
        "k": psv_sizing.get("k_used") if isinstance(psv_sizing, dict) else round(k_in_real, 4),
        "p_upstream_bar": round(p_out, 2),
        "t_relieving_c": round(t_cooler_inlet_c, 1),
        "p_atm_bar": round(p_atm_bar, 5),
        "ambient_temp_c": round(ambient_temp_c, 2),
        "mass_flow_total_kgs": round(mass_flow_kgs, 2),
    }

    # 8. Condensate Drain Collection (Spec 5250 DIN 6608/St37 + Spec 4500 §5.2: >= 15x blow-flask, min 3/5 m3)
    liquid_condensate_rate_m3h = round(0.008 * mass_flow_kgs, 3)
    standard_flow_sm3h = round((vol_flow_mmscmd * 1e6) / 24.0, 1)
    if standard_flow_sm3h <= 100000.0:
        spec_5250_base_tank_m3 = 3.0
        cond_pump_flow_m3h = 5.0
        cond_pump_motor_kw = 2.0
    else:
        spec_5250_base_tank_m3 = 5.0
        cond_pump_flow_m3h = 10.0
        cond_pump_motor_kw = 4.0
    min_15x_blowflask_m3 = round(
        max(3.0, mfs_sizing["dump_system"]["min_dump_tank_volume_m3"], 15.0 * cfs_sizing["blow_flask"]["dump_volume_m3"]),
        2,
    )
    condensate_tank_volume_m3 = round(
        max(
            spec_5250_base_tank_m3,
            min_15x_blowflask_m3,
            liquid_condensate_rate_m3h * 24.0 * 2.5,
        ),
        1,
    )

    # 8. Mainline Pigging Units
    mainline_nps = 24 if mass_flow_kgs < 50 else (36 if mass_flow_kgs < 120 else 48)
    pig_receiver_size = f"{mainline_nps}\" x {mainline_nps + 4}\" Class 600"
    pig_launcher_size = f"{mainline_nps}\" x {mainline_nps + 4}\" Class 900"

    # 9. Process Nodes Matrix (Compressor Outlet == Unit Discharge Header == Gas Cooler Inlet)
    nodes = [
        {
            "id": "N01_MAINLINE_INLET",
            "name": "Ana Hat Emiş Girişi (Mainline In)",
            "pressure_bar": round(p_in, 2),
            "temp_c": round(t_in, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Gaz (Vapor)",
            "state_desc": "Pig Alıcı (Trap) öncesi ham hat gazı",
            "color": "#38bdf8",
        },
        {
            "id": "N02_SUCTION_HEADER",
            "name": "Emiş Kolektörü (Suction Header)",
            "pressure_bar": round(p_in - 0.05, 2),
            "temp_c": round(t_in, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Gaz (Vapor)",
            "state_desc": "Siklon seperatör dağıtım kolektörü",
            "color": "#0ea5e9",
        },
        {
            "id": "N03_CYCLONE_OUTLET",
            "name": "Siklon Çıkışı (Post-Cyclone)",
            "pressure_bar": p_post_cyclone,
            "temp_c": round(t_in - 0.2, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Temizlenmiş Gaz (>10µm serbest)",
            "state_desc": f"{cyclone_op_count} aktif siklon sonrası sıvı ayrıştırılmış gaz",
            "color": "#2563eb",
        },
        {
            "id": "N04_FILTER_OUTLET",
            "name": "Kartuş Filtre Çıkışı (Post-Filter)",
            "pressure_bar": p_comp_inlet,
            "temp_c": round(t_in - 0.3, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Hassas Gaz (<0.3µm aerosol)",
            "state_desc": f"{filter_op_count} aktif kartuş sonrası süper-temiz gaz",
            "color": "#1d4ed8",
        },
        {
            "id": "N05_COMPRESSOR_DISCHARGE",
            "name": "Kompresör Çıkışı (Compressor Out)",
            "pressure_bar": round(p_out, 2),
            "temp_c": t_cooler_inlet_c,
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Yüksek Basınçlı Sıcak Gaz",
            "state_desc": f"{comp_op_count} aktif turbo-kompresör treni çıkışı",
            "color": "#ef4444",
        },
        {
            "id": "N06_DISCHARGE_HEADER",
            "name": "Ünite Basma Kolektörü / Soğutucu Girişi (Unit Discharge Header)",
            "pressure_bar": round(p_out - 0.05, 2),
            "temp_c": t_cooler_inlet_c,
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Basma Kolektör Gazı (Soğutucu Girişi)",
            "state_desc": "Gaz soğutucu sıcak girişi ve ana recycle ayrım noktası",
            "color": "#dc2626",
        },
        {
            "id": "N07_COOLER_OUTLET",
            "name": "Soğutucu Çıkışı (Post-Cooler)",
            "pressure_bar": p_post_cooler,
            "temp_c": round(t_target_pipeline, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Soğutulmuş Hat Gazı",
            "state_desc": f"{cooler_bays_count} bay hava soğutucu çıkışı",
            "color": "#10b981",
        },
        {
            "id": "N08_MAINLINE_OUTLET",
            "name": "Ana Hat İletim Basma (Mainline Out)",
            "pressure_bar": round(p_post_cooler - 0.05, 2),
            "temp_c": round(t_target_pipeline, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Şebeke Teslim Gazı",
            "state_desc": "Pig Atıcı (Trap) sonrası ana iletim hattı",
            "color": "#059669",
        },
    ]

    # 10. Dynamic Pipe Sizing & Natural Gas Flow Network (User Max Velocity + Governing Common Header Rule)
    max_vel_user_override = _has_explicit_value(inputs, "max_velocity_ms")
    max_velocity_ms = max(2.0, min(60.0, _user_float("max_velocity_ms", 20.0)))
    pipe_material_used = str(inputs.get("pipe_material") or "API 5L X70")
    design_factor_used = float(_user_float("design_factor_F", 0.50))

    def _clean_pipe_choice(raw_val: Any) -> Optional[str]:
        if raw_val is None:
            return None
        s = str(raw_val).replace('"', "").strip()
        if not s or s.lower() in {"auto", "otomatik", "none", "null"}:
            return None
        return s

    cyclone_inlet_pipe_choice = _clean_pipe_choice(inputs.get("cyclone_inlet_pipe_size"))
    cyclone_outlet_pipe_choice = _clean_pipe_choice(inputs.get("cyclone_outlet_pipe_size"))
    filter_inlet_pipe_choice = _clean_pipe_choice(inputs.get("filter_inlet_pipe_size"))
    filter_outlet_pipe_choice = _clean_pipe_choice(inputs.get("filter_outlet_pipe_size"))
    suct_len_user_override = _has_explicit_value(inputs, "suction_equiv_length_m")
    disch_len_user_override = _has_explicit_value(inputs, "discharge_equiv_length_m")
    suction_equiv_length_m = max(1.0, min(50000.0, _user_float("suction_equiv_length_m", 120.0)))
    discharge_equiv_length_m = max(1.0, min(50000.0, _user_float("discharge_equiv_length_m", 150.0)))

    station_piping = PipeSizingService.size_station_network(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_in,
        p_out_bar=p_out,
        t_in_c=t_in,
        t_discharge_c=t_cooler_inlet_c,
        t_cooled_c=t_target_pipeline,
        comp_op_count=comp_op_count,
        cyclone_op_count=cyclone_op_count,
        filter_op_count=filter_op_count,
        cooler_bays_count=cooler_bays_count,
        gas_mw=mw,
        pipe_material=pipe_material_used,
        design_factor_F=design_factor_used,
        pipe_standard=inputs.get("pipe_standard", "BOTAŞ"),
        psl_level=inputs.get("psl_level", "PSL2"),
        max_velocity_ms=max_velocity_ms,
        dp_cyclone_bar=dp_cyclone,
        dp_filter_bar=dp_filter,
        dp_cooler_bar=dp_cooler,
        gas_comp=gas_comp,
        eos_model=eos_key,
        thermo_solver=solver,
        cyclone_inlet_nominal=cyclone_inlet_pipe_choice,
        cyclone_outlet_nominal=cyclone_outlet_pipe_choice,
        filter_inlet_nominal=filter_inlet_pipe_choice,
        filter_outlet_nominal=filter_outlet_pipe_choice,
        suction_equiv_length_m=suction_equiv_length_m,
        discharge_equiv_length_m=discharge_equiv_length_m,
    )
    p_lines = station_piping["lines"]

    # 10b. Emergency Shutdown & Depressurization (ESD / BDV) Sizing:
    # HP blowdown uses user `esd_hp_volume_m3` at Compressor Outlet Pressure (`p_out`)
    # LP blowdown uses user `esd_lp_volume_m3` at Compressor Inlet Pressure (`p_in`)
    # Both discharge to Design Tab atmospheric pressure (`p_atm_bar`) and ambient temp (`ambient_temp_c`).
    def _line_size_in(key: str, fallback: float) -> float:
        raw = (p_lines.get(key) or {}).get("nominal_size_in")
        try:
            return float(str(raw).replace('"', "").strip())
        except (TypeError, ValueError):
            return fallback

    esd_hp_user_override = _has_explicit_value(inputs, "esd_hp_volume_m3")
    esd_lp_user_override = _has_explicit_value(inputs, "esd_lp_volume_m3")
    esd_hp_volume_m3 = max(0.5, _safety_float("esd_hp_volume_m3", 50.0))
    esd_lp_volume_m3 = max(0.5, _safety_float("esd_lp_volume_m3", 40.0))
    esd_allowable_dp_bar = max(0.05, _safety_float("esd_allowable_dp_bar", 0.5))
    esd_valve_type = str(inputs.get("esd_valve_type") or "full_bore_ball").strip().lower()
    if esd_valve_type not in ("full_bore_ball", "ball", "butterfly", "gate"):
        esd_valve_type = "full_bore_ball"
    esd_count = max(1, min(6, int(_safety_float("esd_count", 2.0))))
    esd_duty_count = max(1, min(esd_count, int(_safety_float("esd_duty_count", 1.0))))
    esd_suction_line_in = _line_size_in("suction_header", float(mainline_nps))
    esd_discharge_line_in = _line_size_in("discharge_header", float(mainline_nps))

    rho_hp_discharge = (
        float(hot_state.density)
        if (hot_state is not None and getattr(hot_state, "density", None) and math.isfinite(hot_state.density) and hot_state.density > 0)
        else max(0.2, (p_out * 1e5) / (max(0.1, z_in_real) * R_gas * max(120.0, t_cooler_inlet_c + 273.15)))
    )

    esd_suction, esd_suction_warnings = _size_esd_blowdown_section(
        path="ESD-LP-SUCTION",
        piping_volume_m3=esd_lp_volume_m3,
        upstream_pressure_bar=p_in,
        upstream_temp_c=t_in,
        p_atm_bar=p_atm_bar,
        ambient_temp_c=ambient_temp_c,
        depressurization_time_min=bdv_depressurization_time_min,
        line_size_in=esd_suction_line_in,
        gas_density_kgm3=rho_suction,
        mw_g_mol=mw,
        composition=gas_comp,
        eos_model=eos_key,
        allowable_dp_bar=esd_allowable_dp_bar,
        valve_type=esd_valve_type,
        duty_count=esd_duty_count,
    )
    esd_discharge, esd_discharge_warnings = _size_esd_blowdown_section(
        path="ESD-HP-DISCHARGE",
        piping_volume_m3=esd_hp_volume_m3,
        upstream_pressure_bar=p_out,
        upstream_temp_c=t_cooler_inlet_c,
        p_atm_bar=p_atm_bar,
        ambient_temp_c=ambient_temp_c,
        depressurization_time_min=bdv_depressurization_time_min,
        line_size_in=esd_discharge_line_in,
        gas_density_kgm3=rho_hp_discharge,
        mw_g_mol=mw,
        composition=gas_comp,
        eos_model=eos_key,
        allowable_dp_bar=esd_allowable_dp_bar,
        valve_type=esd_valve_type,
        duty_count=esd_duty_count,
    )
    esd_warnings = list(esd_suction_warnings) + list(esd_discharge_warnings)
    esd_input_contract = [
        {"key": "esd_hp_volume_m3", "label": "Boşaltılacak yüksek basınç borulama hacmi (m³)", "value": round(esd_hp_volume_m3, 2), "source": "user" if esd_hp_user_override else "derived"},
        {"key": "esd_lp_volume_m3", "label": "Boşaltılacak düşük basınç borulama hacmi (m³)", "value": round(esd_lp_volume_m3, 2), "source": "user" if esd_lp_user_override else "derived"},
        {"key": "esd_count", "label": "ESD/BDV vana adedi (toplam)", "value": esd_count, "source": "user" if _has_explicit_value(inputs, "esd_count") else "derived"},
        {"key": "esd_duty_count", "label": "Eşzamanlı aktif ESD/BDV adedi", "value": esd_duty_count, "source": "user" if _has_explicit_value(inputs, "esd_duty_count") else "derived"},
        {"key": "bdv_depressurization_time_min", "label": "Hedef boşaltma süresi (dk)", "value": bdv_depressurization_time_min, "source": "user" if _has_explicit_value(inputs, "bdv_depressurization_time_min") else "derived"},
        {"key": "esd_allowable_dp_bar", "label": "Hat ESD izin verilen basınç kaybı (bar)", "value": esd_allowable_dp_bar, "source": "user" if _has_explicit_value(inputs, "esd_allowable_dp_bar") else "derived"},
        {"key": "esd_valve_type", "label": "ESD vana tipi", "value": esd_valve_type, "source": "user" if _has_explicit_value(inputs, "esd_valve_type") else "derived"},
        {"key": "esd_suction_line_size_in", "label": "Emiş ESD hat çapı (inç)", "value": esd_suction_line_in, "source": "calculated"},
        {"key": "esd_discharge_line_size_in", "label": "Basma ESD hat çapı (inç)", "value": esd_discharge_line_in, "source": "calculated"},
    ]
    esd_missing_inputs = [item["key"] for item in esd_input_contract if item["source"] == "derived"]
    esd_auto_inputs = {
        "gas_comp": gas_comp,
        "eos_model": eos_key,
        "mw": round(mw, 3),
        "p_atm_bar": round(p_atm_bar, 5),
        "ambient_temp_c": round(ambient_temp_c, 2),
        "suction_p_in_bar": round(p_in, 2),
        "suction_t_c": round(t_in, 1),
        "suction_piping_volume_m3": round(esd_lp_volume_m3, 2),
        "suction_line_size_in": esd_suction_line_in,
        "discharge_p_in_bar": round(p_out, 2),
        "discharge_t_c": round(t_cooler_inlet_c, 1),
        "discharge_piping_volume_m3": round(esd_hp_volume_m3, 2),
        "discharge_line_size_in": esd_discharge_line_in,
        "mass_flow_total_kgs": round(mass_flow_kgs, 2),
    }

    # 10c. Ultrasonic Gas Flow Meter (USM - FT-401) on Station Discharge Header
    rho_cooled = (
        float(cooled_state.density)
        if (cooled_state is not None and getattr(cooled_state, "density", None) and cooled_state.density > 0)
        else max(1.0, (p_post_cooler * 1e5) / (max(0.1, z_in_real) * R_gas * (t_target_pipeline + 273.15)))
    )
    sos_cooled = (
        float(cooled_state.speed_of_sound)
        if (cooled_state is not None and getattr(cooled_state, "speed_of_sound", None) and cooled_state.speed_of_sound > 0)
        else math.sqrt(max(1.1, k_in_real) * max(0.1, z_in_real) * R_gas * (t_target_pipeline + 273.15))
    )
    usm_actual_flow_m3h = round((mass_flow_kgs / max(0.1, rho_cooled)) * 3600.0, 1)
    usm_velocity_ms = float(p_lines["discharge_header"].get("actual_velocity_ms") or 12.0)
    ultrasonic_meter_sizing = {
        "tag": "FT-401",
        "meter_type": "8-Path Chordal Ultrasonic Gas Flow Meter (AGA Report No. 9 / ISO 17089)",
        "nominal_size_in": p_lines["discharge_header"]["nominal_size_in"],
        "od_mm": p_lines["discharge_header"].get("od_mm", 1016.0),
        "pressure_bar_a": round(p_post_cooler, 2),
        "temperature_c": round(t_target_pipeline, 1),
        "mass_flow_kgs": round(mass_flow_kgs, 2),
        "actual_volumetric_flow_m3h": usm_actual_flow_m3h,
        "standard_flow_mmscmd": round(vol_flow_mmscmd, 2),
        "gas_velocity_ms": round(usm_velocity_ms, 2),
        "max_recommended_velocity_ms": 25.0,
        "speed_of_sound_ms": round(sos_cooled, 1),
        "gas_density_kgm3": round(rho_cooled, 2),
        "accuracy_class": "±0.15% (Custody Transfer / Fiscal Metering)",
        "straight_run_requirement": "10D Giriş (Flow Conditioner ile) / 5D Çıkış",
    }

    station_utilities = _size_station_utilities_and_relief(
        p_out_bar=p_out,
        p_in_bar=p_in,
        p_atm_bar=p_atm_bar,
        ambient_temp_c=ambient_temp_c,
        cooler_inlet_temp_c=t_cooler_inlet_c,
        cooler_outlet_temp_c=t_target_pipeline,
        mass_flow_kgs=mass_flow_kgs,
        comp_total_count=comp_total_count,
        cooler_bays_count=cooler_bays_count,
        bdv_depressurization_time_min=bdv_depressurization_time_min,
        ultrasonic_meter_sizing=ultrasonic_meter_sizing,
    )

    # Aggregate unique station-wide engineering warnings across thermo, valves, cooler, PSV, and piping
    station_warnings: List[str] = []

    def _add_warnings(prefix: str, items: List[str]):
        for item in items or []:
            msg = str(item).strip()
            if not msg:
                continue
            labeled = msg if msg.startswith(prefix) else f"{prefix}: {msg}"
            if labeled not in station_warnings:
                station_warnings.append(labeled)

    _add_warnings("Termodinamik", thermo_warnings)
    _add_warnings("MFS Siklon", mfs_sizing["design_warnings"])
    _add_warnings("CFS Kartuş Filtre", cfs_sizing["design_warnings"])
    _add_warnings("Turbo-Kompresör & Yardımcılar", comp_aux["design_warnings"])
    _add_warnings("ASV", asv_warnings)
    _add_warnings("PCV", pcv_warnings)
    _add_warnings("TCV", tcv_warnings)
    _add_warnings("Hava Soğutucu", air_cooler_warnings)
    _add_warnings("PSV", psv_sizing_warnings)
    _add_warnings("ESD", esd_warnings)
    _add_warnings("Yardımcı Tesisler", station_utilities.get("warnings", []))
    _add_warnings("Boru Ağı", station_piping.get("warnings", []))

    # 11. Pipe Flow Vectors (Dynamic speed factors scaled by actual flow velocities)
    pipe_flows = {
        "main_suction": {
            "speed_factor": round(max(0.4, p_lines["suction_header"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["suction_header"]["actual_velocity_ms"],
            "nominal_size": p_lines["suction_header"]["nominal_size_in"],
            "dir": "right",
            "color": "#0ea5e9",
            "status": "active",
        },
        "cyclone_branches": {
            "speed_factor": round(max(0.3, p_lines["cyclone_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["cyclone_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["cyclone_branch"]["nominal_size_in"],
            "dir": "down",
            "color": "#2563eb",
            "status": "active",
        },
        "cyclone_outlet_branches": {
            "speed_factor": round(max(0.3, p_lines["cyclone_outlet_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["cyclone_outlet_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["cyclone_outlet_branch"]["nominal_size_in"],
            "dir": "up",
            "color": "#2563eb",
            "status": "active",
        },
        "filter_branches": {
            "speed_factor": round(max(0.3, p_lines["filter_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["filter_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["filter_branch"]["nominal_size_in"],
            "dir": "down",
            "color": "#1d4ed8",
            "status": "active",
        },
        "filter_outlet_branches": {
            "speed_factor": round(max(0.3, p_lines["filter_outlet_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["filter_outlet_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["filter_outlet_branch"]["nominal_size_in"],
            "dir": "right",
            "color": "#1d4ed8",
            "status": "active",
        },
        "comp_suction": {
            "speed_factor": round(max(0.4, p_lines["comp_suction_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["comp_suction_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["comp_suction_branch"]["nominal_size_in"],
            "dir": "right",
            "color": "#3b82f6",
            "status": "active",
        },
        "comp_discharge": {
            "speed_factor": round(max(0.4, p_lines["comp_discharge_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["comp_discharge_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["comp_discharge_branch"]["nominal_size_in"],
            "dir": "up",
            "color": "#ef4444",
            "status": "active",
        },
        "anti_surge_loop": {
            "speed_factor": round(p_lines["anti_surge_loop"]["actual_velocity_ms"] / 15.0, 2),
            "actual_velocity_ms": p_lines["anti_surge_loop"]["actual_velocity_ms"],
            "nominal_size": p_lines["anti_surge_loop"]["nominal_size_in"],
            "dir": "down",
            "color": "#f59e0b",
            "status": "standby",
        },
        "station_recycle": {
            "speed_factor": 0.0,
            "actual_velocity_ms": p_lines["station_recycle"]["actual_velocity_ms"],
            "nominal_size": p_lines["station_recycle"]["nominal_size_in"],
            "dir": "left",
            "color": "#f97316",
            "status": "closed",
        },
        "cooler_inlet": {
            "speed_factor": round(max(0.4, p_lines["cooler_inlet"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["cooler_inlet"]["actual_velocity_ms"],
            "nominal_size": p_lines["cooler_inlet"]["nominal_size_in"],
            "dir": "right",
            "color": "#dc2626",
            "status": "active",
        },
        "main_discharge": {
            "speed_factor": round(max(0.4, p_lines["mainline_outlet"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["mainline_outlet"]["actual_velocity_ms"],
            "nominal_size": p_lines["mainline_outlet"]["nominal_size_in"],
            "dir": "right",
            "color": "#10b981",
            "status": "active",
        },
    }

    nodes_by_id = {n["id"]: n for n in nodes}
    equalized_hdr_keys = ("suction_header", "comp_suction_header", "unit_discharge_header", "discharge_header")
    common_hdr_nps_set = {p_lines[k]["nominal_key"] for k in equalized_hdr_keys if k in p_lines}
    common_hdr_nps = p_lines["suction_header"]["nominal_size_in"]
    gov_hdr_key = p_lines["suction_header"].get("governing_header_key") or "suction_header"

    p_atm_src = site_ambient["p_atm_source"]
    t_amb_src = site_ambient["ambient_temp_source"]
    max_vel_src = "user_input" if max_vel_user_override else "fixed_default"
    pipe_mat_src = "user_input" if _has_explicit_value(inputs, "pipe_material") else "fixed_default"
    design_f_src = "user_input" if _has_explicit_value(inputs, "design_factor_F") else "fixed_default"
    cooler_air_src = "user_input" if cooler_air_user_override else t_amb_src
    cooler_max_out_src = "user_input" if cooler_max_out_user_override else "fixed_default"
    cooler_bays_src = "user_input" if user_cooler_bays not in (None, "") else "station_3d_calc"
    cyc_cnt_src = "user_input" if user_cyclone_op else "station_3d_calc"
    flt_cnt_src = "user_input" if user_filter_op else "station_3d_calc"
    comp_cnt_src = (
        "user_input"
        if (_has_explicit_value(inputs, "comp_op_count") or _has_explicit_value(inputs, "operating_trains"))
        else ("design_tab" if (_has_explicit_value(inputs, "num_units") or bool(dr.get("num_units"))) else "station_3d_calc")
    )

    piping_provenance: List[Dict[str, Any]] = []
    for l_key, l_val in p_lines.items():
        is_common_hdr = l_key in equalized_hdr_keys
        if l_key in ("mainline_inlet", "suction_header", "cyclone_branch"):
            p_src_line, p_origin_line = "design_tab", "Tasarım Sekmesi Kompresör Giriş Basıncı (p_in)"
            t_src_line, t_origin_line = "design_tab", "Tasarım Sekmesi Gaz Giriş Sıcaklığı (t_in)"
        elif l_key in ("cyclone_outlet_branch", "filter_branch", "filter_outlet_branch", "comp_suction_header", "comp_suction_branch"):
            p_src_line, p_origin_line = "station_3d_calc", "p_in − Siklon/Filtre ΔP (3D İstasyon Hidrolik Hesabı)"
            t_src_line, t_origin_line = "design_tab", "Tasarım Sekmesi Gaz Giriş Sıcaklığı (t_in)"
        elif l_key in (
            "comp_discharge_branch",
            "anti_surge_loop",
            "unit_discharge_header",
            "station_recycle",
            "cooler_inlet",
            "cooler_bay_risers",
            "cooler_bay_inlet_header",
            "cooler_bypass",
        ):
            p_src_line, p_origin_line = "design_tab", "Tasarım Sekmesi Kompresör Çıkış Basıncı (p_out)"
            t_src_line, t_origin_line = "station_3d_calc", "Kompresör Çıkış Sıcaklığı (ThermoEngine / Tasarım t_out_c)"
        else:
            p_src_line, p_origin_line = "station_3d_calc", "p_out − Gaz Soğutucu ΔP (0.40 bar)"
            t_src_line, t_origin_line = (
                cooler_max_out_src if t_target_pipeline == round(cooler_max_outlet_temp_c, 1) else "station_3d_calc",
                "Gaz Soğutucu Çıkış Sıcaklığı (Kullanıcı Maks. Çıkış Sınırı / Yaklaşım Kontrolü)",
            )

        flow_src_line = (
            "design_tab"
            if l_key in (
                "mainline_inlet",
                "suction_header",
                "comp_suction_header",
                "unit_discharge_header",
                "discharge_header",
                "station_recycle",
                "cooler_inlet",
                "cooler_outlet",
                "mainline_outlet",
            )
            else "station_3d_calc"
        )
        flow_origin_line = (
            "Tasarım Sekmesi Toplam İstasyon Kütlesel Debisi (flow → kg/s)"
            if flow_src_line == "design_tab"
            else "Toplam Debinin Aktif Paralel Ekipman / Bay / Oran Sayısına Bölümü (3D Dinamik Dağıtım)"
        )

        piping_provenance.append(
            {
                "key": l_key,
                "tag": l_val.get("tag"),
                "name": l_val.get("name"),
                "hierarchy_level": l_val.get("hierarchy_level"),
                "hierarchy_label": l_val.get("hierarchy_label"),
                "is_common_header": is_common_hdr,
                "nominal_size_in": l_val.get("nominal_size_in"),
                "individual_nominal_size_in": l_val.get("individual_nominal_size_in"),
                "acceptable_nominals": l_val.get("acceptable_nominals", []),
                "acceptable_diameters_summary": l_val.get("acceptable_diameters_summary", ""),
                "parameters": [
                    {
                        "param": "flow_kgs",
                        "label": "Hat Kütlesel Debisi",
                        "value": l_val.get("flow_kgs"),
                        "unit": "kg/s",
                        "source": flow_src_line,
                        "origin_detail": flow_origin_line,
                    },
                    {
                        "param": "pressure_bar",
                        "label": "Hat İşletme Basıncı",
                        "value": l_val.get("pressure_bar"),
                        "unit": "bar(a)",
                        "source": p_src_line,
                        "origin_detail": p_origin_line,
                    },
                    {
                        "param": "temp_c",
                        "label": "Hat Gaz Sıcaklığı",
                        "value": l_val.get("temp_c"),
                        "unit": "°C",
                        "source": t_src_line,
                        "origin_detail": t_origin_line,
                    },
                    {
                        "param": "max_velocity_ms",
                        "label": "İzin Verilen Maks. Gaz Hızı Sınırı",
                        "value": round(max_velocity_ms, 2),
                        "unit": "m/s",
                        "source": max_vel_src,
                        "origin_detail": (
                            "3D Sekmesi Kullanıcı Girişi (max_velocity_ms)"
                            if max_vel_user_override
                            else "Sabit Default Maksimum Gaz Hızı (20.0 m/s)"
                        ),
                    },
                    {
                        "param": "pipe_material",
                        "label": "Boru Çelik Sınıfı",
                        "value": pipe_material_used,
                        "unit": "-",
                        "source": pipe_mat_src,
                        "origin_detail": (
                            "3D Sekmesi Kullanıcı Seçimi" if pipe_mat_src == "user_input" else "Sabit Default (API 5L X70)"
                        ),
                    },
                    {
                        "param": "design_factor_F",
                        "label": "ASME B31.8 Tasarım Faktörü (F)",
                        "value": design_factor_used,
                        "unit": "-",
                        "source": design_f_src,
                        "origin_detail": (
                            "3D Sekmesi Kullanıcı Seçimi" if design_f_src == "user_input" else "Sabit Default İstasyon içi F=0.50"
                        ),
                    },
                    {
                        "param": "individual_nominal_size_in",
                        "label": "Hız Sınırına Göre Tekil Min. Ticari Çap",
                        "value": l_val.get("individual_nominal_size_in"),
                        "unit": "NPS",
                        "source": "station_3d_calc",
                        "origin_detail": f"Gerçek EOS yoğunluğu + Barlow et kalınlığı + v ≤ {max_velocity_ms:.1f} m/s + API RP 14E",
                    },
                    {
                        "param": "nominal_size_in",
                        "label": "Uygulanan Nihai Hat Çapı",
                        "value": l_val.get("nominal_size_in"),
                        "unit": "NPS",
                        "source": "station_3d_calc",
                        "origin_detail": (
                            f"Ortak Header Kuralı: Ekipman bağlantıları hariç tüm header'ların en büyüğü ({common_hdr_nps}, belirleyici: {gov_hdr_key})"
                            if is_common_hdr
                            else "Ekipman Bağlantı Borulaması: Kendi debi ve hız sınırına göre tekil hesaplanan çap"
                        ),
                    },
                ],
            }
        )

    parameter_sources = {
        "categories": {
            "design_tab": {
                "code": "design_tab",
                "label_tr": "Tasarım Sekmesi (Kullanıcı Girişi / Termodinamik Hesap)",
                "label_en": "Design Tab (User Input / Thermo Calc)",
                "badge_color": "#38bdf8",
            },
            "station_3d_calc": {
                "code": "station_3d_calc",
                "label_tr": "3D / İstasyon Dinamik Hesabı",
                "label_en": "3D / Station Dynamic Calculation",
                "badge_color": "#10b981",
            },
            "user_input": {
                "code": "user_input",
                "label_tr": "3D Sekmesi Kullanıcı Girişi",
                "label_en": "3D Tab User Input",
                "badge_color": "#f59e0b",
            },
            "fixed_default": {
                "code": "fixed_default",
                "label_tr": "Sabit Default Mühendislik Değeri",
                "label_en": "Fixed Engineering Default",
                "badge_color": "#94a3b8",
            },
        },
        "coupling_checks": {
            "compressor_outlet_equals_cooler_inlet": {
                "verified": bool(
                    abs(nodes_by_id["N05_COMPRESSOR_DISCHARGE"]["temp_c"] - t_cooler_inlet_c) < 0.05
                    and abs(nodes_by_id["N06_DISCHARGE_HEADER"]["temp_c"] - t_cooler_inlet_c) < 0.05
                    and abs(p_lines["unit_discharge_header"]["temp_c"] - t_cooler_inlet_c) < 0.05
                ),
                "compressor_outlet_temp_c": nodes_by_id["N05_COMPRESSOR_DISCHARGE"]["temp_c"],
                "unit_discharge_header_temp_c": p_lines["unit_discharge_header"]["temp_c"],
                "cooler_inlet_temp_c": t_cooler_inlet_c,
                "summary_tr": (
                    f"Kompresör çıkış sıcaklığı ({t_cooler_inlet_c:.1f} °C) doğrudan Unit Discharge Header "
                    f"({p_lines['unit_discharge_header']['temp_c']:.1f} °C) ve Gaz Soğutucu giriş sıcaklığı "
                    f"({t_cooler_inlet_c:.1f} °C) olarak alınmaktadır."
                ),
            },
            "headers_equalized_to_max_nps": {
                "verified": len(common_hdr_nps_set) == 1,
                "common_nominal_size_in": common_hdr_nps,
                "governing_header_key": gov_hdr_key,
                "max_velocity_ms": round(max_velocity_ms, 2),
                "equalized_headers": list(equalized_hdr_keys),
                "summary_tr": (
                    f"Ekipman bağlantı borulaması hariç tüm header hesapları içindeki en büyük çap ({common_hdr_nps}, "
                    f"belirleyici: {gov_hdr_key}) Station Suction, Unit Suction, Unit Discharge ve Station Discharge "
                    f"header'larına ortak olarak atanmıştır (v_max = {max_velocity_ms:.1f} m/s)."
                ),
            },
            "esd_uses_design_atm_and_volumes": {
                "verified": bool(
                    esd_discharge is not None
                    and esd_suction is not None
                    and abs(esd_discharge["upstream_pressure_bar"] - round(p_out, 2)) < 0.05
                    and abs(esd_suction["upstream_pressure_bar"] - round(p_in, 2)) < 0.05
                    and abs(esd_auto_inputs["p_atm_bar"] - round(p_atm_bar, 5)) < 1e-4
                    and abs(esd_auto_inputs["ambient_temp_c"] - round(ambient_temp_c, 2)) < 0.05
                ),
                "hp_pressure_bar": round(p_out, 2),
                "hp_volume_m3": round(esd_hp_volume_m3, 2),
                "lp_pressure_bar": round(p_in, 2),
                "lp_volume_m3": round(esd_lp_volume_m3, 2),
                "p_atm_bar": round(p_atm_bar, 5),
                "ambient_temp_c": round(ambient_temp_c, 2),
                "summary_tr": (
                    f"ESD/BDV hesabı YB={p_out:.2f} bar(a) ({esd_hp_volume_m3:.1f} m³), DB={p_in:.2f} bar(a) "
                    f"({esd_lp_volume_m3:.1f} m³), Tasarım Sekmesi P_atm={p_atm_bar:.4f} bar(a) ve T_atm={ambient_temp_c:.1f} °C ile doğrulandı."
                ),
            },
            "psv_uses_design_atm_and_temp": {
                "verified": bool(
                    abs(psv_auto_inputs["p_atm_bar"] - round(p_atm_bar, 5)) < 1e-4
                    and abs(psv_auto_inputs["ambient_temp_c"] - round(ambient_temp_c, 2)) < 0.05
                ),
                "p_atm_bar": round(p_atm_bar, 5),
                "ambient_temp_c": round(ambient_temp_c, 2),
                "psv_back_pressure_bar": round(psv_back_pressure_bar, 5),
                "summary_tr": (
                    f"PSV hesabı Tasarım Sekmesi atmosferik basıncı P_atm={p_atm_bar:.4f} bar(a) ({ambient_pressure_kpa:.2f} kPa) "
                    f"ve ortam sıcaklığı T_atm={ambient_temp_c:.1f} °C ile doğrulandı."
                ),
            },
            "spec_4500_piping_compliance": {
                "verified": bool((station_piping.get("spec_4500_compliance") or {}).get("overall_compliant")),
                "suction_dp_bar": (station_piping.get("spec_4500_compliance") or {}).get("suction_piping", {}).get("dp_piping_bar"),
                "discharge_dp_bar": (station_piping.get("spec_4500_compliance") or {}).get("discharge_piping", {}).get("dp_piping_bar"),
                "summary_tr": (
                    f"4-NGTL 0-CS-M-002-4500 §5.1 borulama doğrulaması: Emiş ΔP="
                    f"{((station_piping.get('spec_4500_compliance') or {}).get('suction_piping') or {}).get('dp_piping_bar', '-')} bar (≤ 1.0 bar, scrubber hariç), "
                    f"Basma ΔP={((station_piping.get('spec_4500_compliance') or {}).get('discharge_piping') or {}).get('dp_piping_bar', '-')} bar (≤ 0.5 bar, soğutucu hariç)."
                ),
            },
        },
        "equipment": [
            {
                "key": "pig_traps",
                "tag": "PIG-R / PIG-L",
                "name": "Giriş Pig Alıcı & Çıkış Pig Atıcı Kovanları",
                "parameters": [
                    {"param": "suction_pressure_bar", "label": "PIG-R İşletme Basıncı", "value": round(p_in, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Giriş Basıncı (p_in)"},
                    {"param": "discharge_pressure_bar", "label": "PIG-L İşletme Basıncı", "value": p_post_cooler, "unit": "bar(a)", "source": "station_3d_calc", "origin_detail": "p_out − Gaz Soğutucu ΔP (3D İstasyon Hesabı)"},
                    {"param": "mainline_nps", "label": "Ana Hat Bağlantı Çapı", "value": p_lines["mainline_inlet"]["nominal_size_in"], "unit": "NPS", "source": "station_3d_calc", "origin_detail": "L-101 / L-115 Hız Sınırı & Barlow Boru Çapı Hesabı"},
                    {"param": "barrel_oversize_in", "label": "Kovan Gövde Büyütme Payı", "value": "+4\"", "unit": "inç", "source": "fixed_default", "origin_detail": "Sabit BOTAŞ Pig Trap standardı (Hat Çapı + 4\", Class 600/900)"},
                ],
            },
            {
                "key": "cyclones",
                "tag": "V-101..N",
                "name": "Çoklu Siklon Seperatörler (MFS)",
                "parameters": [
                    {"param": "total_mass_flow_kgs", "label": "Toplam Gaz Debisi", "value": round(mass_flow_kgs, 2), "unit": "kg/s", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Debi Girişi + Gerçek EOS Birim Çevrimi"},
                    {"param": "inlet_pressure_bar", "label": "Giriş Basıncı", "value": round(p_in, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi p_in"},
                    {"param": "unit_cap_cyclone_kgs", "label": "Birim Siklon Tasarım Kapasitesi", "value": mfs_sizing["unit_design_capacity_kgs"], "unit": "kg/s", "source": "station_3d_calc", "origin_detail": f"Dinamik boyutlandırma: Toplam Debi / N = %{mfs_sizing['unit_capacity_pct']} ünite yükü ({cyclone_op_count} çalışan + 1 yedek)"},
                    {"param": "operating_count", "label": "Çalışan Siklon Sayısı (N)", "value": cyclone_op_count, "unit": "adet", "source": cyc_cnt_src, "origin_detail": "PFD 4000 & Özel §4.8.2 (2+1 %50) veya 3D Kullanıcı Seçimi (+1 Yedek)"},
                    {"param": "pressure_drop_bar", "label": "Siklon Temiz Basınç Kaybı (ΔP)", "value": dp_cyclone, "unit": "bar", "source": "station_3d_calc", "origin_detail": f"Çoklu siklon tüp hızı ΔP (Spec 5260: temiz ≤ 400 mbar, kirli alarm 700 mbar)"},
                    {"param": "efficiency_spec", "label": "Ayırma Hassasiyeti & Mekanik", "value": f"≥ 8 µm %100 · ≥ 4 µm %90 · {mfs_sizing['corrosion_allowance_mm']} mm CA", "unit": "ASME VIII", "source": "fixed_default", "origin_detail": "Spec 4-NGTL 0-GN-P-002-5260 Attachment-I (Spherical Fixed Head, SS iç cıvata)"},
                    {"param": "heat_tracing_min_c", "label": "Blow-Flask & Heat Tracing", "value": mfs_sizing["heat_tracing"]["min_temp_c"], "unit": "°C min", "source": "fixed_default", "origin_detail": f"Spec 4500 §5.2 yatay blow-flask ({mfs_sizing['blow_flask']['diameter_mm']}×{mfs_sizing['blow_flask']['length_mm']} mm) + 2 seviye şişesi + ≥ 2 °C ısıtma"},
                    {"param": "inlet_pipe_size", "label": "MFS Giriş Bağlantı Çapı", "value": p_lines["cyclone_branch"]["nominal_size_in"], "unit": "NPS", "source": p_lines["cyclone_branch"].get("diameter_source", "station_3d_calc"), "origin_detail": f"L-103 tekil giriş branşmanı (min {p_lines['cyclone_branch'].get('velocity_min_nominal_in')} @ v ≤ {max_velocity_ms:.1f} m/s)"},
                    {"param": "outlet_pipe_size", "label": "MFS Çıkış Bağlantı Çapı", "value": p_lines["cyclone_outlet_branch"]["nominal_size_in"], "unit": "NPS", "source": p_lines["cyclone_outlet_branch"].get("diameter_source", "station_3d_calc"), "origin_detail": f"L-103A tekil çıkış branşmanı (min {p_lines['cyclone_outlet_branch'].get('velocity_min_nominal_in')} @ v ≤ {max_velocity_ms:.1f} m/s)"},
                ],
            },
            {
                "key": "cartridge_filters",
                "tag": "F-101..N",
                "name": "Hassas Kartuş / Koaleser Filtreler (CFS)",
                "parameters": [
                    {"param": "inlet_pressure_bar", "label": "CFS Giriş Basıncı", "value": p_post_cyclone, "unit": "bar(a)", "source": "station_3d_calc", "origin_detail": "p_in − ΔP_siklon dinamik düğüm basıncı (N03)"},
                    {"param": "unit_cap_filter_kgs", "label": "Birim Filtre Tasarım Kapasitesi", "value": cfs_sizing["unit_design_capacity_kgs"], "unit": "kg/s", "source": "station_3d_calc", "origin_detail": f"Dinamik boyutlandırma: Toplam Debi / N = %{cfs_sizing['unit_capacity_pct']} ünite yükü ({filter_op_count} çalışan + 1 yedek)"},
                    {"param": "operating_count", "label": "Çalışan Filtre Sayısı (N)", "value": filter_op_count, "unit": "adet", "source": flt_cnt_src, "origin_detail": "PFD 4000 & Özel §4.8.2 (2+1 %50) veya 3D Kullanıcı Seçimi (+1 Yedek)"},
                    {"param": "clean_dp_bar", "label": "Temiz Filtre Basınç Kaybı (ΔP)", "value": dp_filter, "unit": "bar", "source": "station_3d_calc", "origin_detail": "Kartuş yükü ΔP (Spec 5210 §4.3 temiz ≤ 140 mbar; Özel §4.8.2 değişim 300 mbar / patlama 3 bar)"},
                    {"param": "efficiency_spec", "label": "Filtrasyon & Kapak / Mekanik", "value": f"≥ 3 µm %99.8 · QOC + Davit · ASME VIII CE", "unit": "1.5× Test", "source": "fixed_default", "origin_detail": "Spec 5210 §4.4 & Özel §4.8.2 (10 µm sıvı, 3 set yedek filtre + conta, ISO NR 80)"},
                    {"param": "heat_tracing_min_c", "label": "Blow-Flask & Heat Tracing", "value": cfs_sizing["heat_tracing"]["min_temp_c"], "unit": "°C min", "source": "fixed_default", "origin_detail": f"Spec 5210 §4.1 yatay blow-flask ({cfs_sizing['blow_flask']['diameter_mm']}×{cfs_sizing['blow_flask']['length_mm']} mm) + izolasyon braketli ≥ 2 °C ısıtma"},
                    {"param": "inlet_pipe_size", "label": "CFS Giriş Bağlantı Çapı", "value": p_lines["filter_branch"]["nominal_size_in"], "unit": "NPS", "source": p_lines["filter_branch"].get("diameter_source", "station_3d_calc"), "origin_detail": f"L-104 tekil giriş branşmanı (min {p_lines['filter_branch'].get('velocity_min_nominal_in')} @ v ≤ {max_velocity_ms:.1f} m/s)"},
                    {"param": "outlet_pipe_size", "label": "CFS Çıkış Bağlantı Çapı", "value": p_lines["filter_outlet_branch"]["nominal_size_in"], "unit": "NPS", "source": p_lines["filter_outlet_branch"].get("diameter_source", "station_3d_calc"), "origin_detail": f"L-104A tekil çıkış branşmanı (min {p_lines['filter_outlet_branch'].get('velocity_min_nominal_in')} @ v ≤ {max_velocity_ms:.1f} m/s)"},
                ],
            },
            {
                "key": "turbo_compressors",
                "tag": "C-101..N",
                "name": "Santrifüj Turbo-Kompresör Trenleri",
                "parameters": [
                    {"param": "gas_comp", "label": "Doğal Gaz Karışımı & EOS", "value": eos_key.upper(), "unit": "mol%", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Gaz Kompozisyonu ve EOS Seçimi"},
                    {"param": "suction_pressure_bar", "label": "Emiş Basıncı (p_in)", "value": round(p_in, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Giriş Basıncı"},
                    {"param": "discharge_pressure_bar", "label": "Basma Basıncı (p_out)", "value": round(p_out, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Çıkış Basıncı"},
                    {"param": "suction_temp_c", "label": "Emiş Sıcaklığı (t_in)", "value": round(t_in, 1), "unit": "°C", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Giriş Sıcaklığı"},
                    {"param": "operating_count", "label": "Çalışan Ünite Sayısı", "value": comp_op_count, "unit": "adet", "source": comp_cnt_src, "origin_detail": "Tasarım Sekmesi / Gerçek Güç & Debi Zarfı (+1 Yedek)"},
                    {"param": "polytropic_efficiency_pct", "label": "Politropik Verim", "value": polytropic_eff, "unit": "%", "source": "design_tab" if (_has_explicit_value(inputs, "poly_eff") or design_eff) else "fixed_default", "origin_detail": "Tasarım Sekmesi Politropik Verimi (Özel §6.1.2 hedef ≥ %85)"},
                    {"param": "discharge_temp_c", "label": "Kompresör Çıkış Sıcaklığı (T_out)", "value": t_cooler_inlet_c, "unit": "°C", "source": "station_3d_calc", "origin_detail": "Tasarım Sekmesi / Canlı ThermoEngine Gerçek Gaz Politropik Sıkıştırma Çıkışı"},
                    {"param": "total_power_mw", "label": "Toplam Mil Gücü", "value": round(total_power_kw / 1000.0, 2), "unit": "MW", "source": "station_3d_calc", "origin_detail": "Tasarım Sekmesi / ThermoEngine Mil Gücü Hesabı"},
                    {"param": "unit_valves_spec", "label": "Ünite Vana & Geçici Strainer", "value": f"2×MOV (≤{comp_aux['unit_valves_and_strainer']['motor_actuator_stroke_max_s']:.0f}s) + Strainer", "unit": "Spec 4500 §5.5", "source": "fixed_default", "origin_detail": "Emiş/Basma seri çift blok ayrık gövde küresel vana + emiş geçici konik strainer + non-slam çek vana"},
                    {"param": "dgs_spec", "label": "Kuru Gaz Salmastrası (DGS)", "value": f"Duplex 1 µm + PDCV + Carbon Seal", "unit": "API 692", "source": "fixed_default", "origin_detail": comp_aux["dry_gas_seal"]["spare_sets_required"]},
                    {"param": "lube_oil_spec", "label": "Yağlama Yağı & Tank Tutma", "value": f"{comp_aux['lube_oil_system']['flow_lpm_per_unit']} L/dk ({comp_aux['lube_oil_system']['reservoir_min_working_volume_l']:.0f} L min)", "unit": "10 µm Duplex", "source": "station_3d_calc", "origin_detail": f"≥5 dk tutma + ≥51 cm²/(L/dk) ({comp_aux['lube_oil_system']['reservoir_min_surface_area_cm2']:.0f} cm²) + 2-fan hava soğutucu + UPS DC pompa"},
                    {"param": "air_intake_spec", "label": "Türbin Hava Emiş & Gürültü", "value": f"≤ 8 mbar (temiz) · 85 dBA", "unit": "NR 80", "source": "fixed_default", "origin_detail": "Kendini temizleyen ters darbe filtre (7.5/12.5 mbar) + %120 VFD elektrik marş motoru"},
                ],
            },
            {
                "key": "compressor_building",
                "tag": "BLDG-COMP",
                "name": "Kompresör Binası & Akustik Muhafaza",
                "parameters": [
                    {"param": "installed_units", "label": "Kurulu Tren Sayısı (N+1)", "value": comp_total_count, "unit": "adet", "source": "station_3d_calc", "origin_detail": "Çalışan Kompresör Sayısı + 1 Yedek"},
                    {"param": "length_m", "label": "Bina Uzunluğu", "value": shelter_length_m, "unit": "m", "source": "station_3d_calc", "origin_detail": "14.0 × Kurulu Ünite + 8.0 m dinamik yerleşim formülü"},
                    {"param": "width_height_m", "label": "Bina Genişlik × Yükseklik", "value": f"{shelter_width_m} × {shelter_height_m}", "unit": "m", "source": "fixed_default", "origin_detail": "Sabit Default Hol Açıklığı (24.0 m × 12.5 m, ≤ 80 °C UPS havalandırma)"},
                    {"param": "crane_capacity_tons", "label": "Tavan Gezer Vinç Kapasitesi", "value": comp_aux["crane_capacity_tons"], "unit": "ton", "source": "station_3d_calc", "origin_detail": "Ünite mil gücüne bağlı dinamik kaldırma kapasitesi"},
                ],
            },
            {
                "key": "fuel_gas",
                "tag": "FG-101",
                "name": "Yakıt Gazı Şartlandırma & Ölçüm Skidi",
                "parameters": [
                    {"param": "takeoff_point", "label": "Yakıt Gazı Çekiş Noktası", "value": "CFS Çıkışı ↔ Soğutucu Girişi", "unit": "Özel §4.8.5", "source": "fixed_default", "origin_detail": comp_aux["fuel_gas_system"]["takeoff_location"]},
                    {"param": "lhv_kj_kg", "label": "ISO 6976 Alt Isıl Değer (LHV)", "value": comp_aux["fuel_gas_system"]["lhv_kj_kg"], "unit": "kJ/kg", "source": "station_3d_calc", "origin_detail": "Tasarım Sekmesi yakıt gazı kompozisyonu ile ISO 6976:2016 gerçek gaz hesabı"},
                    {"param": "fuel_per_unit_kgh", "label": "Tren Başına Yakıt Debisi (%100 / %120 Tasarım)", "value": f"{comp_aux['fuel_gas_system']['fuel_per_unit_kgh']} / {comp_aux['fuel_gas_system']['design_fuel_per_unit_kgh']}", "unit": "kg/h", "source": "station_3d_calc", "origin_detail": f"Termal Verim %{comp_aux['fuel_gas_system']['thermal_efficiency_pct']} · Spec 4500 §8.5 (%120 tasarım faktörü)"},
                    {"param": "conditioning_spec", "label": "1 µm Seperatör + Eşanjör (1+1)", "value": "99.8% @ 1 µm · 20 ± 5 °C", "unit": "316 SS", "source": "fixed_default", "origin_detail": "Yatay sock seperatör + ≥2 °C blow-flask + 1+1 glikol ısıtıcı + 2×100% regülatör + 2 set yedek filtre"},
                ],
            },
            {
                "key": "air_coolers",
                "tag": "E-101",
                "name": "Fin-Fan Gaz Hava Soğutucular (API 661)",
                "parameters": [
                    {"param": "inlet_temp_c", "label": "Gaz Soğutucu Giriş Sıcaklığı", "value": t_cooler_inlet_c, "unit": "°C", "source": "station_3d_calc", "origin_detail": "Doğrudan Kompresör Çıkış Sıcaklığı (N05 = N06 = E-101 Giriş)"},
                    {"param": "inlet_pressure_bar", "label": "Gaz Soğutucu Giriş Basıncı", "value": round(p_out, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Çıkış Basıncı (p_out)"},
                    {"param": "cooler_air_temp_c", "label": "Soğutma Havası Giriş Sıcaklığı", "value": round(cooler_air_temp_c, 1), "unit": "°C", "source": cooler_air_src, "origin_detail": "3D Kullanıcı Girişi (girilmezse Tasarım Sekmesi Ortam Sıcaklığı ambient_temp)"},
                    {"param": "cooler_max_outlet_temp_c", "label": "Maksimum Gaz Çıkış Sıcaklığı Sınırı", "value": round(cooler_max_outlet_temp_c, 1), "unit": "°C", "source": cooler_max_out_src, "origin_detail": "3D Kullanıcı Girişi (girilmezse 45.0 °C default iletim sınırı)"},
                    {"param": "outlet_temp_c", "label": "Gerçekleşen Gaz Çıkış Sıcaklığı", "value": round(t_target_pipeline, 1), "unit": "°C", "source": "station_3d_calc", "origin_detail": "Maks. gaz çıkış sınırı ile hava sıcaklığı yaklaşım (ΔT_min) kontrolü sonucu"},
                    {"param": "pressure_drop_bar", "label": "Tüp Demeti Basınç Kaybı (ΔP)", "value": dp_cooler, "unit": "bar", "source": "station_3d_calc", "origin_detail": f"API 661 / Spec 5234 Dinamik Tüp Demeti ΔP (v={cooler_bundle_spec['tube_velocity_ms']} m/s · {cooler_bundle_spec['tubes_per_bay']} tüp/bay · 12 BWG)"},
                    {"param": "total_heat_duty_mw", "label": "Toplam Soğutma Isıl Yükü (Q)", "value": heat_duty_mw, "unit": "MW", "source": "station_3d_calc", "origin_detail": "m_dot × (h_giriş − h_çıkış) gerçek EOS entalpi farkı"},
                    {"param": "lmtd_c", "label": "Logaritmik Ortalama Sıcaklık Farkı (LMTD)", "value": round(cooler_lmtd_c, 2), "unit": "°C", "source": "station_3d_calc", "origin_detail": "Gaz (T_in→T_out) ve Hava (T_air,in→T_air,out) karşıt akış LMTD hesabı"},
                    {"param": "bay_count", "label": "Fin-Fan Bay Sayısı", "value": cooler_bays_count, "unit": "bay", "source": cooler_bays_src, "origin_detail": "Isıl yük ve LMTD düzeltmeli bay kapasitesinden dinamik hesap (veya 3D kullanıcı seçimi)"},
                    {"param": "cooler_spec_5234", "label": "Fin-Fan & TCV Tasarım Sınırları", "value": "Forced-Draft · VFD IEEE 519 (≥%95) · 50 m/s", "unit": "Spec 5234 / §5.14", "source": "fixed_default", "origin_detail": "40°C/45°C sınır, Murphy titreşim anahtarı, 2.0 mm alüminyum panjurlu güneşlik, ON/OFF Gas-over-Oil Fail-Open TCV"},
                ],
            },
            {
                "key": "station_utilities",
                "tag": "UTIL-101..401",
                "name": "İstasyon Yardımcı Sistemleri (Power/Utility Gas, Hava, Glikol & Emniyet)",
                "parameters": [
                    {"param": "power_gas_design_bar", "label": "Power Gas & Metanol Dehidratör", "value": station_utilities["power_gas"]["design_pressure_bar"], "unit": "bar(g) (110% MAOP)", "source": "station_3d_calc", "origin_detail": f"Hammerschmidt ΔT={station_utilities['power_gas']['methanol_dehydrator']['hammerschmidt_depression_c']} °C · 1\" drop + 1/2\" SS tubing"},
                    {"param": "utility_gas_demand_sm3h", "label": "Kullanım Gazı Skidi (Özel §4.8.6 / 4500 §9)", "value": station_utilities["utility_gas"]["calculated_demand_sm3h"], "unit": "Sm³/h (Min 1485)", "source": "station_3d_calc", "origin_detail": "Gas Cooler giriş çekişi · Double-pipe + Harici MCC Elektrikli Isıtıcı + Odorizer + 2×100% PRV + PE hat"},
                    {"param": "compressed_air_spec", "label": "Enstrüman Havası & ASME/CE Tank (4320/4330)", "value": f"{station_utilities['compressed_air']['demand_nm3h']} Nm³/h · {station_utilities['compressed_air']['receiver_volume_m3']} m³", "unit": "-40 °C Çiy Noktası", "source": "station_3d_calc", "origin_detail": f"1+1 VFD Eş-Yaşlandırma · Heatless Desikant Kurutucu · ≥10 dk holdup ({station_utilities['compressed_air']['holdup_time_min']} dk) · ≥304 SS"},
                    {"param": "heating_glycol_kw", "label": "Isıtma Sistemi (4500 §11 · 90/70 °C Glikol)", "value": station_utilities["heating_glycol"]["heat_load_kw"], "unit": "kWth", "source": "station_3d_calc", "origin_detail": "2×70% Gaz Kazanı · 3×50% İnline Pompa · %50/%50 Etilen Glikol-Su"},
                    {"param": "relief_bdv_bypass_4500", "label": "PSV/BDV (≥35 m / ≤60 s), Loading & Bypass (§5.9-5.13)", "value": "PSV ≥35m · BDV 1 barg/60s · Check Bypass", "unit": "Spec 4500", "source": "fixed_default", "origin_detail": "Dual-Outlet PSV (2\" pilot) · Gas-over-Oil Plug BDV · Suction MOV Loading · Ana Hat Non-Slam Check Bypass"},
                ],
            },
            {
                "key": "station_recycle",
                "tag": "PCV-101 / ASV",
                "name": "İstasyon Recycle & Ünite Anti-Surge Kontrol Vanaları",
                "parameters": [
                    {"param": "upstream_pressure_bar", "label": "Vana Giriş Basıncı", "value": round(p_out, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Çıkış Basıncı (p_out)"},
                    {"param": "downstream_pressure_bar", "label": "Vana Çıkış Basıncı", "value": round(max(p_in, p_comp_inlet), 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Giriş Basıncı (p_in)"},
                    {"param": "inlet_temp_c", "label": "Sıcak Gaz Giriş Sıcaklığı", "value": t_cooler_inlet_c, "unit": "°C", "source": "station_3d_calc", "origin_detail": "Kompresör Çıkış Sıcaklığı"},
                    {"param": "surge_ratio", "label": "ASV Surge Sınır Debi Oranı", "value": 0.68, "unit": "oran", "source": "fixed_default", "origin_detail": "Sabit Default API 617 %68 ünite debisi oranı"},
                    {"param": "pcv_cv", "label": "PCV / ASV IEC 60534 Cv & Çap", "value": (pcv_sizing or {}).get("valve_inch", "-"), "unit": "NPS", "source": "station_3d_calc", "origin_detail": "ControlValveAdapter IEC 60534-2-1 gerçek gaz hesabı"},
                ],
            },
            {
                "key": "safety_relief_psv",
                "tag": "PSV-101..N",
                "name": "Emniyet Tahliye Vanaları (API 520 / API 526)",
                "parameters": [
                    {"param": "p_upstream_bar", "label": "Korunan Hat Basıncı (p_out)", "value": round(p_out, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Çıkış Basıncı"},
                    {"param": "t_relieving_c", "label": "Tahliye Gaz Sıcaklığı", "value": t_cooler_inlet_c, "unit": "°C", "source": "station_3d_calc", "origin_detail": "Kompresör Çıkış Sıcaklığı"},
                    {"param": "mass_flow_total_kgs", "label": "Bloke Çıkış Tahliye Debisi", "value": round(mass_flow_kgs, 2), "unit": "kg/s", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Toplam İstasyon Debisi"},
                    {"param": "ambient_pressure_bar", "label": "Atmosferik Basınç (P_atm)", "value": round(p_atm_bar, 5), "unit": "bar(a)", "source": p_atm_src, "origin_detail": "Tasarım Sekmesi Saha & Çevre Şartları (ambient_pressure / rakım)"},
                    {"param": "ambient_temp_c", "label": "Atmosferik Ortam Sıcaklığı (T_atm)", "value": round(ambient_temp_c, 1), "unit": "°C", "source": t_amb_src, "origin_detail": "Tasarım Sekmesi Saha & Çevre Şartları (ambient_temp)"},
                    {"param": "psv_set_pressure_bar", "label": "PSV Set Basıncı", "value": psv_set_pressure_bar, "unit": "bar(g)", "source": "user_input" if _has_explicit_value(inputs, "psv_set_pressure_bar") else "station_3d_calc", "origin_detail": "3D HUD Kullanıcı Girişi (girilmezse 1.10 × (p_out − P_atm))"},
                    {"param": "psv_back_pressure_bar", "label": "PSV Karşı Basıncı", "value": psv_back_pressure_bar, "unit": "bar(a)", "source": "user_input" if psv_back_user_override else p_atm_src, "origin_detail": "Tasarım Sekmesi Atmosferik Basıncı P_atm (veya 3D HUD kullanıcı override)"},
                    {"param": "psv_overpressure_pct", "label": "Aşırı Basınç Oranı", "value": psv_overpressure_pct, "unit": "%", "source": "user_input" if _has_explicit_value(inputs, "psv_overpressure_pct") else "fixed_default", "origin_detail": "3D HUD Kullanıcı Girişi (yoksa %10 API 520 default)"},
                    {"param": "selected_orifice", "label": "Seçilen API 526 Orifis & Flanş", "value": (psv_sizing or {}).get("selected_orifice", "-"), "unit": "API 526", "source": "station_3d_calc", "origin_detail": "PSVAdapter API 520 Part I kritik/alt-kritik gerçek gaz orifis hesabı"},
                ],
            },
            {
                "key": "esd_blowdown_valves",
                "tag": "ESD / BDV-101..N",
                "name": "Acil Kapatma & Envanter Boşaltma (Blowdown) Vanaları",
                "parameters": [
                    {"param": "esd_hp_volume_m3", "label": "Boşaltılacak Yüksek Basınç Borulama Hacmi", "value": round(esd_hp_volume_m3, 2), "unit": "m³", "source": "user_input" if esd_hp_user_override else "fixed_default", "origin_detail": "3D Sekmesi Kullanıcı Girişi (girilmezse 50.0 m³ default)"},
                    {"param": "esd_lp_volume_m3", "label": "Boşaltılacak Düşük Basınç Borulama Hacmi", "value": round(esd_lp_volume_m3, 2), "unit": "m³", "source": "user_input" if esd_lp_user_override else "fixed_default", "origin_detail": "3D Sekmesi Kullanıcı Girişi (girilmezse 40.0 m³ default)"},
                    {"param": "hp_upstream_pressure_bar", "label": "Yüksek Basınç (Kompresör Çıkış Basıncı)", "value": round(p_out, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Çıkış Basıncı (p_out)"},
                    {"param": "lp_upstream_pressure_bar", "label": "Düşük Basınç (Kompresör Giriş Basıncı)", "value": round(p_in, 2), "unit": "bar(a)", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Kompresör Giriş Basıncı (p_in)"},
                    {"param": "ambient_pressure_bar", "label": "Atmosferik Basınç (P_atm)", "value": round(p_atm_bar, 5), "unit": "bar(a)", "source": p_atm_src, "origin_detail": "Tasarım Sekmesi Saha & Çevre Şartları (ambient_pressure / rakım)"},
                    {"param": "ambient_temp_c", "label": "Atmosferik Ortam Sıcaklığı (T_atm)", "value": round(ambient_temp_c, 1), "unit": "°C", "source": t_amb_src, "origin_detail": "Tasarım Sekmesi Saha & Çevre Şartları (ambient_temp)"},
                    {"param": "bdv_depressurization_time_min", "label": "Hedef Boşaltma Süresi", "value": bdv_depressurization_time_min, "unit": "dk", "source": "user_input" if _has_explicit_value(inputs, "bdv_depressurization_time_min") else "fixed_default", "origin_detail": "3D HUD Kullanıcı Girişi (girilmezse API 521 15.0 dk default)"},
                    {"param": "hp_calculated_size_in", "label": "YB Boşaltma Vanası Hesaplanan Çap", "value": f"{(esd_discharge or {}).get('calculated_size_in', '-')}\"", "unit": "inç", "source": "station_3d_calc", "origin_detail": "API 521 hacim boşaltma debisi + IEC 60534 sonik gaz Cv hesabı"},
                    {"param": "lp_calculated_size_in", "label": "DB Boşaltma Vanası Hesaplanan Çap", "value": f"{(esd_suction or {}).get('calculated_size_in', '-')}\"", "unit": "inç", "source": "station_3d_calc", "origin_detail": "API 521 hacim boşaltma debisi + IEC 60534 sonik gaz Cv hesabı"},
                ],
            },
            {
                "key": "ultrasonic_meter",
                "tag": "FT-401",
                "name": "Ultrasonik Doğal Gaz Debimetresi (AGA-9)",
                "parameters": [
                    {"param": "nominal_size_in", "label": "Metre Gövde Çapı", "value": ultrasonic_meter_sizing["nominal_size_in"], "unit": "NPS", "source": "station_3d_calc", "origin_detail": "Station Discharge Header ortak çapından (L-109) türetilir"},
                    {"param": "pressure_bar_a", "label": "Ölçüm Basıncı", "value": ultrasonic_meter_sizing["pressure_bar_a"], "unit": "bar(a)", "source": "station_3d_calc", "origin_detail": "Gaz Soğutucu çıkış basıncı (p_out − ΔP_cooler)"},
                    {"param": "temperature_c", "label": "Ölçüm Sıcaklığı", "value": ultrasonic_meter_sizing["temperature_c"], "unit": "°C", "source": "station_3d_calc", "origin_detail": "Gaz Soğutucu çıkış sıcaklığı"},
                    {"param": "max_recommended_velocity_ms", "label": "AGA-9 Tavsiye Edilen Maks. Hız", "value": 25.0, "unit": "m/s", "source": "fixed_default", "origin_detail": "Sabit Default AGA Report No. 9 üst hız sınırı (25.0 m/s)"},
                ],
            },
            {
                "key": "condensate_system",
                "tag": "TK-101",
                "name": "Kondensat Toplama ve Depolama Tankı (Spec 5250 / DIN 6608)",
                "parameters": [
                    {"param": "mass_flow_kgs", "label": "İstasyon Gaz Debisi", "value": round(mass_flow_kgs, 2), "unit": "kg/s", "source": "design_tab", "origin_detail": "Tasarım Sekmesi Toplam İstasyon Debisi"},
                    {"param": "spec_5250_pump", "label": "Ex-Proof Dalgıç Pompa (Spec 5250 / 4190)", "value": f"{cond_pump_flow_m3h}±20% m³/h @ 5 m · {cond_pump_motor_kw} kW", "unit": "DIN 6608 / St37", "source": "station_3d_calc", "origin_detail": f"Spec 5250 ({standard_flow_sm3h} Sm³/h): baz {spec_5250_base_tank_m3} m³ · 15× blow-flask={min_15x_blowflask_m3} m³ · 2 bar hidrostatik test"},
                    {"param": "collection_tank_volume_m3", "label": "Kondensat Tank Hacmi", "value": condensate_tank_volume_m3, "unit": "m³", "source": "station_3d_calc", "origin_detail": "max(Spec 5250, 15× blow-flask, 2.5 gün depolama) dinamik tank hacmi"},
                ],
            },
            {
                "key": "pigging",
                "tag": "PIG-R / PIG-L",
                "name": "PIG Kovanları, Ana Hat Blok & İstasyon Yan Vanaları (4500 §5.4, §5.12–13)",
                "parameters": [
                    {"param": "dp_interlock_barg", "label": "ΔP Açılma Kilidi & Aktüatör", "value": "0.5–4.0 barg · Gas-over-Oil", "unit": "Spec 4500 §5.4", "source": "fixed_default", "origin_detail": "İstasyon yan vanaları Fail-Closed · Ana hat blok vanası Fail-Open · ≥%50 branşmanda scraper-barred tee"},
                    {"param": "loading_and_bypass", "label": "Loading Line & Station Bypass Check", "value": "Loading (Globe+Ball) · Non-Slam Check Bypass", "unit": "§5.12–§5.13", "source": "fixed_default", "origin_detail": "Suction MOV Loading baypası + Ana hat çapında soğutucu sonrası/USM öncesi Non-Slam Piston/Nozul çekvalf"},
                ],
            },
            {
                "key": "fire_water",
                "tag": "FW-101",
                "name": "Yangın Suyu, F&G Algılama & HVAC Sistemi (4500 §12–14)",
                "parameters": [
                    {"param": "tank_volume_m3", "label": "Yangın Suyu Depolama Tankı", "value": 300.0, "unit": "m³", "source": "fixed_default", "origin_detail": "NFPA 20 (1 Elektrikli + 1 Dizel + Jockey) · Çevre Ring Hidrant · Türbin kabini otomatik CO2"},
                ],
            },
            {
                "key": "spec_4500_piping_compliance",
                "tag": "4500 §5.1",
                "name": "Borulama Hidroliği, ANSI B31.3/B31.8 & Akustik Doğrulama",
                "parameters": [
                    {"param": "suction_equiv_length_m", "label": "Emiş Eşdeğer Boru Metrajı", "value": round(suction_equiv_length_m, 1), "unit": "m", "source": "user_input" if suct_len_user_override else "fixed_default", "origin_detail": "3D Sekmesi Kullanıcı Girişi (yoksa 120.0 m default eşdeğer uzunluk)"},
                    {"param": "discharge_equiv_length_m", "label": "Basma Eşdeğer Boru Metrajı", "value": round(discharge_equiv_length_m, 1), "unit": "m", "source": "user_input" if disch_len_user_override else "fixed_default", "origin_detail": "3D Sekmesi Kullanıcı Girişi (yoksa 150.0 m default eşdeğer uzunluk)"},
                    {"param": "suction_dp_piping_bar", "label": "Emiş Borulama ΔP (Scrubber Hariç)", "value": ((station_piping.get("spec_4500_compliance") or {}).get("suction_piping") or {}).get("dp_piping_bar"), "unit": "bar", "source": "station_3d_calc", "origin_detail": "Natural Gas Flow Calc 20-segment compressible Darcy-Weisbach + Churchill (sınır ≤ 1.0 bar)"},
                    {"param": "discharge_dp_piping_bar", "label": "Basma Borulama ΔP (Soğutucu Hariç)", "value": ((station_piping.get("spec_4500_compliance") or {}).get("discharge_piping") or {}).get("dp_piping_bar"), "unit": "bar", "source": "station_3d_calc", "origin_detail": "Sıcak+Soğuk 20-segment compressible Darcy-Weisbach + Churchill (sınır ≤ 0.5 bar)"},
                    {"param": "stress_b313_b318_pct_smys", "label": "B31.8 Çember Gerilmesi / B31.3 Sürdürülen", "value": ((station_piping.get("spec_4500_compliance") or {}).get("stress_b313_b318") or {}).get("b318_max_hoop_pct_smys"), "unit": "% SMYS", "source": "station_3d_calc", "origin_detail": "ASME B31.8 (P tasarım) + ANSI B31.3 (sürdürülen & ısıl gerilme + destek aralığı)"},
                    {"param": "acoustic_max_mach", "label": "Akustik Maks. Mach & FIV Mom. Akısı", "value": ((station_piping.get("spec_4500_compliance") or {}).get("acoustic_pulsation") or {}).get("max_mach"), "unit": "Ma", "source": "station_3d_calc", "origin_detail": "EOS ses hızı Mach + ρ·v² EI FIV + Strouhal vorteks taraması"},
                ],
            },
        ],
        "piping": piping_provenance,
    }

    return {
        "success": True,
        "warnings": station_warnings,
        "station_summary": {
            "total_mass_flow_kgs": round(mass_flow_kgs, 2),
            "volumetric_flow_mmscmd": round(vol_flow_mmscmd, 2),
            "suction_pressure_bar": round(p_in, 2),
            "discharge_pressure_bar": round(p_out, 2),
            "pressure_ratio": round(p_out / p_in, 2),
            "suction_temp_c": round(t_in, 1),
            "compressor_outlet_temp_c": t_cooler_inlet_c,
            "cooler_outlet_temp_c": round(t_target_pipeline, 1),
            "ambient_pressure_bar": round(p_atm_bar, 5),
            "ambient_pressure_kpa": ambient_pressure_kpa,
            "ambient_temp_c": round(ambient_temp_c, 2),
            "altitude_m": round(altitude_m, 1),
            "total_power_kw": round(total_power_kw, 1),
            "total_power_mw": round(total_power_kw / 1000.0, 2),
            "cooler_heat_duty_mw": heat_duty_mw,
            "gas_mw": round(mw, 2),
            "suction_density_kgm3": round(rho_suction, 2),
            "suction_z_factor": round(z_in_real, 4),
            "eos_model": eos_key,
            "max_pipe_velocity_limit_ms": round(max_velocity_ms, 2),
            "common_header_size_in": common_hdr_nps,
            "governing_header_key": gov_hdr_key,
            "mainline_pipe_size": p_lines["mainline_inlet"]["nominal_size_in"],
            "mainline_velocity_ms": p_lines["mainline_inlet"]["actual_velocity_ms"],
        },
        "equipment_sizing": {
            "cyclones": {
                **mfs_sizing,
                "configuration": f"{cyclone_op_count} Çalışan + 1 Yedek ({cyclone_total_count} x %{mfs_sizing['unit_capacity_pct']})",
                "inlet_pipe_size": p_lines["cyclone_branch"]["nominal_size_in"],
                "inlet_velocity_ms": p_lines["cyclone_branch"]["actual_velocity_ms"],
                "inlet_min_pipe_size": p_lines["cyclone_branch"]["velocity_min_nominal_in"],
                "inlet_min_diameter_ok": p_lines["cyclone_branch"]["meets_min_velocity_diameter"],
                "inlet_pipe_source": p_lines["cyclone_branch"]["diameter_source"],
                "outlet_pipe_size": p_lines["cyclone_outlet_branch"]["nominal_size_in"],
                "outlet_velocity_ms": p_lines["cyclone_outlet_branch"]["actual_velocity_ms"],
                "outlet_min_pipe_size": p_lines["cyclone_outlet_branch"]["velocity_min_nominal_in"],
                "outlet_min_diameter_ok": p_lines["cyclone_outlet_branch"]["meets_min_velocity_diameter"],
                "outlet_pipe_source": p_lines["cyclone_outlet_branch"]["diameter_source"],
            },
            "cartridge_filters": {
                **cfs_sizing,
                "configuration": f"{filter_op_count} Çalışan + 1 Yedek ({filter_total_count} x %{cfs_sizing['unit_capacity_pct']})",
                "inlet_pipe_size": p_lines["filter_branch"]["nominal_size_in"],
                "inlet_velocity_ms": p_lines["filter_branch"]["actual_velocity_ms"],
                "inlet_min_pipe_size": p_lines["filter_branch"]["velocity_min_nominal_in"],
                "inlet_min_diameter_ok": p_lines["filter_branch"]["meets_min_velocity_diameter"],
                "inlet_pipe_source": p_lines["filter_branch"]["diameter_source"],
                "outlet_pipe_size": p_lines["filter_outlet_branch"]["nominal_size_in"],
                "outlet_velocity_ms": p_lines["filter_outlet_branch"]["actual_velocity_ms"],
                "outlet_min_pipe_size": p_lines["filter_outlet_branch"]["velocity_min_nominal_in"],
                "outlet_min_diameter_ok": p_lines["filter_outlet_branch"]["meets_min_velocity_diameter"],
                "outlet_pipe_source": p_lines["filter_outlet_branch"]["diameter_source"],
            },
            "turbo_compressors": {
                "operating_count": comp_op_count,
                "standby_count": max(0, comp_total_count - comp_op_count),
                "installed_count": comp_total_count,
                "configuration": f"{comp_op_count} Çalışan + 1 Yedek ({comp_total_count} x %{round(100.0 / comp_op_count)})",
                "flow_per_unit_kgs": flow_per_comp,
                "power_per_unit_kw": power_per_unit_kw,
                "power_per_unit_hp": round(power_per_unit_kw * 1.34102, 1),
                "polytropic_head_kj_kg": polytropic_head_kj,
                "polytropic_efficiency_pct": polytropic_eff,
                "discharge_temp_c": t_cooler_inlet_c,
                "suction_nozzle_size_in": f"{p_lines['comp_suction_branch']['nominal_size_in']} (başlık {p_lines['comp_suction_header']['nominal_size_in']} - Note 32)",
                "discharge_nozzle_size_in": f"{p_lines['comp_discharge_branch']['nominal_size_in']} (başlık {p_lines['unit_discharge_header']['nominal_size_in']} - Note 32)",
                "suction_velocity_ms": p_lines["comp_suction_branch"]["actual_velocity_ms"],
                "discharge_velocity_ms": p_lines["comp_discharge_branch"]["actual_velocity_ms"],
                "anti_surge_valve_size_in": int(p_lines["anti_surge_loop"]["nominal_key"]) if p_lines["anti_surge_loop"]["nominal_key"].isdigit() else asv_valve_size_in,
                "anti_surge_stroke_time_s": asv_stroke_time_s,
                "surge_limit_flow_kgs": surge_flow_limit,
                "anti_surge_valve_sizing": asv_sizing,
                "anti_surge_valve_warnings": asv_warnings,
                "unit_valves_and_strainer": comp_aux["unit_valves_and_strainer"],
                "dry_gas_seal": comp_aux["dry_gas_seal"],
                "fuel_gas_system": comp_aux["fuel_gas_system"],
                "lube_oil_system": comp_aux["lube_oil_system"],
                "air_intake_and_enclosure": comp_aux["air_intake_and_enclosure"],
                "design_warnings": comp_aux["design_warnings"],
            },
            "fuel_gas": {
                **comp_aux["fuel_gas_system"],
                "operating_units": comp_op_count,
                "installed_units": comp_total_count,
            },
            "compressor_building": {
                "width_m": shelter_width_m,
                "length_m": shelter_length_m,
                "height_m": shelter_height_m,
                "area_m2": round(shelter_width_m * shelter_length_m, 1),
                "crane_capacity_tons": comp_aux["crane_capacity_tons"],
                "acoustic_attenuation_dba": "≤ ISO NR 80 / 85 dBA @ 1m",
                "enclosure_max_temp_c": 80.0,
                "enclosure_ventilation_ups": True,
                "fire_and_gas_system": comp_aux["air_intake_and_enclosure"]["fire_and_gas"],
            },
            "air_coolers": {
                "bay_count": cooler_bays_count,
                "fans_per_bay": 2,
                "total_fans": cooler_bays_count * 2,
                "total_heat_duty_mw": heat_duty_mw,
                "inlet_temp_c": t_cooler_inlet_c,
                "outlet_temp_c": round(t_target_pipeline, 1),
                "requested_max_outlet_temp_c": round(cooler_max_outlet_temp_c, 1),
                "air_inlet_temp_c": round(cooler_air_temp_c, 1),
                "air_outlet_temp_c": round(cooler_air_out_c, 1),
                "approach_temp_c": round(t_target_pipeline - cooler_air_temp_c, 1),
                "lmtd_c": round(cooler_lmtd_c, 2),
                "compressor_outlet_coupled": True,
                "pressure_drop_bar": dp_cooler,
                "tube_bundle": {
                    "allowable_dp_bar": cooler_bundle_spec["allowable_dp_bar"],
                    "tube_velocity_ms": cooler_bundle_spec["tube_velocity_ms"],
                    "reynolds": cooler_bundle_spec["reynolds"],
                    "tubes_per_row": cooler_bundle_spec["tubes_per_row"],
                    "tubes_per_bay": cooler_bundle_spec["tubes_per_bay"],
                    "tube_passes": cooler_bundle_spec["tube_passes"],
                    "tube_length_m": cooler_bundle_spec["tube_length_m"],
                    "tube_wall_bwg": cooler_bundle_spec["tube_wall_bwg"],
                    "nozzle_rating": cooler_bundle_spec["nozzle_rating"],
                },
                "draft_type": cooler_bundle_spec["draft_type"],
                "fan_blades_min": cooler_bundle_spec["fan_blades_min"],
                "max_fan_tip_speed_ms": cooler_bundle_spec["max_fan_tip_speed_ms"],
                "fan_motor_max_kw": cooler_bundle_spec["fan_motor_max_kw"],
                "noise_limit_150m_dba": cooler_bundle_spec["noise_limit_150m_dba"],
                "design_reference_ambient_c": cooler_bundle_spec["design_reference_ambient_c"],
                "max_design_gas_outlet_c": cooler_bundle_spec["max_design_gas_outlet_c"],
                "vfd_drive_spec": cooler_bundle_spec["vfd_drive_spec"],
                "vibration_switches": cooler_bundle_spec["vibration_switches"],
                "louver_and_sunshade": cooler_bundle_spec["louver_and_sunshade"],
                "isolation_and_drain": cooler_bundle_spec["isolation_and_drain"],
                "tcv_control_spec": cooler_bundle_spec["tcv_control_spec"],
                "inlet_header_pipe_size": p_lines["cooler_inlet"]["nominal_size_in"],
                "riser_pipe_size": p_lines["cooler_bay_risers"]["nominal_size_in"],
                "bay_inlet_header_pipe_size": p_lines["cooler_bay_inlet_header"]["nominal_size_in"],
                "bay_outlet_header_pipe_size": p_lines["cooler_bay_outlet_header"]["nominal_size_in"],
                "outlet_riser_pipe_size": p_lines["cooler_bay_outlet_risers"]["nominal_size_in"],
                "outlet_pipe_size": p_lines["cooler_outlet"]["nominal_size_in"],
                "detailed_design": air_cooler_design,
                "design_warnings": air_cooler_warnings,
                "cooler_bypass_valve_sizing": tcv_sizing,
                "cooler_bypass_warnings": tcv_warnings,
                "bypass_line": {
                    "pipe_size": p_lines["cooler_bypass"]["nominal_size_in"],
                    "control_valve": "TCV Termostatik ON/OFF Baypas · Gas-over-Oil Hidrolik · Fail-Open (4500 §5.14)",
                    "purpose": "VFD fan devir düşümüne rağmen aşırı soğuma durumunda sıcak gaz karışımı (sinyal kaybında fail-open)",
                },
            },
            "condensate_system": {
                "collection_tank_volume_m3": condensate_tank_volume_m3,
                "spec_5250_base_tank_m3": spec_5250_base_tank_m3,
                "min_15x_blowflask_m3": min_15x_blowflask_m3,
                "estimated_liquid_rate_m3h": liquid_condensate_rate_m3h,
                "design_standard": "DIN 6608 / St37 (Spec 5250)",
                "pump_flow_m3h": cond_pump_flow_m3h,
                "pump_head_m": 5.0,
                "pump_motor_kw": cond_pump_motor_kw,
                "pump_spec": "Dikey Dalgıç Ex-Proof Pompa (Spec 4190)",
                "hydrostatic_test_bar": 2.0,
                "coating": "İç sentetik kaplama + Dış kömür katranı epoksi (5420)",
                "instrumentation": "LI + LSL (pompa durdurma) + LSH (kontrol odası alarmı) + Alev tutuculu vent",
                "source_drains": "MFS/CFS Blow-Flask → Atmosferik Siklon (Oto/Man) + Kompresör Ünite Drenajları",
                "atmospheric_cyclone_separator": "Atmosferik Sıvı/Gaz Siklon Seperatörü + Flame Arrestor Vent + Seperatörler Arası Manuel Purge (4500 §5.2)",
                "vent_protection": "Flame Arrester Emniyetli Atmosferik Vent Bacası (Note 14)",
            },
            "safety_relief_and_blowdown": {
                "psv_count": psv_count,
                "psv_duty_count": psv_duty_count,
                "psv_set_pressure_bar": psv_set_pressure_bar,
                "psv_overpressure_pct": psv_overpressure_pct,
                "psv_back_pressure_bar": psv_back_pressure_bar,
                "psv_valve_type": psv_valve_type,
                "psv_pilot_supply": '2" Pilot Supply Hattı + Pulsasyon Snubber + Çift Çıkış + Field Test Connection + Önünde Küresel Vana (4500 §5.10 / Özel §5.4)',
                "ambient_pressure_bar": round(p_atm_bar, 5),
                "ambient_temp_c": round(ambient_temp_c, 2),
                "relief_capacity_pct": 100.0,
                "bdv_valves_count": esd_count,
                "bdv_valve_type": "Lubricated Flanged Plug Vana · Gas-over-Oil (1 s/inch) · Fail-Open · ESD Sonrası Manuel Kapama (4500 §5.11)",
                "depressurization_time_min": bdv_depressurization_time_min,
                "flare_vent_stack_height_m": 35.0,
                "psv_sizing": psv_sizing,
                "psv_sizing_warnings": psv_sizing_warnings,
                "auto_inputs": psv_auto_inputs,
                "input_contract": psv_input_contract,
                "missing_inputs": psv_missing_inputs,
            },
            "esd_sizing": {
                "esd_count": esd_count,
                "esd_duty_count": esd_duty_count,
                "valve_type": esd_valve_type,
                "allowable_dp_bar": esd_allowable_dp_bar,
                "depressurization_time_min": bdv_depressurization_time_min,
                "esd_hp_volume_m3": round(esd_hp_volume_m3, 2),
                "esd_lp_volume_m3": round(esd_lp_volume_m3, 2),
                "ambient_pressure_bar": round(p_atm_bar, 5),
                "ambient_temp_c": round(ambient_temp_c, 2),
                "suction": esd_suction,
                "discharge": esd_discharge,
                "auto_inputs": esd_auto_inputs,
                "input_contract": esd_input_contract,
                "missing_inputs": esd_missing_inputs,
                "warnings": esd_warnings,
            },
            "ultrasonic_meter": ultrasonic_meter_sizing,
            "pigging": {
                "mainline_nps": p_lines["mainline_inlet"]["nominal_size_in"],
                "receiver": pig_receiver_size,
                "launcher": pig_launcher_size,
                "signaller_type": "İntrusif Manyetik Pinger",
                "side_valves": "Tam Geçişli Block & Bleed Küresel Vana · Gas-over-Oil Aktüatör · Sinyal Kaybında Fail-Closed (4500 §5.4)",
                "mainline_block_valve": "Gas-over-Oil Aktüatör · Sinyal Kaybında Fail-Open (4500 §5.4)",
                "dp_interlock_barg": "0.5–4.0 barg ayarlanabilir fark basınç açılma kilidi",
                "scraper_barred_tees": True,
                "loading_line": "4500 §5.12: Suction MOV baypası (küresel + kapalı limit switch'li globe vana)",
                "station_bypass_check": "4500 §5.13: Ana hat çapında Suction–Discharge Non-Slam Piston/Nozul Çekvalf (Soğutucu sonrası, USM öncesi)",
            },
            "station_suction_valve": {
                "tag": "SV-IN",
                "name": "İstasyon Giriş Yan Vanası (Station Suction Side Valve)",
                "nominal_size": p_lines["suction_header"]["nominal_size_in"],
                "standard": "API 6D QSL 2 · Tam Geçişli Block & Bleed Küresel Vana",
                "actuator": "Gas-over-Oil Hidrolik Aktüatör (Çift Selenoid · S.C.S. / ESD)",
                "fail_action": "Sinyal / güç kaybında Fail-Closed (4500 §5.4)",
                "dp_interlock": "0.5–4.0 barg ayarlanabilir ΔP açılma kilidi (4500 §5.4)",
                "body_vent_class": "≥16\" gövde/mil/seat ventleri üzerinde 1500 Class küresel + sürgülü vana (Özel §5.4)",
                "scraper_barred_tee": True,
            },
            "station_discharge_valve": {
                "tag": "SV-OUT",
                "name": "İstasyon Çıkış Yan Vanası (Station Discharge Side Valve)",
                "nominal_size": p_lines["discharge_header"]["nominal_size_in"],
                "standard": "API 6D QSL 2 · Tam Geçişli Block & Bleed Küresel Vana",
                "actuator": "Gas-over-Oil Hidrolik Aktüatör (Çift Selenoid · S.C.S. / ESD)",
                "fail_action": "Sinyal / güç kaybında Fail-Closed (4500 §5.4)",
                "dp_interlock": "0.5–4.0 barg ayarlanabilir ΔP açılma kilidi (4500 §5.4)",
                "body_vent_class": "≥16\" gövde/mil/seat ventleri üzerinde 1500 Class küresel + sürgülü vana (Özel §5.4)",
                "scraper_barred_tee": True,
            },
            "mainline_block_valve": {
                "tag": "MLBV-101",
                "name": "Ana Hat Blok Vanası (Mainline Block Valve)",
                "nominal_size": p_lines["mainline_inlet"]["nominal_size_in"],
                "standard": "API 6D QSL 2 · Konsept 1-NGTL-0-CS-P-001-4000",
                "actuator": "Gas-over-Oil Hidrolik Aktüatör (S.C.S. / ESD)",
                "fail_action": "Sinyal kaybında Fail-Open (4500 §5.4)",
                "dp_interlock": "0.5–4.0 barg ayarlanabilir ΔP açılma kilidi (4500 §5.4)",
                "pit_installation": "Yeraltı vanalar vent & drenajlı vana çukurunda (Özel §5.4)",
            },
            "station_loading_line": {
                "tag": "LV-101 / LV-102",
                "name": "İstasyon Dolum Hattı ve Vanaları (Station Loading Line)",
                "installed_around": "station_suction_valve",
                "upstream_valve": "Flanşlı Küresel Vana (3\"+ redüktörlü · Özel §5.4)",
                "downstream_valve": "Flanşlı Globe Vana · Kapalı Limit Switch Alarmı (4500 §5.12)",
                "remote_control_ozel_5_4": True,
                "note": "4500 §5.12 manuel küresel + limit-switch globe; Özel §5.4 uzaktan kontrollü açma-kapama",
            },
            "station_bypass_valve": {
                "tag": "NRV-BP-101",
                "name": "İstasyon By-Pass Hattı ve Non-Slam Çekvalf",
                "nominal_size": p_lines["discharge_header"]["nominal_size_in"],
                "valve_type": "Piston veya Nozul Tipi Non-Slam Çekvalf (4500 §5.13)",
                "tie_in_location": "Station Discharge Header (Gaz Soğutucu sonrası, USM öncesi) ↔ Station Suction Header",
                "slam_retarder_required": False,
            },
            "station_recycle": {
                "pipe_size": p_lines["station_recycle"]["nominal_size_in"],
                "max_recirculation_capacity_kgs": station_recycle_capacity_kgs,
                "control_valve_type": "Kademeli Basınç Düşürücü Düşük Gürültülü Trim",
                "inline_check_valve_nrv": True,
                "power_gas_actuator_bottle": {
                    "dedicated_bottle": True,
                    "tubing_material": "316 SS",
                    "stroke_time_s": "20–30 s ayarlanabilir",
                    "fail_safe": "ESD / sinyal kaybında Fail-Closed",
                },
                "note13_purge_rack_separated": True,
                "pcv_sizing": pcv_sizing,
                "pcv_warnings": pcv_warnings,
            },
            "station_utilities": station_utilities,
        },
        "nodes": nodes,
        "pipe_flows": pipe_flows,
        "station_piping": station_piping,
        "parameter_sources": parameter_sources,
    }
