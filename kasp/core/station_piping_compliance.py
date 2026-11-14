"""
Station Piping Hydraulics, ANSI B31.3 / ASME B31.8 Stress & Acoustic/Pulsation Compliance Engine.

Implements Technical Specification 4-NGTL 0-CS-M-002-4500 §5.1 verification by combining:
  - Multi-segment compressible Darcy-Weisbach + Churchill friction solver with
    Weymouth / Panhandle A / Panhandle B empirical cross-checks (adapted from Natural Gas Flow Calc)
  - ASME B31.8 pressure design (Barlow hoop %SMYS) + ANSI B31.3 sustained & thermal expansion checks
  - Mach / Kinetic Energy (rho * v^2) / Strouhal FIV-AIV acoustic & pulsation screening
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from kasp.core.pipe_sizing import (
    PIPE_MATERIALS,
    churchill_friction_factor,
    lee_gonzalez_eakin_viscosity,
)

GAS_CONSTANT_R = 8.314462
STD_PRESS_PA = 101325.0
STD_TEMP_K = 288.15


def _estimate_z_papay(p_bar: float, t_c: float, gas_mw: float) -> float:
    """Papay compressibility fallback when thermodynamic EOS solver is not supplied."""
    gamma_g = max(0.55, min(1.5, float(gas_mw or 18.2) / 28.9647))
    p_pc = 48.8 - 1.8 * gamma_g
    t_pc = 93.3 + 180.0 * gamma_g - 6.94 * (gamma_g ** 2)
    p_pr = max(0.01, float(p_bar) / max(10.0, p_pc))
    t_pr = max(0.5, (float(t_c) + 273.15) / max(100.0, t_pc))
    z = 1.0 - (3.52 * p_pr) / (10.0 ** (0.9813 * t_pr)) + (0.274 * (p_pr ** 2)) / (10.0 ** (0.8157 * t_pr))
    return max(0.35, min(1.25, z))

# Spec 4-NGTL 0-CS-M-002-4500 §5.1 Limits
SPEC_4500_REF = "4-NGTL 0-CS-M-002-4500 §5.1"
SPEC_MAX_SUCTION_DP_BAR = 1.0
SPEC_MAX_DISCHARGE_DP_BAR = 0.5
SPEC_MAX_VELOCITY_MS = 20.0
DEFAULT_SUCTION_EQUIV_LENGTH_M = 120.0
DEFAULT_DISCHARGE_EQUIV_LENGTH_M = 150.0


def single_phase_segment_loss(
    density: float,
    velocity: float,
    friction_factor: float,
    length_m: float,
    diameter_m: float,
) -> float:
    """Darcy-Weisbach segment pressure loss in bar (adapted from Natural Gas Flow Calc)."""
    if diameter_m <= 0.0 or length_m <= 0.0 or density <= 0.0 or velocity <= 0.0:
        return 0.0
    dp_pa = friction_factor * (length_m / diameter_m) * (0.5 * density * velocity * velocity)
    return dp_pa / 1e5


def compute_empirical_dp_crosscheck(
    mass_flow_kgs: float,
    p_in_bar: float,
    t_c: float,
    diameter_m: float,
    equiv_length_m: float,
    gas_mw: float,
    z_avg: float,
    reynolds: float,
) -> Dict[str, float]:
    """
    Compute Weymouth, Panhandle A & Panhandle B compressible ΔP cross-checks (bar)
    over an isothermal horizontal equivalent length.
    """
    if mass_flow_kgs <= 0.0 or p_in_bar <= 0.0 or diameter_m <= 0.0 or equiv_length_m <= 0.0:
        return {"weymouth": 0.0, "panhandle_a": 0.0, "panhandle_b": 0.0}

    t_k = max(120.0, t_c + 273.15)
    r_spec = GAS_CONSTANT_R / (max(2.0, gas_mw) / 1000.0)
    p1_pa = p_in_bar * 1e5
    z_safe = max(0.2, min(1.5, z_avg))
    re_safe = max(2500.0, reynolds)
    eff_sq = 0.92 ** 2  # standard pipeline efficiency E = 0.92

    # Fundamental compressible gas pressure-squared equation:
    # P1^2 - P2^2 = (16 * f_D * m_dot^2 * Z * R_spec * T * L) / (pi^2 * D^5)
    geom_factor = (
        16.0 * (mass_flow_kgs ** 2) * z_safe * r_spec * t_k * equiv_length_m
    ) / ((math.pi ** 2) * (diameter_m ** 5))

    def _dp_from_f(f_darcy: float) -> float:
        delta_p2 = max(0.0, f_darcy * geom_factor)
        p2_sq = max(STD_PRESS_PA ** 2, (p1_pa ** 2) - delta_p2)
        p2_pa = math.sqrt(p2_sq)
        return round(max(0.0, (p1_pa - p2_pa) / 1e5), 4)

    f_weymouth = 0.009407 / (diameter_m ** (1.0 / 3.0))
    f_pan_a = (0.085 * (re_safe ** -0.1461)) / eff_sq
    f_pan_b = (0.0147 * (re_safe ** -0.03922)) / eff_sq

    return {
        "weymouth": _dp_from_f(f_weymouth),
        "panhandle_a": _dp_from_f(f_pan_a),
        "panhandle_b": _dp_from_f(f_pan_b),
    }


def _fallback_gas_state(p_bar: float, t_c: float, gas_mw: float) -> Dict[str, float]:
    t_k = max(120.0, t_c + 273.15)
    mw_kg = max(2.0, gas_mw) / 1000.0
    r_spec = GAS_CONSTANT_R / mw_kg
    z = _estimate_z_papay(p_bar, t_c, gas_mw)
    rho = max(0.1, (p_bar * 1e5) / (max(0.2, z) * r_spec * t_k))
    mu = lee_gonzalez_eakin_viscosity(t_k, rho, gas_mw)
    k_isen = 1.29
    c_sound = math.sqrt(max(100.0, k_isen * z * r_spec * t_k))
    return {
        "density_kgm3": rho,
        "viscosity_pa_s": mu,
        "z_factor": z,
        "speed_of_sound_ms": c_sound,
        "isentropic_k": k_isen,
    }


def calculate_compressible_pipe_dp(
    mass_flow_kgs: float,
    p_in_bar: float,
    t_c: float,
    id_mm: float,
    equiv_length_m: float,
    gas_mw: float = 18.2,
    roughness_mm: float = 0.0457,
    num_segments: int = 20,
    eos_state_fn: Optional[Callable[[float, float], Dict[str, Optional[float]]]] = None,
) -> Dict[str, Any]:
    """
    Multi-segment compressible steady-state Darcy-Weisbach pressure drop solver
    (adapted from Natural Gas Flow Calc `calculate_pressure_drop`).

    Splits `equiv_length_m` into `num_segments` steps and updates real EOS gas density,
    viscosity, velocity, Mach number, and Churchill friction factor per segment.
    """
    d_m = max(1e-3, float(id_mm) / 1000.0)
    area_m2 = math.pi * (d_m ** 2) / 4.0
    rel_roughness = max(1e-7, float(roughness_mm) / 1000.0 / d_m)
    l_eq = max(0.1, float(equiv_length_m))
    n_seg = max(1, int(num_segments))
    dl = l_eq / n_seg

    def _query_state(p_b: float) -> Dict[str, float]:
        fb = _fallback_gas_state(p_b, t_c, gas_mw)
        if eos_state_fn is None:
            return fb
        try:
            eos_res = eos_state_fn(p_b, t_c) or {}
            rho_e = eos_res.get("density_kgm3")
            mu_e = eos_res.get("viscosity_pa_s")
            z_e = eos_res.get("z_factor")
            c_e = eos_res.get("speed_of_sound_ms")
            k_e = eos_res.get("isentropic_k")
            rho_v = float(rho_e) if rho_e and math.isfinite(float(rho_e)) and float(rho_e) > 0 else fb["density_kgm3"]
            mu_v = float(mu_e) if mu_e and math.isfinite(float(mu_e)) and float(mu_e) > 0 else lee_gonzalez_eakin_viscosity(max(120.0, t_c + 273.15), rho_v, gas_mw)
            z_v = float(z_e) if z_e and math.isfinite(float(z_e)) and float(z_e) > 0 else fb["z_factor"]
            c_v = float(c_e) if c_e and math.isfinite(float(c_e)) and float(c_e) > 0 else fb["speed_of_sound_ms"]
            k_v = float(k_e) if k_e and math.isfinite(float(k_e)) and float(k_e) > 0 else fb["isentropic_k"]
            return {
                "density_kgm3": rho_v,
                "viscosity_pa_s": mu_v,
                "z_factor": z_v,
                "speed_of_sound_ms": c_v,
                "isentropic_k": k_v,
            }
        except Exception:
            return fb

    p_curr = max(1.01325, float(p_in_bar))
    choked = False
    v_in = 0.0
    v_out = 0.0
    v_max = 0.0
    mach_in = 0.0
    mach_out = 0.0
    mach_max = 0.0
    rho_in = 0.0
    rho_out = 0.0
    c_sound_ref = 400.0
    re_last = 1.0e5
    f_last = 0.012
    z_sum = 0.0
    segs_done = 0

    for idx in range(n_seg):
        st = _query_state(p_curr)
        rho = st["density_kgm3"]
        mu = st["viscosity_pa_s"]
        c_s = st["speed_of_sound_ms"]
        z_v = st["z_factor"]
        vel = max(0.0, float(mass_flow_kgs)) / (rho * area_m2) if area_m2 > 0 else 0.0
        mach = vel / max(50.0, c_s)
        re = (rho * vel * d_m) / max(1e-7, mu)
        f_d = churchill_friction_factor(re, rel_roughness)
        dp_seg = single_phase_segment_loss(rho, vel, f_d, dl, d_m)

        if idx == 0:
            v_in = vel
            mach_in = mach
            rho_in = rho
            c_sound_ref = c_s
        v_out = vel
        mach_out = mach
        rho_out = rho
        v_max = max(v_max, vel)
        mach_max = max(mach_max, mach)
        re_last = re
        f_last = f_d
        z_sum += z_v
        segs_done += 1

        if mach >= 1.0 or (p_curr - dp_seg) <= 1.01325:
            p_curr = max(1.01325, p_curr - dp_seg)
            choked = True
            break
        p_curr -= dp_seg

    dp_total = max(0.0, float(p_in_bar) - p_curr)
    z_avg = z_sum / max(1, segs_done)
    empirical = compute_empirical_dp_crosscheck(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_in_bar,
        t_c=t_c,
        diameter_m=d_m,
        equiv_length_m=l_eq,
        gas_mw=gas_mw,
        z_avg=z_avg,
        reynolds=re_last,
    )

    return {
        "method": "compressible_darcy_weisbach_20seg",
        "equiv_length_m": round(l_eq, 1),
        "p_inlet_bar": round(float(p_in_bar), 3),
        "p_outlet_bar": round(p_curr, 3),
        "dp_total_bar": round(dp_total, 4),
        "velocity_in_ms": round(v_in, 2),
        "velocity_out_ms": round(v_out, 2),
        "velocity_max_ms": round(v_max, 2),
        "mach_inlet": round(mach_in, 4),
        "mach_outlet": round(mach_out, 4),
        "mach_max": round(mach_max, 4),
        "sonic_velocity_ms": round(c_sound_ref, 1),
        "rho_inlet_kgm3": round(rho_in, 2),
        "rho_outlet_kgm3": round(rho_out, 2),
        "reynolds": round(re_last, 0),
        "friction_factor": round(f_last, 5),
        "choked": choked,
        "empirical_dp_bar": empirical,
    }


def _resolve_material_props(pipe_material: str) -> Dict[str, Any]:
    raw_name = str(pipe_material or "API 5L X70")
    smys_val = PIPE_MATERIALS.get(raw_name, PIPE_MATERIALS.get("API 5L X70", 483.0))
    if isinstance(smys_val, dict):
        smys_mpa = float(smys_val.get("SMYS_MPa", 483.0))
        uts_mpa = float(smys_val.get("UTS_MPa", 570.0))
    else:
        smys_mpa = float(smys_val or 483.0)
        uts_mpa = max(smys_mpa + 85.0, smys_mpa * 1.18)
        try:
            from kasp.integrations.api5l.vendor.database import get_smys_info

            grade = raw_name.replace("API 5L ", "").strip()
            if grade.lower() in {"gr. b", "gr b", "grade b"}:
                grade = "GRADE B"
            info = get_smys_info(grade)
            if isinstance(info, dict):
                smys_mpa = float(info.get("yield_min_mpa") or smys_mpa)
                uts_mpa = float(info.get("tensile_min_mpa") or uts_mpa)
        except Exception:
            pass
    is_ss = any(tok in raw_name.upper() for tok in ("304", "316", "SS", "DUPLEX"))
    return {
        "smys_mpa": smys_mpa,
        "uts_mpa": uts_mpa,
        "b313_allowable_s_mpa": min(smys_mpa * (2.0 / 3.0), uts_mpa / 3.0),
        "youngs_modulus_mpa": 193000.0 if is_ss else 200000.0,
        "thermal_alpha_per_k": 16.5e-6 if is_ss else 11.7e-6,
    }


def evaluate_b313_b318_stress(
    segments: List[Dict[str, Any]],
    pipe_material: str,
    design_factor_F: float,
    t_install_c: float = 15.0,
    corrosion_allowance_mm: float = 0.0,
) -> Dict[str, Any]:
    """
    ASME B31.8 hoop pressure design + ANSI B31.3 sustained & thermal expansion stress check.
    Returns governing values across the evaluated header segments.
    """
    mat = _resolve_material_props(pipe_material)
    smys = mat["smys_mpa"]
    s_allow_b313 = mat["b313_allowable_s_mpa"]
    e_mpa = mat["youngs_modulus_mpa"]
    alpha = mat["thermal_alpha_per_k"]
    f_b318 = max(0.30, min(0.80, float(design_factor_F or 0.50)))
    s_hoop_limit_b318 = smys * f_b318

    segment_results: List[Dict[str, Any]] = []
    max_hoop_pct_smys = 0.0
    max_sustained_ratio_pct = 0.0
    max_thermal_ratio_pct = 0.0
    worst_sustained_mpa = 0.0
    worst_thermal_mpa = 0.0
    worst_hoop_mpa = 0.0
    min_recommended_span_m = 12.0
    all_b318_ok = True
    all_b313_ok = True

    for seg in segments:
        p_des_bar = float(seg.get("p_design_bar") or 82.5)
        t_des_c = float(seg.get("t_design_c") if seg.get("t_design_c") is not None else 45.0)
        od_mm = max(20.0, float(seg.get("od_mm") or 508.0))
        wall_mm = max(2.0, float(seg.get("wall_thickness_mm") or 14.3))
        rho_gas = max(1.0, float(seg.get("rho_kgm3") or 40.0))
        t_min_std = seg.get("minimum_standard_thickness_mm")
        tol_pct_raw = seg.get("mill_tolerance_pct")
        if t_min_std is not None and float(t_min_std) > 0:
            t_net_mm = max(1.0, float(t_min_std) - corrosion_allowance_mm)
        else:
            tol_pct = float(tol_pct_raw) if tol_pct_raw is not None else 0.0
            t_net_mm = max(1.0, wall_mm * (1.0 - tol_pct / 100.0) - corrosion_allowance_mm)
        p_mpa = max(0.1, p_des_bar / 10.0)

        # B31.8 Barlow hoop stress at net wall thickness
        t_req_b318 = (p_mpa * od_mm) / (2.0 * s_hoop_limit_b318) + corrosion_allowance_mm
        s_hoop = (p_mpa * od_mm) / (2.0 * t_net_mm)
        pct_smys = (s_hoop / smys) * 100.0
        b318_seg_ok = (s_hoop <= s_hoop_limit_b318 * 1.001) and (wall_mm >= t_req_b318)

        # Recommended support spacing so bending stress <= 25% of B31.3 basic allowable S_h
        od_m = od_mm / 1000.0
        id_m = max(0.01, (od_mm - 2.0 * wall_mm) / 1000.0)
        area_steel = math.pi * (od_m ** 2 - id_m ** 2) / 4.0
        area_gas = math.pi * (id_m ** 2) / 4.0
        weight_per_m_n = (area_steel * 7850.0 + area_gas * rho_gas) * 9.81
        i_m4 = math.pi * (od_m ** 4 - id_m ** 4) / 64.0
        z_pipe_m3 = i_m4 / (od_m / 2.0)

        target_bend_pa = 0.25 * s_allow_b313 * 1e6
        l_span_calc = math.sqrt(max(1.0, (12.0 * z_pipe_m3 * target_bend_pa) / max(10.0, weight_per_m_n)))
        l_span_m = round(max(4.5, min(11.0, l_span_calc)), 1)

        s_bend_mpa = ((weight_per_m_n * (l_span_m ** 2) / 12.0) / max(1e-8, z_pipe_m3)) / 1e6
        s_lp_mpa = (p_mpa * od_mm) / (4.0 * t_net_mm)
        s_sustained_mpa = s_lp_mpa + s_bend_mpa
        sustained_ratio_pct = (s_sustained_mpa / s_allow_b313) * 100.0

        # ANSI B31.3 §302.3.5 / §319 displacement stress range screen
        # Guided-cantilever / restrained thermal envelope vs S_A = 1.5 * S_h
        delta_t = abs(t_des_c - t_install_c)
        s_a_mpa = 1.5 * s_allow_b313
        s_e_restrained_mpa = e_mpa * alpha * delta_t
        # With practical station L/U/Z expansion bends (~35% flexibility factor relative to rigidly anchored bar),
        # flag if even un-relieved thermal range exceeds 1.2 * S_A (requires dedicated expansion loop sizing)
        s_e_screen_mpa = 0.35 * s_e_restrained_mpa
        thermal_ratio_pct = (s_e_screen_mpa / s_a_mpa) * 100.0
        b313_seg_ok = (s_sustained_mpa <= s_allow_b313) and (s_e_screen_mpa <= s_a_mpa)

        all_b318_ok = all_b318_ok and b318_seg_ok
        all_b313_ok = all_b313_ok and b313_seg_ok
        max_hoop_pct_smys = max(max_hoop_pct_smys, pct_smys)
        max_sustained_ratio_pct = max(max_sustained_ratio_pct, sustained_ratio_pct)
        max_thermal_ratio_pct = max(max_thermal_ratio_pct, thermal_ratio_pct)
        worst_sustained_mpa = max(worst_sustained_mpa, s_sustained_mpa)
        worst_thermal_mpa = max(worst_thermal_mpa, s_e_screen_mpa)
        worst_hoop_mpa = max(worst_hoop_mpa, s_hoop)
        min_recommended_span_m = min(min_recommended_span_m, l_span_m)

        segment_results.append({
            "key": seg.get("key"),
            "tag": seg.get("tag"),
            "p_design_bar": round(p_des_bar, 2),
            "t_design_c": round(t_des_c, 1),
            "b318_t_req_mm": round(t_req_b318, 2),
            "b318_hoop_stress_mpa": round(s_hoop, 1),
            "b318_hoop_pct_smys": round(pct_smys, 1),
            "b313_sustained_stress_mpa": round(s_sustained_mpa, 1),
            "b313_thermal_stress_mpa": round(s_e_screen_mpa, 1),
            "b313_thermal_unrestrained_mpa": round(s_e_restrained_mpa, 1),
            "recommended_support_span_m": l_span_m,
            "b318_ok": b318_seg_ok,
            "b313_ok": b313_seg_ok,
        })

    return {
        "codes": "ANSI B31.3 (Process Stress) + ASME B31.8 (Pressure Design)",
        "pipe_material": pipe_material,
        "smys_mpa": round(smys, 1),
        "b318_design_factor_F": round(f_b318, 2),
        "b318_allowable_pct_smys": round(f_b318 * 100.0, 1),
        "b318_max_hoop_stress_mpa": round(worst_hoop_mpa, 1),
        "b318_max_hoop_pct_smys": round(max_hoop_pct_smys, 1),
        "b318_compliant": all_b318_ok,
        "b313_allowable_stress_mpa": round(s_allow_b313, 1),
        "b313_max_sustained_mpa": round(worst_sustained_mpa, 1),
        "b313_max_sustained_pct": round(max_sustained_ratio_pct, 1),
        "b313_max_thermal_mpa": round(worst_thermal_mpa, 1),
        "b313_allowable_thermal_sa_mpa": round(1.5 * s_allow_b313, 1),
        "b313_max_thermal_pct": round(max_thermal_ratio_pct, 1),
        "b313_compliant": all_b313_ok,
        "recommended_support_span_m": round(min_recommended_span_m, 1),
        "compliant": all_b318_ok and all_b313_ok,
        "segments": segment_results,
    }


def evaluate_acoustic_pulsation(
    line_checks: List[Dict[str, Any]],
    support_span_m: float = 7.0,
) -> Dict[str, Any]:
    """
    Acoustic / Pulsation / Flow-Induced Vibration (FIV) screening for station piping:
      - Mach number Ma = v / c_sound
      - Kinetic energy / momentum flux rho * v^2 (Energy Institute FIV screening)
      - Strouhal vortex shedding f_v vs pipe span natural frequency f_n,
        deriving required support spacing per line per 4-NGTL 0-CS-M-002-4500 §5.1.
    """
    max_mach = 0.0
    max_rho_v2 = 0.0
    max_velocity_ms = 0.0
    min_freq_ratio = 99.0
    min_required_span_m = 99.0
    governing_line = "-"
    flags: List[str] = []
    line_results: List[Dict[str, Any]] = []

    base_span = max(3.5, float(support_span_m or 7.0))

    for item in line_checks:
        tag = str(item.get("tag") or "-")
        vel = float(item.get("velocity_ms") or 0.0)
        rho = max(0.5, float(item.get("rho_kgm3") or 30.0))
        c_s = max(100.0, float(item.get("sonic_velocity_ms") or 400.0))
        od_m = max(0.02, float(item.get("od_mm") or 508.0) / 1000.0)
        id_m = max(0.01, float(item.get("id_mm") or 480.0) / 1000.0)

        mach = vel / c_s
        rho_v2 = rho * (vel ** 2)
        f_vortex = (0.20 * vel) / id_m if vel > 0.0 else 0.0

        # Beam stiffness coefficient for clamped/continuous rack span
        area_s = math.pi * (od_m ** 2 - id_m ** 2) / 4.0
        area_g = math.pi * (id_m ** 2) / 4.0
        mass_per_m = max(5.0, area_s * 7850.0 + area_g * rho)
        i_m4 = math.pi * (od_m ** 4 - id_m ** 4) / 64.0
        beam_coeff = (22.37 / (2.0 * math.pi)) * math.sqrt((2.0e11 * i_m4) / mass_per_m)

        # Practical support span bounded by B31.3 span and OD-proportional pipe-rack spacing (~12*OD max)
        od_span_cap = max(3.0, min(base_span, 16.0 * od_m))
        target_fn = max(2.0, 2.5 * f_vortex)
        max_nonresonant_span = math.sqrt(beam_coeff / target_fn) if f_vortex > 0.1 else od_span_cap
        design_span_m = round(max(2.0, min(od_span_cap, max_nonresonant_span)), 1)

        f_n = beam_coeff / (design_span_m ** 2)
        freq_ratio = (f_n / f_vortex) if f_vortex > 0.1 else 99.0

        if rho_v2 >= max_rho_v2:
            max_rho_v2 = rho_v2
            governing_line = tag
        max_mach = max(max_mach, mach)
        max_velocity_ms = max(max_velocity_ms, vel)
        min_freq_ratio = min(min_freq_ratio, freq_ratio)
        min_required_span_m = min(min_required_span_m, design_span_m)

        line_results.append({
            "tag": tag,
            "velocity_ms": round(vel, 2),
            "mach": round(mach, 4),
            "momentum_flux_pa": round(rho_v2, 0),
            "vortex_freq_hz": round(f_vortex, 2),
            "natural_freq_hz": round(f_n, 1),
            "freq_separation_ratio": round(min(99.0, freq_ratio), 2),
            "required_support_span_m": design_span_m,
        })

    if max_rho_v2 > 25000.0:
        fiv_risk = "Yüksek (High)"
        flags.append(
            f"Yüksek momentum akısı (ρ·v² = {max_rho_v2:.0f} Pa > 25,000 Pa, {governing_line}): "
            "4500 §5.1 gereği vortex spoiler, küçük çap branşman destekleme veya boru çapı büyütme değerlendirilmelidir."
        )
    elif max_rho_v2 > 5000.0:
        fiv_risk = "Orta (Moderate)"
    else:
        fiv_risk = "Düşük (Low)"

    if max_mach > 0.30:
        flags.append(
            f"Yüksek Mach sayısı (Ma = {max_mach:.3f} > 0.30): Akustik/AIV gürültü ve pulsasyon riski yüksek, akustik susturucu veya büyük NPS gereklidir."
        )

    if min_freq_ratio < 2.0 or min_required_span_m < 2.5:
        flags.append(
            f"Vorteks rezonans ayrım oranı kritik (f_n / f_v = {min_freq_ratio:.2f}, min span = {min_required_span_m:.1f} m): Destek aralığı sıkılaştırma veya vortex spoiler gerekir."
        )

    compliant = (max_mach <= 0.30) and (max_rho_v2 <= 25000.0) and (min_freq_ratio >= 2.0) and (min_required_span_m >= 2.5)

    return {
        "governing_tag": governing_line,
        "max_velocity_ms": round(max_velocity_ms, 2),
        "max_mach": round(max_mach, 4),
        "max_momentum_flux_pa": round(max_rho_v2, 0),
        "fiv_risk_level": fiv_risk,
        "min_freq_separation_ratio": round(min(99.0, min_freq_ratio), 2),
        "recommended_support_span_m": round(min_required_span_m, 1) if min_required_span_m < 90.0 else round(base_span, 1),
        "mitigation_notes": flags,
        "compliant": compliant,
        "lines": line_results,
    }


def evaluate_station_piping_compliance(
    lines: Dict[str, Dict[str, Any]],
    mass_flow_kgs: float,
    p_in_bar: float,
    p_out_bar: float,
    p_cooled_bar: float,
    t_in_c: float,
    t_discharge_c: float,
    t_cooled_c: float,
    gas_mw: float,
    pipe_material: str,
    design_factor_F: float,
    dp_cyclone_bar: float = 0.0,
    dp_filter_bar: float = 0.0,
    dp_cooler_bar: float = 0.0,
    suction_equiv_length_m: float = DEFAULT_SUCTION_EQUIV_LENGTH_M,
    discharge_equiv_length_m: float = DEFAULT_DISCHARGE_EQUIV_LENGTH_M,
    eos_state_fn: Optional[Callable[[float, float], Dict[str, Optional[float]]]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Evaluate full Technical Spec 4-NGTL 0-CS-M-002-4500 §5.1 piping compliance across the station network.
    Returns `(compliance_report_dict, warnings_list)`.
    """
    suct_hdr = lines.get("suction_header") or {}
    unit_disch_hdr = lines.get("unit_discharge_header") or {}
    disch_hdr = lines.get("discharge_header") or {}

    suct_len = max(1.0, float(suction_equiv_length_m or DEFAULT_SUCTION_EQUIV_LENGTH_M))
    disch_len = max(1.0, float(discharge_equiv_length_m or DEFAULT_DISCHARGE_EQUIV_LENGTH_M))

    suct_id_mm = float(suct_hdr.get("id_mm") or max(100.0, float(suct_hdr.get("od_mm", 660.4)) - 2.0 * float(suct_hdr.get("wall_thickness_mm", 14.3))))
    unit_disch_id_mm = float(unit_disch_hdr.get("id_mm") or suct_id_mm)
    disch_id_mm = float(disch_hdr.get("id_mm") or suct_id_mm)

    # 1. Suction piping ΔP (excluding scrubber: MFS cyclone + CFS filter)
    suction_hyd = calculate_compressible_pipe_dp(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_in_bar,
        t_c=t_in_c,
        id_mm=suct_id_mm,
        equiv_length_m=suct_len,
        gas_mw=gas_mw,
        eos_state_fn=eos_state_fn,
    )
    dp_scrubber_excl = max(0.0, float(dp_cyclone_bar or 0.0)) + max(0.0, float(dp_filter_bar or 0.0))
    suction_dp_piping = suction_hyd["dp_total_bar"]
    suction_dp_ok = (suction_dp_piping <= SPEC_MAX_SUCTION_DP_BAR) and (not suction_hyd["choked"])

    # 2. Discharge piping ΔP (excluding Gas Cooler):
    #    40% hot unit discharge piping + 60% cooled station discharge piping to PIG-L
    hot_len = max(0.5, 0.40 * disch_len)
    cold_len = max(0.5, 0.60 * disch_len)
    disch_hot_hyd = calculate_compressible_pipe_dp(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_out_bar,
        t_c=t_discharge_c,
        id_mm=unit_disch_id_mm,
        equiv_length_m=hot_len,
        gas_mw=gas_mw,
        eos_state_fn=eos_state_fn,
    )
    p_cold_start = max(1.01325, float(p_cooled_bar or (p_out_bar - float(dp_cooler_bar or 0.0))))
    disch_cold_hyd = calculate_compressible_pipe_dp(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_cold_start,
        t_c=t_cooled_c,
        id_mm=disch_id_mm,
        equiv_length_m=cold_len,
        gas_mw=gas_mw,
        eos_state_fn=eos_state_fn,
    )
    dp_cooler_excl = max(0.0, float(dp_cooler_bar or 0.0))
    disch_dp_piping = round(disch_hot_hyd["dp_total_bar"] + disch_cold_hyd["dp_total_bar"], 4)
    disch_dp_ok = (
        (disch_dp_piping <= SPEC_MAX_DISCHARGE_DP_BAR)
        and (not disch_hot_hyd["choked"])
        and (not disch_cold_hyd["choked"])
    )

    # 3. Spec 4500 §5.1 Velocity check (<= 20.0 m/s across headers & branches)
    worst_vel_tag = "-"
    worst_vel_ms = 0.0
    lines_exceeding_20: List[str] = []
    for l_val in lines.values():
        v_act = float(l_val.get("actual_velocity_ms") or 0.0)
        tag = str(l_val.get("tag") or "-")
        if v_act > worst_vel_ms:
            worst_vel_ms = v_act
            worst_vel_tag = tag
        if v_act > SPEC_MAX_VELOCITY_MS + 1e-6:
            lines_exceeding_20.append(f"{tag} ({v_act:.2f} m/s)")
    velocity_ok = len(lines_exceeding_20) == 0

    # 4. ANSI B31.3 + ASME B31.8 stress & support span analysis
    stress_segments = [
        {
            "key": "suction_header",
            "tag": suct_hdr.get("tag", "L-102"),
            "p_design_bar": suct_hdr.get("design_pressure_bar", max(p_in_bar * 1.15, p_out_bar)),
            "t_design_c": t_in_c,
            "od_mm": suct_hdr.get("od_mm", 508.0),
            "wall_thickness_mm": suct_hdr.get("wall_thickness_mm", 14.3),
            "rho_kgm3": suct_hdr.get("density_kgm3", suction_hyd["rho_inlet_kgm3"]),
            "minimum_standard_thickness_mm": (suct_hdr.get("standard_recommendation") or {}).get("minimum_standard_thickness_mm"),
            "mill_tolerance_pct": (suct_hdr.get("standard_recommendation") or {}).get("tolerance_percent"),
        },
        {
            "key": "unit_discharge_header",
            "tag": unit_disch_hdr.get("tag", "L-109A"),
            "p_design_bar": unit_disch_hdr.get("design_pressure_bar", p_out_bar * 1.10),
            "t_design_c": t_discharge_c,
            "od_mm": unit_disch_hdr.get("od_mm", 508.0),
            "wall_thickness_mm": unit_disch_hdr.get("wall_thickness_mm", 14.3),
            "rho_kgm3": unit_disch_hdr.get("density_kgm3", disch_hot_hyd["rho_inlet_kgm3"]),
            "minimum_standard_thickness_mm": (unit_disch_hdr.get("standard_recommendation") or {}).get("minimum_standard_thickness_mm"),
            "mill_tolerance_pct": (unit_disch_hdr.get("standard_recommendation") or {}).get("tolerance_percent"),
        },
        {
            "key": "discharge_header",
            "tag": disch_hdr.get("tag", "L-109"),
            "p_design_bar": disch_hdr.get("design_pressure_bar", p_out_bar * 1.10),
            "t_design_c": t_cooled_c,
            "od_mm": disch_hdr.get("od_mm", 508.0),
            "wall_thickness_mm": disch_hdr.get("wall_thickness_mm", 14.3),
            "rho_kgm3": disch_hdr.get("density_kgm3", disch_cold_hyd["rho_inlet_kgm3"]),
            "minimum_standard_thickness_mm": (disch_hdr.get("standard_recommendation") or {}).get("minimum_standard_thickness_mm"),
            "mill_tolerance_pct": (disch_hdr.get("standard_recommendation") or {}).get("tolerance_percent"),
        },
    ]
    stress_report = evaluate_b313_b318_stress(
        segments=stress_segments,
        pipe_material=pipe_material,
        design_factor_F=design_factor_F,
    )

    # 5. Acoustic / Pulsation / FIV screening across main headers & compressor nozzles
    acoustic_inputs = [
        {
            "tag": suct_hdr.get("tag", "L-102"),
            "velocity_ms": max(float(suct_hdr.get("actual_velocity_ms") or 0.0), suction_hyd["velocity_max_ms"]),
            "rho_kgm3": suction_hyd["rho_inlet_kgm3"],
            "sonic_velocity_ms": suction_hyd["sonic_velocity_ms"],
            "od_mm": suct_hdr.get("od_mm", 508.0),
            "id_mm": suct_id_mm,
        },
        {
            "tag": unit_disch_hdr.get("tag", "L-109A"),
            "velocity_ms": max(float(unit_disch_hdr.get("actual_velocity_ms") or 0.0), disch_hot_hyd["velocity_max_ms"]),
            "rho_kgm3": disch_hot_hyd["rho_inlet_kgm3"],
            "sonic_velocity_ms": disch_hot_hyd["sonic_velocity_ms"],
            "od_mm": unit_disch_hdr.get("od_mm", 508.0),
            "id_mm": unit_disch_id_mm,
        },
        {
            "tag": disch_hdr.get("tag", "L-109"),
            "velocity_ms": max(float(disch_hdr.get("actual_velocity_ms") or 0.0), disch_cold_hyd["velocity_max_ms"]),
            "rho_kgm3": disch_cold_hyd["rho_inlet_kgm3"],
            "sonic_velocity_ms": disch_cold_hyd["sonic_velocity_ms"],
            "od_mm": disch_hdr.get("od_mm", 508.0),
            "id_mm": disch_id_mm,
        },
    ]
    for branch_key, ref_sonic in (
        ("comp_suction_branch", suction_hyd["sonic_velocity_ms"]),
        ("comp_discharge_branch", disch_hot_hyd["sonic_velocity_ms"]),
    ):
        br = lines.get(branch_key)
        if br:
            acoustic_inputs.append({
                "tag": br.get("tag", branch_key),
                "velocity_ms": float(br.get("actual_velocity_ms") or 0.0),
                "rho_kgm3": float(br.get("density_kgm3") or 35.0),
                "sonic_velocity_ms": ref_sonic,
                "od_mm": float(br.get("od_mm") or 406.4),
                "id_mm": float(br.get("id_mm") or 380.0),
            })

    acoustic_report = evaluate_acoustic_pulsation(
        line_checks=acoustic_inputs,
        support_span_m=stress_report["recommended_support_span_m"],
    )

    warnings: List[str] = []
    if not suction_dp_ok:
        warnings.append(
            f"Şartname {SPEC_4500_REF}: Emiş hattı borulama ΔP (scrubber hariç) sınırı aşıldı "
            f"({suction_dp_piping:.3f} bar > {SPEC_MAX_SUCTION_DP_BAR:.1f} bar, L_eq={suct_len:.0f} m)."
        )
    if not disch_dp_ok:
        warnings.append(
            f"Şartname {SPEC_4500_REF}: Basma hattı borulama ΔP (gaz soğutucu hariç) sınırı aşıldı "
            f"({disch_dp_piping:.3f} bar > {SPEC_MAX_DISCHARGE_DP_BAR:.1f} bar, L_eq={disch_len:.0f} m)."
        )
    if not velocity_ok:
        warnings.append(
            f"Şartname {SPEC_4500_REF}: Maks. gaz hızı 20.0 m/s sınırı aşıldı: {', '.join(lines_exceeding_20)}."
        )
    if not stress_report["compliant"]:
        warnings.append(
            f"Şartname {SPEC_4500_REF}: ANSI B31.3 / ASME B31.8 boru gerilme veya et kalınlığı kontrolü başarısız "
            f"(B31.8 %SMYS={stress_report['b318_max_hoop_pct_smys']}%, B31.3 S_L={stress_report['b313_max_sustained_mpa']} MPa)."
        )
    for note in acoustic_report["mitigation_notes"]:
        warnings.append(f"Şartname {SPEC_4500_REF} (Akustik/Pulsasyon): {note}")

    overall_compliant = (
        suction_dp_ok
        and disch_dp_ok
        and velocity_ok
        and stress_report["compliant"]
        and acoustic_report["compliant"]
    )

    report = {
        "spec_ref": SPEC_4500_REF,
        "engine_source": "Natural Gas Flow Calc Compressible 20-Seg Darcy-Weisbach + Churchill + Weymouth/Panhandle",
        "overall_compliant": overall_compliant,
        "suction_piping": {
            "equiv_length_m": round(suct_len, 1),
            "header_nps": suct_hdr.get("nominal_size_in"),
            "dp_piping_bar": suction_dp_piping,
            "limit_bar": SPEC_MAX_SUCTION_DP_BAR,
            "utilization_pct": round((suction_dp_piping / SPEC_MAX_SUCTION_DP_BAR) * 100.0, 1),
            "dp_excluded_scrubber_bar": round(dp_scrubber_excl, 3),
            "dp_total_with_scrubber_bar": round(suction_dp_piping + dp_scrubber_excl, 3),
            "mach_max": suction_hyd["mach_max"],
            "velocity_out_ms": suction_hyd["velocity_out_ms"],
            "empirical_dp_bar": suction_hyd["empirical_dp_bar"],
            "choked": suction_hyd["choked"],
            "compliant": suction_dp_ok,
        },
        "discharge_piping": {
            "equiv_length_m": round(disch_len, 1),
            "hot_header_nps": unit_disch_hdr.get("nominal_size_in"),
            "cold_header_nps": disch_hdr.get("nominal_size_in"),
            "dp_hot_segment_bar": disch_hot_hyd["dp_total_bar"],
            "dp_cold_segment_bar": disch_cold_hyd["dp_total_bar"],
            "dp_piping_bar": disch_dp_piping,
            "limit_bar": SPEC_MAX_DISCHARGE_DP_BAR,
            "utilization_pct": round((disch_dp_piping / SPEC_MAX_DISCHARGE_DP_BAR) * 100.0, 1),
            "dp_excluded_cooler_bar": round(dp_cooler_excl, 3),
            "dp_total_with_cooler_bar": round(disch_dp_piping + dp_cooler_excl, 3),
            "mach_max": max(disch_hot_hyd["mach_max"], disch_cold_hyd["mach_max"]),
            "empirical_hot_dp_bar": disch_hot_hyd["empirical_dp_bar"],
            "empirical_cold_dp_bar": disch_cold_hyd["empirical_dp_bar"],
            "choked": disch_hot_hyd["choked"] or disch_cold_hyd["choked"],
            "compliant": disch_dp_ok,
        },
        "velocity_check": {
            "limit_ms": SPEC_MAX_VELOCITY_MS,
            "max_actual_ms": round(worst_vel_ms, 2),
            "governing_tag": worst_vel_tag,
            "exceeding_lines": lines_exceeding_20,
            "compliant": velocity_ok,
        },
        "stress_b313_b318": stress_report,
        "acoustic_pulsation": acoustic_report,
    }

    return report, warnings
