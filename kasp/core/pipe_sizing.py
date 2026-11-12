"""
KASP Pipe Sizing & Natural Gas Flow Calculations Core Module (kasp/core/pipe_sizing.py)
Embedded from Natural Gas Flow Calc project with ASME B36.10M & API 5L Standards:
- ASME B36.10M Dimensions (1/8" to 80" nominal sizes)
- API 5L Pipe Steel Grades & Specified Minimum Yield Strength (SMYS)
- ASME B31.8 / API 5L Barlow's Equation for Minimum Required Wall Thickness
- Churchill (1977) Friction Factor & Colebrook-White correlation
- Lee-Gonzalez-Eakin (1966) Natural Gas Dynamic Viscosity
- API RP 14E Gas Flow Erosion Velocity Limit (v_e = C / sqrt(rho))
- Optimum Commercial Pipe Selector with Weight & Velocity Minimization
"""

import math
from typing import Dict, Any, List, Optional, Tuple

# Boru Malzemeleri ve SMYS (Specified Minimum Yield Strength - MPa)
PIPE_MATERIALS: Dict[str, float] = {
    "API 5L Grade B": 241.0,
    "API 5L X42": 290.0,
    "API 5L X52": 359.0,
    "API 5L X60": 414.0,
    "API 5L X65": 448.0,
    "API 5L X70": 483.0,
    "API 5L X80": 555.0,
    "ASTM A53 Grade B": 241.0,
    "ASTM A106 Grade B": 241.0,
    "ASTM A312 TP316L": 210.0,
    "ASTM A335 P11": 205.0,
}

# Boru Mutlak Pürüzlülük Değerleri (metre cinsinden - commercial steel eps = 0.0457 mm)
PIPE_ROUGHNESS: Dict[str, float] = {
    "API 5L Grade B": 0.0457e-3,
    "API 5L X42": 0.0457e-3,
    "API 5L X52": 0.0457e-3,
    "API 5L X60": 0.0457e-3,
    "API 5L X65": 0.0457e-3,
    "API 5L X70": 0.0457e-3,
    "API 5L X80": 0.0457e-3,
    "ASTM A53 Grade B": 0.0457e-3,
    "ASTM A106 Grade B": 0.0457e-3,
    "ASTM A312 TP316L": 0.0015e-3,
    "ASTM A335 P11": 0.0457e-3,
}

# Fitting K Direnç Faktörleri
FITTING_K_FACTORS: Dict[str, float] = {
    "90_elbow": 0.30,
    "45_elbow": 0.20,
    "180_return": 0.50,
    "tee_through": 0.40,
    "tee_branch": 1.50,
    "ball_valve_full": 0.05,
    "check_valve": 2.00,
    "gate_valve": 0.15,
}

# ASME B36.10M Standard Pipe Dimensions (OD_mm and schedule wall thicknesses in mm)
ASME_B36_10M_DATA: Dict[str, Dict[str, Any]] = {
    "1/8": {"OD_mm": 10.29, "schedules": {"10": 1.24, "30": 1.45, "STD": 1.73, "40": 1.73, "XS": 2.41, "80": 2.41, "160": 3.15, "XXS": 4.83}},
    "1/4": {"OD_mm": 13.72, "schedules": {"10": 1.65, "30": 1.85, "STD": 2.24, "40": 2.24, "XS": 3.02, "80": 3.02, "160": 3.68, "XXS": 6.05}},
    "3/8": {"OD_mm": 17.14, "schedules": {"10": 1.65, "30": 1.85, "STD": 2.31, "40": 2.31, "XS": 3.20, "80": 3.20, "160": 4.01, "XXS": 6.40}},
    "1/2": {"OD_mm": 21.34, "schedules": {"5": 1.65, "10": 2.11, "30": 2.41, "STD": 2.77, "40": 2.77, "XS": 3.73, "80": 3.73, "160": 4.78, "XXS": 7.47}},
    "3/4": {"OD_mm": 26.67, "schedules": {"5": 1.65, "10": 2.11, "30": 2.41, "STD": 2.87, "40": 2.87, "XS": 3.91, "80": 3.91, "160": 5.56, "XXS": 7.82}},
    "1": {"OD_mm": 33.40, "schedules": {"5": 1.65, "10": 2.77, "30": 2.90, "STD": 3.38, "40": 3.38, "XS": 4.55, "80": 4.55, "160": 6.35, "XXS": 9.09}},
    "1 1/4": {"OD_mm": 42.16, "schedules": {"5": 1.65, "10": 2.77, "30": 2.97, "STD": 3.56, "40": 3.56, "XS": 4.85, "80": 4.85, "160": 6.35, "XXS": 9.70}},
    "1 1/2": {"OD_mm": 48.26, "schedules": {"5": 1.65, "10": 2.77, "30": 3.18, "STD": 3.68, "40": 3.68, "XS": 5.08, "80": 5.08, "160": 7.14, "XXS": 10.16}},
    "2": {"OD_mm": 60.32, "schedules": {"5": 1.65, "10": 2.77, "30": 3.18, "STD": 3.91, "40": 3.91, "XS": 5.54, "80": 5.54, "160": 8.74, "XXS": 11.07}},
    "2 1/2": {"OD_mm": 73.02, "schedules": {"5": 2.11, "10": 2.77, "30": 4.78, "STD": 5.16, "40": 5.16, "XS": 7.01, "80": 7.01, "160": 9.52, "XXS": 14.02}},
    "3": {"OD_mm": 88.90, "schedules": {"5": 2.11, "10": 3.05, "30": 4.78, "STD": 5.49, "40": 5.49, "XS": 7.62, "80": 7.62, "160": 11.13, "XXS": 15.24}},
    "3 1/2": {"OD_mm": 101.60, "schedules": {"5": 2.11, "10": 3.05, "30": 4.78, "STD": 5.74, "40": 5.74, "XS": 8.08, "80": 8.08}},
    "4": {"OD_mm": 114.30, "schedules": {"5": 2.11, "10": 3.05, "30": 4.78, "STD": 6.02, "40": 6.02, "XS": 8.56, "80": 8.56, "120": 11.13, "160": 13.49, "XXS": 17.12}},
    "5": {"OD_mm": 141.30, "schedules": {"5": 2.77, "10": 3.40, "STD": 6.55, "40": 6.55, "XS": 9.52, "80": 9.52, "120": 12.70, "160": 15.88, "XXS": 19.05}},
    "6": {"OD_mm": 168.28, "schedules": {"5": 2.77, "10": 3.40, "STD": 7.11, "40": 7.11, "XS": 10.97, "80": 10.97, "120": 14.27, "160": 18.26, "XXS": 21.95}},
    "8": {"OD_mm": 219.08, "schedules": {"5": 2.77, "10": 3.76, "20": 6.35, "30": 7.04, "STD": 8.18, "40": 8.18, "60": 10.31, "XS": 12.70, "80": 12.70, "100": 15.09, "120": 18.26, "140": 20.62, "160": 23.01, "XXS": 22.22}},
    "10": {"OD_mm": 273.00, "schedules": {"5": 3.40, "10": 4.19, "20": 6.35, "30": 7.80, "STD": 9.27, "40": 9.27, "60": 12.70, "XS": 12.70, "80": 15.09, "100": 18.26, "120": 21.44, "140": 25.40, "160": 28.58, "XXS": 25.40}},
    "12": {"OD_mm": 323.80, "schedules": {"5": 3.96, "10": 4.57, "20": 6.35, "30": 8.38, "STD": 9.52, "40": 10.31, "60": 14.27, "XS": 12.70, "80": 17.48, "100": 21.44, "120": 25.40, "140": 28.58, "160": 33.32, "XXS": 25.40}},
    "14": {"OD_mm": 355.60, "schedules": {"5": 3.96, "10": 6.35, "20": 7.92, "30": 9.52, "STD": 9.52, "40": 11.13, "60": 15.09, "XS": 12.70, "80": 19.05, "100": 23.83, "120": 27.79, "140": 31.75, "160": 35.71}},
    "16": {"OD_mm": 406.40, "schedules": {"5": 4.19, "10": 6.35, "20": 7.92, "30": 9.52, "STD": 9.52, "40": 12.70, "60": 16.66, "XS": 12.70, "80": 21.44, "100": 26.19, "120": 30.96, "140": 36.53, "160": 40.49}},
    "18": {"OD_mm": 457.20, "schedules": {"10": 6.35, "20": 7.92, "30": 11.13, "STD": 9.52, "40": 14.27, "60": 19.05, "XS": 12.70, "80": 23.83, "100": 29.36, "120": 34.92, "140": 39.67, "160": 45.24}},
    "20": {"OD_mm": 508.00, "schedules": {"10": 6.35, "20": 9.52, "30": 12.70, "STD": 9.52, "40": 15.09, "60": 20.62, "XS": 12.70, "80": 26.19, "100": 32.54, "120": 38.10, "140": 44.45, "160": 50.01}},
    "22": {"OD_mm": 558.80, "schedules": {"10": 6.35, "20": 9.52, "30": 12.70, "STD": 9.52, "60": 22.22, "XS": 12.70, "80": 28.58, "100": 34.92, "120": 41.28, "140": 47.62, "160": 53.98}},
    "24": {"OD_mm": 609.60, "schedules": {"10": 6.35, "20": 9.52, "30": 14.27, "STD": 9.52, "40": 17.48, "60": 24.61, "XS": 12.70, "80": 30.96, "100": 38.89, "120": 46.02, "140": 52.37, "160": 59.54}},
    "26": {"OD_mm": 660.40, "schedules": {"10": 7.92, "20": 12.70, "STD": 9.52, "XS": 12.70, "30": 15.88, "40": 19.05}},
    "28": {"OD_mm": 711.20, "schedules": {"10": 7.92, "20": 12.70, "30": 15.88, "STD": 9.52, "XS": 12.70, "40": 19.05}},
    "30": {"OD_mm": 762.00, "schedules": {"5": 6.35, "10": 7.92, "20": 12.70, "30": 15.88, "STD": 9.52, "XS": 12.70, "40": 19.05, "60": 25.40}},
    "32": {"OD_mm": 813.00, "schedules": {"10": 7.92, "20": 12.70, "30": 15.88, "40": 17.48, "STD": 9.52, "XS": 12.70, "60": 25.40}},
    "34": {"OD_mm": 864.00, "schedules": {"10": 7.92, "20": 12.70, "30": 15.88, "40": 17.48, "STD": 9.52, "XS": 12.70}},
    "36": {"OD_mm": 914.00, "schedules": {"10": 7.92, "20": 12.70, "30": 14.27, "40": 19.05, "STD": 9.52, "XS": 12.70, "60": 25.40}},
    "38": {"OD_mm": 965.00, "schedules": {"STD": 9.52, "XS": 12.70, "10": 7.92, "20": 14.27, "30": 19.05}},
    "40": {"OD_mm": 1016.00, "schedules": {"STD": 9.52, "XS": 12.70, "10": 8.74, "20": 15.88, "30": 20.62}},
    "42": {"OD_mm": 1067.00, "schedules": {"STD": 9.52, "XS": 12.70, "10": 8.74, "20": 15.88, "30": 22.22}},
    "44": {"OD_mm": 1118.00, "schedules": {"STD": 9.52, "XS": 12.70, "10": 8.74, "20": 15.88, "30": 22.22}},
    "46": {"OD_mm": 1168.00, "schedules": {"STD": 9.52, "XS": 12.70, "10": 9.52, "20": 17.48, "30": 23.83}},
    "48": {"OD_mm": 1219.00, "schedules": {"STD": 9.52, "XS": 12.70, "10": 9.52, "20": 17.48, "30": 22.22, "40": 25.40, "60": 31.75}},
    "52": {"OD_mm": 1321.00, "schedules": {"STD": 9.52, "XS": 12.70, "20": 17.48, "30": 23.83, "40": 28.58}},
    "56": {"OD_mm": 1422.00, "schedules": {"STD": 9.52, "XS": 12.70, "20": 17.48, "30": 25.40, "40": 30.18}},
    "60": {"OD_mm": 1524.00, "schedules": {"STD": 9.52, "XS": 12.70, "20": 19.05, "30": 26.97, "40": 31.75}},
    "64": {"OD_mm": 1626.00, "schedules": {"STD": 9.52, "XS": 12.70, "20": 19.05, "30": 26.97, "40": 31.75}},
    "72": {"OD_mm": 1829.00, "schedules": {"STD": 12.70, "20": 20.62, "30": 28.58, "40": 34.92}},
    "80": {"OD_mm": 2032.00, "schedules": {"STD": 14.27, "20": 22.22, "30": 30.18, "40": 38.10}},
}


def nd_sort_key(nd_str: str) -> float:
    """Sort key for nominal pipe size strings (e.g. '1/8', '1 1/2', '48')."""
    try:
        s = nd_str.strip().replace('"', '')
        if " " in s:
            parts = s.split(" ")
            val = float(parts[0])
            if "/" in parts[1]:
                num, den = map(float, parts[1].split("/"))
                val += num / den
        elif "/" in s:
            num, den = map(float, s.split("/"))
            val = num / den
        else:
            val = float(s)
    except (ValueError, IndexError, ZeroDivisionError):
        val = 999.0
    return val


def calculate_pipe_weight_api5l(OD_mm: float, t_mm: float) -> float:
    """Calculates linear weight of steel pipe according to API 5L in kg/m: w = t * (OD - t) * 0.02466"""
    try:
        od = float(OD_mm)
        t = float(t_mm)
    except (TypeError, ValueError):
        return 0.0
    if t <= 0.0 or od <= t:
        return 0.0
    return round(t * (od - t) * 0.0246615, 2)


def churchill_friction_factor(Re: float, relative_roughness: float) -> float:
    """
    Computes Churchill (1977) friction factor valid across laminar, critical, and turbulent regimes.
    """
    if Re <= 0:
        return 0.02
    if Re < 2000.0:
        f_lam = 64.0 / max(640.0, float(Re)) if Re < 640.0 else 64.0 / Re
        return min(0.10, max(0.005, f_lam))
    try:
        rel_rough = max(0.0, float(relative_roughness))
        A = (2.457 * math.log(1.0 / ((7.0 / Re) ** 0.9 + 0.27 * rel_rough))) ** 16
        B = (37530.0 / Re) ** 16
        f = 8.0 * ((8.0 / Re) ** 12.0 + 1.0 / (A + B) ** 1.5) ** (1.0 / 12.0)
        return min(0.10, max(0.005, f))
    except (ValueError, OverflowError, ZeroDivisionError):
        return 0.015


def lee_gonzalez_eakin_viscosity(T_K: float, density_kg_m3: float, MW_g_mol: float) -> float:
    """
    Computes natural gas dynamic viscosity (Pa*s) using Lee, Gonzalez & Eakin (1966) correlation.
    """
    if density_kg_m3 <= 0 or T_K <= 0:
        return 1.1e-5
    T_R = T_K * 1.8
    rho_gcc = density_kg_m3 / 1000.0
    X = 3.5 + 986.0 / T_R + 0.01 * MW_g_mol
    Y = max(0.1, 2.4 - 0.2 * X)
    K = ((9.4 + 0.02 * MW_g_mol) * (T_R ** 1.5)) / (209.0 + 19.0 * MW_g_mol + T_R)
    try:
        visc_micropoise = K * math.exp(X * (rho_gcc ** Y))
        return visc_micropoise * 1e-7  # convert micropoise to Pa*s (1 P = 0.1 Pa*s, 1 uP = 1e-7 Pa*s)
    except (OverflowError, ValueError):
        return 1.2e-5


def calculate_erosion_velocity(density_kg_m3: float, C_empirical: float = 122.0) -> float:
    """
    API RP 14E Erosion Velocity limit: v_e = C / sqrt(rho)
    C = 122 for continuous solids-free gas service (or 100 for conservative design).
    """
    c_val = float(C_empirical) if C_empirical is not None and float(C_empirical) > 0 else 122.0
    if density_kg_m3 <= 0:
        return 25.0
    return round(c_val / math.sqrt(density_kg_m3), 2)


def get_sorted_pipes(
    P_design_pa: float,
    SMYS_mpa: float = 483.0,
    F: float = 0.50,
    E: float = 1.0,
    T: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Evaluates ASME B36.10M pipes and filters schedules that satisfy Barlow's minimum wall thickness:
    t_required = (P_design * OD) / (2 * SMYS * F * E * T)
    """
    smys_safe = max(50.0, float(SMYS_mpa)) if (SMYS_mpa is not None and float(SMYS_mpa) > 0) else 483.0
    F_safe = max(0.10, min(1.0, float(F))) if (F is not None and float(F) > 0) else 0.50
    E_safe = max(0.50, min(1.0, float(E))) if (E is not None and float(E) > 0) else 1.0
    T_safe = max(0.50, min(1.0, float(T))) if (T is not None and float(T) > 0) else 1.0

    SMYS_pa = smys_safe * 1e6
    denom = 2.0 * SMYS_pa * F_safe * E_safe * T_safe
    p_des = max(0.0, float(P_design_pa)) if P_design_pa is not None else 1e5
    valid_pipes = []

    for nominal, data in ASME_B36_10M_DATA.items():
        OD_mm = data["OD_mm"]
        OD_m = OD_mm / 1000.0
        t_req_mm = (p_des * OD_m / denom) * 1000.0

        for schedule, t_mm in data["schedules"].items():
            if t_mm >= t_req_mm:
                D_inner_mm = OD_mm - 2.0 * t_mm
                if D_inner_mm > 0:
                    valid_pipes.append({
                        "nominal": nominal,
                        "nominal_float": nd_sort_key(nominal),
                        "OD_mm": OD_mm,
                        "schedule": schedule,
                        "t_mm": t_mm,
                        "D_inner_mm": round(D_inner_mm, 2),
                        "t_required_mm": round(t_req_mm, 2),
                        "weight_kg_m": calculate_pipe_weight_api5l(OD_mm, t_mm),
                    })

    valid_pipes.sort(key=lambda p: (p["nominal_float"], p["t_mm"]))
    return valid_pipes


def size_single_pipe(
    flow_kgs: float,
    p_bar: float,
    t_c: float,
    mw: float = 18.2,
    max_velocity_ms: float = 16.0,
    p_design_bar: Optional[float] = None,
    material: str = "API 5L X70",
    design_factor_F: float = 0.50,
    c_erosion: float = 122.0,
    preferred_nominal: Optional[str] = None,
    density_kgm3: Optional[float] = None,
    viscosity_pa_s: Optional[float] = None,
    z_factor: Optional[float] = None,
    length_m: Optional[float] = None,
    fitting_k_total: float = 0.0,
    elevation_m: float = 0.0,
) -> Dict[str, Any]:
    """
    Finds the optimum commercial pipe (ASME B36.10M / API 5L) for a given natural gas flow condition.
    Checks:
    1. Barlow's formula: t >= t_req at design pressure
    2. Gas velocity: v <= max_velocity_ms
    3. API RP 14E erosion velocity: v <= v_erosion
    4. Pressure gradient & weight minimization
    """
    flow_kgs = max(0.1, float(flow_kgs))
    p_bar = max(1.0, float(p_bar))
    p_pa = p_bar * 1e5
    try:
        t_val = float(t_c) if t_c is not None else 20.0
    except (TypeError, ValueError):
        t_val = 20.0
    t_k = max(50.0, t_val + 273.15)

    # Design pressure (typically 1.1x operating pressure or minimum 10 bar margin)
    if p_design_bar is None or p_design_bar <= p_bar:
        p_design_bar = max(p_bar * 1.15, p_bar + 10.0)
    p_design_pa = p_design_bar * 1e5

    # Gas compressibility & density estimate (approx PR / real gas)
    mw_safe = max(1.0, float(mw or 18.2))
    R_gas = 8314.462 / mw_safe  # J/(kg*K)
    Z = max(0.75, min(0.96, 1.0 - (p_bar / 120.0) * 0.12))
    if z_factor is not None and z_factor > 0:
        Z = float(z_factor)
    rho = max(0.01, p_pa / (Z * R_gas * t_k))  # kg/m3
    if density_kgm3 is not None and density_kgm3 > 0:
        rho = float(density_kgm3)

    # Dynamic viscosity (Lee-Gonzalez-Eakin)
    viscosity = lee_gonzalez_eakin_viscosity(t_k, rho, mw_safe)
    if viscosity_pa_s is not None and viscosity_pa_s > 0:
        viscosity = float(viscosity_pa_s)

    # API RP 14E Erosion Velocity
    v_erosion = calculate_erosion_velocity(rho, c_erosion)

    # SMYS
    SMYS_mpa = PIPE_MATERIALS.get(material, 483.0)
    roughness = PIPE_ROUGHNESS.get(material, 0.0457e-3)

    # Get valid candidates from ASME B36.10M
    candidates = get_sorted_pipes(
        P_design_pa=p_design_pa,
        SMYS_mpa=SMYS_mpa,
        F=design_factor_F,
        E=1.0,
        T=1.0,
    )

    if not candidates:
        raise ValueError(f"ASME B36.10M kataloğunda {p_design_bar} bar tasarım basıncına uygun boru bulunamadı.")

    # Group by nominal size
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for cand in candidates:
        nd = cand["nominal"]
        if nd not in grouped:
            grouped[nd] = []
        grouped[nd].append(cand)

    sorted_nds = sorted(grouped.keys(), key=nd_sort_key)

    # If preferred nominal is requested, check if it's feasible
    selected_pipe = None
    if preferred_nominal and preferred_nominal in grouped:
        pref_cand = grouped[preferred_nominal][0]  # Thinnest valid schedule
        d_m = pref_cand["D_inner_mm"] / 1000.0
        area = math.pi * (d_m ** 2) / 4.0
        v_pref = flow_kgs / (rho * area)
        if v_pref <= max_velocity_ms * 1.25 and v_pref <= v_erosion:
            selected_pipe = pref_cand

    # If no preferred or preferred doesn't meet criteria, find optimum size
    if not selected_pipe:
        for nd in sorted_nds:
            # Thinnest schedule that meets Barlow's formula
            cand = grouped[nd][0]
            d_m = cand["D_inner_mm"] / 1000.0
            area = math.pi * (d_m ** 2) / 4.0
            v_act = flow_kgs / (rho * area)

            # Check velocity constraints
            if v_act <= max_velocity_ms and v_act <= v_erosion:
                selected_pipe = cand
                break

    # If none found within velocity limit (extreme high flow), pick the largest available
    if not selected_pipe:
        selected_pipe = grouped[sorted_nds[-1]][0]

    # Calculate final hydrodynamics for selected pipe
    od_mm = selected_pipe["OD_mm"]
    id_mm = selected_pipe["D_inner_mm"]
    t_mm = selected_pipe["t_mm"]
    t_req_mm = selected_pipe["t_required_mm"]
    schedule = selected_pipe["schedule"]
    nominal = selected_pipe["nominal"]

    d_inner_m = id_mm / 1000.0
    area_m2 = math.pi * (d_inner_m ** 2) / 4.0
    v_actual = round(flow_kgs / (rho * area_m2), 2)
    evr_pct = round((v_actual / v_erosion) * 100.0, 1) if v_erosion > 0 else 0.0

    reynolds = round((rho * v_actual * d_inner_m) / viscosity, 0) if viscosity > 0 else 0
    rel_rough = roughness / d_inner_m
    f_churchill = round(churchill_friction_factor(reynolds, rel_rough), 5)

    # Darcy-Weisbach pressure drop per 100 meters (Pa -> bar)
    # dp = f * (L / D) * (rho * v^2 / 2)
    dp_100m_pa = f_churchill * (100.0 / d_inner_m) * (rho * (v_actual ** 2) / 2.0)
    dp_100m_bar = round(dp_100m_pa / 1e5, 4)

    # Total hydraulic pressure drop for the requested line length, fittings and elevation.
    hydraulic_length_m = float(length_m) if length_m is not None and float(length_m) > 0 else 100.0
    velocity_head_pa = rho * (v_actual ** 2) / 2.0
    friction_dp_pa = f_churchill * (hydraulic_length_m / d_inner_m) * velocity_head_pa
    fittings_dp_pa = max(0.0, float(fitting_k_total or 0.0)) * velocity_head_pa
    elevation_dp_pa = rho * 9.80665 * float(elevation_m or 0.0)
    total_dp_pa = friction_dp_pa + fittings_dp_pa + elevation_dp_pa
    total_dp_bar = round(total_dp_pa / 1e5, 4)
    outlet_pressure_bar = round(max(0.0, p_bar - total_dp_bar), 3)

    weight_kgm = selected_pipe["weight_kg_m"]

    # Status check
    if v_actual > v_erosion:
        vel_status = "Erozyon Limiti Aşıldı (Kritik)"
    elif v_actual > max_velocity_ms:
        vel_status = "Tasarım Hızı Üzerinde"
    elif v_actual < 3.0:
        vel_status = "Düşük Hız (Geniş Çap)"
    else:
        vel_status = "Optimum (API RP 14E & ASME B31.8 Uygun)"

    return {
        "nominal_size_in": f"{nominal}\"",
        "nominal_key": nominal,
        "schedule": schedule,
        "od_mm": od_mm,
        "id_mm": id_mm,
        "wall_thickness_mm": t_mm,
        "min_required_thickness_mm": t_req_mm,
        "actual_velocity_ms": v_actual,
        "max_design_velocity_ms": max_velocity_ms,
        "erosion_velocity_ms": v_erosion,
        "erosion_ratio_pct": evr_pct,
        "reynolds_number": int(reynolds),
        "friction_factor": f_churchill,
        "pressure_drop_bar_per_100m": dp_100m_bar,
        "length_m": round(hydraulic_length_m, 2),
        "fitting_k_total": round(float(fitting_k_total or 0.0), 3),
        "elevation_m": round(float(elevation_m or 0.0), 3),
        "pressure_drop_friction_bar": round(friction_dp_pa / 1e5, 4),
        "pressure_drop_fittings_bar": round(fittings_dp_pa / 1e5, 4),
        "pressure_drop_elevation_bar": round(elevation_dp_pa / 1e5, 4),
        "pressure_drop_bar_total": total_dp_bar,
        "outlet_pressure_bar": outlet_pressure_bar,
        "pipe_weight_kg_m": weight_kgm,
        "gas_density_kgm3": round(rho, 2),
        "gas_viscosity_pa_s": round(viscosity, 7),
        "z_factor": round(Z, 4),
        "design_pressure_bar": p_design_bar,
        "pipe_material": material,
        "smys_mpa": SMYS_mpa,
        "design_factor_F": design_factor_F,
        "velocity_status": vel_status,
        "design_standard": "ASME B31.8 / API 5L / API RP 14E",
    }
