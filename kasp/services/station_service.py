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
from kasp.core.thermo import ThermoEngine
from kasp.core.units import UnitSystem
from kasp.services.pipe_sizing_service import PipeSizingService

logger = logging.getLogger(__name__)

_STATION_EOS_ALIASES = {
    "coolprop": "coolprop",
    "heos": "coolprop",
    "pr": "pr",
    "peng-robinson": "pr",
    "bwrs": "pr",
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
    if u_low in ("sm³/h", "sm3/h", "smâ³/h", "m3/h", "m³/h"):
        return "Sm³/h"
    if u_low in ("nm³/h", "nm3/h", "nmâ³/h"):
        return "Nm³/h"
    if u_low == "mmscfd":
        return "MMSCFD"
    if u_low == "mmscmd":
        return "MMSCMD"
    if u_low in ("kmol/h", "kgmol/h"):
        return "kmol/h"
    return u


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
    # 0. Parse Gas Composition, Molecular Weight, and Selected EOS FIRST
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

    # Pressures in bar(a) — use the shared unit system so bar(g) is converted correctly.
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

    try:
        p_in = UnitSystem.convert_pressure(raw_p_in, p_in_unit, "bar(a)")
    except Exception:
        p_in = raw_p_in
    try:
        p_out = UnitSystem.convert_pressure(raw_p_out, p_out_unit, "bar(a)")
    except Exception:
        p_out = raw_p_out

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

    # 2. Dynamic Cyclone Separator (Scrubber) Sizing
    unit_cap_cyclone = 22.0  # kg/s per cyclone vessel
    user_cyclone_op = inputs.get("cyclone_op_count") or inputs.get("cyclones_count")
    if user_cyclone_op:
        cyclone_op_count = max(1, min(12, int(user_cyclone_op)))
    else:
        cyclone_op_count = max(1, min(8, math.ceil(mass_flow_kgs / unit_cap_cyclone)))
    cyclone_total_count = cyclone_op_count + 1  # Standard N+1 sparing
    flow_per_cyclone = mass_flow_kgs / cyclone_op_count
    dp_cyclone = round(0.30 * (flow_per_cyclone / unit_cap_cyclone) ** 1.8, 3)  # bar drop
    p_post_cyclone = round(max(0.5, p_in - dp_cyclone), 2)

    # 3. Dynamic Cartridge Coalescing Filter Sizing
    unit_cap_filter = 18.0  # kg/s per filter vessel
    user_filter_op = inputs.get("filter_op_count") or inputs.get("filters_count")
    if user_filter_op:
        filter_op_count = max(1, min(12, int(user_filter_op)))
    else:
        filter_op_count = max(1, min(8, math.ceil(mass_flow_kgs / unit_cap_filter)))
    filter_total_count = filter_op_count + 1  # Standard N+1 sparing
    flow_per_filter = mass_flow_kgs / filter_op_count
    dp_filter = round(0.22 * (flow_per_filter / unit_cap_filter) ** 1.5, 3)
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

    unit_cap_comp = design_unit_cap if design_unit_cap and design_unit_cap > 0 else 35.0
    user_comp_op = inputs.get("comp_op_count") or inputs.get("operating_trains") or inputs.get("num_units")
    if user_comp_op:
        try:
            comp_op_count = max(1, min(8, int(user_comp_op)))
        except (TypeError, ValueError):
            comp_op_count = max(1, min(6, math.ceil(mass_flow_kgs / unit_cap_comp)))
    else:
        comp_op_count = max(1, min(6, math.ceil(mass_flow_kgs / unit_cap_comp)))
    comp_total_count = comp_op_count + 1
    flow_per_comp = round(mass_flow_kgs / comp_op_count, 2)

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
    t_discharge_hot = max(t_in, min(350.0, t_discharge_hot))

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
        "ASV", surge_flow_limit, p_out, max(p_in, p_comp_inlet), t_discharge_hot
    )
    pcv_sizing, pcv_warnings = _size_control_valve(
        "PCV", station_recycle_capacity_kgs, p_out, max(p_in, p_comp_inlet), t_discharge_hot
    )

    # 6. Fin-Fan Gas Air Coolers Sizing (Real EOS Enthalpy Δh / Real Cp — NO hardcoded Cp=2.45)
    t_target_pipeline = 45.0
    dp_cooler = 0.40  # bar
    p_post_cooler = round(max(0.5, p_out - dp_cooler), 2)

    hot_state = _safe_eos_state(p_out, t_discharge_hot)
    cooled_state = _safe_eos_state(p_post_cooler, t_target_pipeline)

    if t_discharge_hot > t_target_pipeline:
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
            delta_h_kj_kg = cp_real * (t_discharge_hot - t_target_pipeline)
        heat_duty_mw = round(max(0.05, (mass_flow_kgs * delta_h_kj_kg) / 1000.0), 2)
    else:
        heat_duty_mw = 0.05

    cooler_bay_capacity_mw = 3.2
    user_cooler_bays = inputs.get("cooler_bays_count")
    if user_cooler_bays:
        cooler_bays_count = max(2, min(16, int(user_cooler_bays)))
    else:
        cooler_bays_count = max(2, min(8, math.ceil(heat_duty_mw / cooler_bay_capacity_mw)))

    air_cooler_design = None
    air_cooler_warnings = []
    include_air_cooler_design = bool(inputs.get("include_air_cooler_design", False))
    if include_air_cooler_design and t_discharge_hot > t_target_pipeline + 1.0:
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
                    "t_in_c": t_discharge_hot,
                    "t_out_c": t_target_pipeline,
                    "air_in_c": float(inputs.get("ambient_temp", 15.0) or 15.0),
                    "air_out_c": float(inputs.get("ambient_temp", 15.0) or 15.0) + 20.0,
                    "auto_size": True,
                }
            )
            air_cooler_design = design.get("results")
            air_cooler_warnings = list(design.get("warnings", []) or [])
        except BaseException as exc:
            air_cooler_warnings.append(f"Detaylı hava soğutucu tasarımı yapılamadı: {exc}")

    tcv_sizing, tcv_warnings = _size_control_valve(
        "TCV", mass_flow_kgs * 0.35, p_out, p_post_cooler, t_discharge_hot
    )
    cooler_bypass_valve_size_in = 16 if mass_flow_kgs < 60.0 else 24

    # 7. Safety & Depressurization (PSV & Blowdown) with Real EOS Z, MW, k
    psv_set_pressure_bar = round(p_out * 1.10, 1)
    psv_count = 2
    bdv_depressurization_time_min = 15.0

    psv_sizing = None
    psv_sizing_warnings = []
    try:
        from kasp.integrations.psv.adapter import PSVAdapter

        p_relieve_bar = psv_set_pressure_bar * 1.10
        relieve_state = _safe_eos_state(p_relieve_bar, t_discharge_hot) or hot_state
        psv_payload: Dict[str, Any] = {
            "service": "gas",
            "p1_bar": p_relieve_bar,
            "p2_bar": 1.01325,
            "t_c": t_discharge_hot,
            "mass_flow_kgs": mass_flow_kgs,
            "valve_type": "conventional",
            "num_valves": 1,
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
        psv_sizing = psv_result.get("results", {})
        psv_sizing_warnings = list(psv_result.get("warnings", []) or [])
        if psv_sizing.get("Selected_Orifice_Letter") == "Multiple Valves Required":
            multi_msg = "Tek PSV orifisi (API 526 T) kapasitesi aşıldı; çoklu paralel PSV seçimi gereklidir."
            if multi_msg not in psv_sizing_warnings:
                psv_sizing_warnings.append(multi_msg)
        if psv_sizing.get("Required_Area_sqin") is not None:
            psv_sizing = {
                "required_area_sqin": psv_sizing.get("Required_Area_sqin"),
                "selected_orifice": psv_sizing.get("Selected_Orifice_Letter"),
                "selected_orifice_area_sqin": psv_sizing.get("Selected_Orifice_Area_sqin"),
                "orifice_loading_pct": psv_sizing.get("Orifice_Loading_Pct"),
                "flow_type": psv_sizing.get("Flow_Type"),
                "z_used": psv_payload.get("z"),
                "mw_used": psv_payload.get("mw"),
                "k_used": psv_payload.get("k"),
                "standard": (psv_result.get("provenance") or {}).get("standard"),
                "warnings": psv_sizing_warnings,
            }
    except BaseException as exc:
        psv_sizing_warnings.append(f"PSV ön boyutlandırma yapılamadı: {exc}")

    # 8. Condensate Drain Collection (BOTAŞ PFD Note 14 & 15)
    liquid_condensate_rate_m3h = round(0.008 * mass_flow_kgs, 3)
    condensate_tank_volume_m3 = round(max(10.0, liquid_condensate_rate_m3h * 24.0 * 2.5), 1)

    # 8. Mainline Pigging Units
    mainline_nps = 24 if mass_flow_kgs < 50 else (36 if mass_flow_kgs < 120 else 48)
    pig_receiver_size = f"{mainline_nps}\" x {mainline_nps + 4}\" Class 600"
    pig_launcher_size = f"{mainline_nps}\" x {mainline_nps + 4}\" Class 900"

    # 9. Process Nodes Matrix
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
            "temp_c": round(t_discharge_hot, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Yüksek Basınçlı Sıcak Gaz",
            "state_desc": f"{comp_op_count} aktif turbo-kompresör treni çıkışı",
            "color": "#ef4444",
        },
        {
            "id": "N06_DISCHARGE_HEADER",
            "name": "Basma Kolektörü (Discharge Header)",
            "pressure_bar": round(p_out - 0.05, 2),
            "temp_c": round(t_discharge_hot - 0.5, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Basma Kolektör Gazı",
            "state_desc": "Hava soğutucular ve ana recycle ayrım noktası",
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

    # 10. Dynamic Pipe Sizing & Natural Gas Flow Network (ASME B36.10M / API 5L / API RP 14E)
    station_piping = PipeSizingService.size_station_network(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_in,
        p_out_bar=p_out,
        t_in_c=t_in,
        t_discharge_c=t_discharge_hot,
        t_cooled_c=t_target_pipeline,
        comp_op_count=comp_op_count,
        cyclone_op_count=cyclone_op_count,
        filter_op_count=filter_op_count,
        cooler_bays_count=cooler_bays_count,
        gas_mw=mw,
        pipe_material=inputs.get("pipe_material", "API 5L X70"),
        design_factor_F=float(inputs.get("design_factor_F", 0.50)),
        pipe_standard=inputs.get("pipe_standard", "BOTAŞ"),
        psl_level=inputs.get("psl_level", "PSL2"),
        dp_cyclone_bar=dp_cyclone,
        dp_filter_bar=dp_filter,
        dp_cooler_bar=dp_cooler,
        gas_comp=gas_comp,
        eos_model=eos_key,
        thermo_solver=solver,
    )
    p_lines = station_piping["lines"]

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
    _add_warnings("ASV", asv_warnings)
    _add_warnings("PCV", pcv_warnings)
    _add_warnings("TCV", tcv_warnings)
    _add_warnings("Hava Soğutucu", air_cooler_warnings)
    _add_warnings("PSV", psv_sizing_warnings)
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
        "filter_branches": {
            "speed_factor": round(max(0.3, p_lines["filter_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["filter_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["filter_branch"]["nominal_size_in"],
            "dir": "down",
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

    return {
        "success": True,
        "warnings": station_warnings,
        "station_summary": {
            "total_mass_flow_kgs": round(mass_flow_kgs, 2),
            "volumetric_flow_mmscmd": round(vol_flow_mmscmd, 2),
            "suction_pressure_bar": round(p_in, 2),
            "discharge_pressure_bar": round(p_out, 2),
            "pressure_ratio": round(p_out / p_in, 2),
            "total_power_kw": round(total_power_kw, 1),
            "total_power_mw": round(total_power_kw / 1000.0, 2),
            "cooler_heat_duty_mw": heat_duty_mw,
            "gas_mw": round(mw, 2),
            "suction_density_kgm3": round(rho_suction, 2),
            "suction_z_factor": round(z_in_real, 4),
            "eos_model": eos_key,
            "mainline_pipe_size": p_lines["mainline_inlet"]["nominal_size_in"],
            "mainline_velocity_ms": p_lines["mainline_inlet"]["actual_velocity_ms"],
        },
        "equipment_sizing": {
            "cyclones": {
                "operating_count": cyclone_op_count,
                "installed_count": cyclone_total_count,
                "configuration": f"{cyclone_op_count} Çalışan + 1 Yedek",
                "flow_per_unit_kgs": round(flow_per_cyclone, 2),
                "pressure_drop_bar": dp_cyclone,
                "vessel_diameter_mm": 1200,
                "liquid_knockout_pct": 99.5,
                "inlet_pipe_size": p_lines["cyclone_branch"]["nominal_size_in"],
                "inlet_velocity_ms": p_lines["cyclone_branch"]["actual_velocity_ms"],
            },
            "cartridge_filters": {
                "operating_count": filter_op_count,
                "installed_count": filter_total_count,
                "configuration": f"{filter_op_count} Çalışan + 1 Yedek",
                "flow_per_unit_kgs": round(flow_per_filter, 2),
                "clean_dp_bar": dp_filter,
                "filter_efficiency_micron": "0.3 µm (%99.98)",
                "inlet_pipe_size": p_lines["filter_branch"]["nominal_size_in"],
                "inlet_velocity_ms": p_lines["filter_branch"]["actual_velocity_ms"],
            },
            "turbo_compressors": {
                "operating_count": comp_op_count,
                "installed_count": comp_total_count,
                "configuration": f"{comp_op_count} Çalışan + 1 Yedek ({comp_total_count} x %{round(100.0 / comp_op_count)})",
                "flow_per_unit_kgs": flow_per_comp,
                "power_per_unit_kw": power_per_unit_kw,
                "power_per_unit_hp": round(power_per_unit_kw * 1.34102, 1),
                "polytropic_head_kj_kg": polytropic_head_kj,
                "polytropic_efficiency_pct": polytropic_eff,
                "suction_nozzle_size_in": f"{p_lines['comp_suction_branch']['nominal_size_in']} (başlık {p_lines['comp_suction_header']['nominal_size_in']} - Note 32)",
                "discharge_nozzle_size_in": f"{p_lines['comp_discharge_branch']['nominal_size_in']} (başlık {p_lines['discharge_header']['nominal_size_in']} - Note 32)",
                "suction_velocity_ms": p_lines["comp_suction_branch"]["actual_velocity_ms"],
                "discharge_velocity_ms": p_lines["comp_discharge_branch"]["actual_velocity_ms"],
                "anti_surge_valve_size_in": int(p_lines["anti_surge_loop"]["nominal_key"]) if p_lines["anti_surge_loop"]["nominal_key"].isdigit() else asv_valve_size_in,
                "anti_surge_stroke_time_s": asv_stroke_time_s,
                "surge_limit_flow_kgs": surge_flow_limit,
                "anti_surge_valve_sizing": asv_sizing,
                "anti_surge_valve_warnings": asv_warnings,
            },
            "compressor_building": {
                "width_m": shelter_width_m,
                "length_m": shelter_length_m,
                "height_m": shelter_height_m,
                "area_m2": round(shelter_width_m * shelter_length_m, 1),
                "crane_capacity_tons": 15.0,
                "acoustic_attenuation_dba": "85 dBA @ 1m",
            },
            "air_coolers": {
                "bay_count": cooler_bays_count,
                "fans_per_bay": 2,
                "total_fans": cooler_bays_count * 2,
                "total_heat_duty_mw": heat_duty_mw,
                "inlet_temp_c": round(t_discharge_hot, 1),
                "outlet_temp_c": t_target_pipeline,
                "pressure_drop_bar": dp_cooler,
                "inlet_header_pipe_size": p_lines["cooler_inlet"]["nominal_size_in"],
                "riser_pipe_size": p_lines["cooler_bay_risers"]["nominal_size_in"],
                "outlet_pipe_size": p_lines["cooler_outlet"]["nominal_size_in"],
                "detailed_design": air_cooler_design,
                "design_warnings": air_cooler_warnings,
                "cooler_bypass_valve_sizing": tcv_sizing,
                "cooler_bypass_warnings": tcv_warnings,
                "bypass_line": {
                    "pipe_size": p_lines["cooler_bypass"]["nominal_size_in"],
                    "control_valve": "TCV Sıcaklık Kontrol Baypas Vanası (Note 17)",
                    "purpose": "VFD fan devir düşümüne rağmen aşırı soğuma durumunda sıcak gaz karışımı",
                },
            },
            "condensate_system": {
                "collection_tank_volume_m3": condensate_tank_volume_m3,
                "estimated_liquid_rate_m3h": liquid_condensate_rate_m3h,
                "source_drains": "Siklon Seperatör ve Kartuş Filtre LCV Seviye Kontrol Vanaları",
                "vent_protection": "Flame Arrester Emniyetli Atmosferik Vent Bacası (Note 14)",
            },
            "safety_relief_and_blowdown": {
                "psv_count": psv_count,
                "psv_set_pressure_bar": psv_set_pressure_bar,
                "relief_capacity_pct": 100.0,
                "bdv_valves_count": 2,
                "depressurization_time_min": bdv_depressurization_time_min,
                "flare_vent_stack_height_m": 35.0,
                "psv_sizing": psv_sizing,
                "psv_sizing_warnings": psv_sizing_warnings,
            },
            "pigging": {
                "mainline_nps": p_lines["mainline_inlet"]["nominal_size_in"],
                "receiver": pig_receiver_size,
                "launcher": pig_launcher_size,
                "signaller_type": "İntrusif Manyetik Pinger",
            },
            "station_recycle": {
                "pipe_size": p_lines["station_recycle"]["nominal_size_in"],
                "max_recirculation_capacity_kgs": station_recycle_capacity_kgs,
                "control_valve_type": "Kademeli Basınç Düşürücü Düşük Gürültülü Trim",
                "pcv_sizing": pcv_sizing,
                "pcv_warnings": pcv_warnings,
            },
        },
        "nodes": nodes,
        "pipe_flows": pipe_flows,
        "station_piping": station_piping,
    }
