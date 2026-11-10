import math
from .valve_selection import select_orifice
from .validation import validate_liquid_inputs, ValidationError
from .constants import (
    LIQUID_FORMULA_CONSTANT, REYNOLDS_CONSTANT,
    KV_CONSTANT, KV_EXPONENT, KV_REYNOLDS_MIN, KV_VISCOSITY_LIMIT_CP,
    PRELIM_KD_LIQUID, NONCERTIFIED_KD_LIQUID,
    ATMOSPHERIC_PSIA,
)

# API 520 Part I 10th ed. Figure 39 — Capacity correction factor Kp due to
# overpressure for NONCERTIFIED pressure-relief valves in liquid service.
# Reference points: Kp = 0.6 at 10 % overpressure, Kp = 1.0 at 25 %.
# Curve digitized from Figure 39 (10th ed., PDF page 95). Values above 25 %
# reflect the "overpressure only" region of the curve.
KP_FIGURE_39 = [
    (10.0, 0.60),
    (12.5, 0.70),
    (15.0, 0.79),
    (17.5, 0.86),
    (20.0, 0.91),
    (22.5, 0.96),
    (25.0, 1.00),
    (30.0, 1.015),
    (35.0, 1.035),
    (40.0, 1.055),
    (45.0, 1.074),
    (50.0, 1.092),
]

# API 520 Part I 10th ed. Figure 32 — Capacity correction factor Kw due to
# backpressure on balanced spring-loaded PRVs in liquid service. Applicable
# for all overpressures; curve digitized from Figure 32 (PDF page 60).
KW_BALANCED_BELLOWS_LIQUID = [
    (0.0, 1.000),
    (15.0, 1.000),
    (17.0, 0.993),
    (18.0, 0.988),
    (19.0, 0.980),
    (20.0, 0.971),
    (22.0, 0.950),
    (25.0, 0.917),
    (27.5, 0.891),
    (30.0, 0.866),
    (32.5, 0.841),
    (35.0, 0.816),
    (37.5, 0.792),
    (40.0, 0.767),
    (42.5, 0.742),
    (45.0, 0.717),
    (47.5, 0.692),
    (50.0, 0.667),
]

# Certified liquid service (§5.8 Eq 32) does not use Kp.
KP_CURVE = KP_FIGURE_39


def _interpolate_points(val: float, points: list) -> float:
    """Linear interpolation between points [(x0, y0), (x1, y1), ...]."""
    if val <= points[0][0]:
        return points[0][1]
    if val >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if x1 <= val <= x2:
            return y1 + ((val - x1) / (x2 - x1)) * (y2 - y1)
    return points[-1][1]


def calculate_kp(overpressure_pct: float) -> float:
    """
    API 520 Part I 10th ed. Figure 39 — Capacity correction factor Kp due to
    overpressure for NONCERTIFIED pressure-relief valves in liquid service.

    Kp = 0.6 at 10 % overpressure (chatter region below 10 % shall be
    avoided) and Kp = 1.0 at the 25 % reference point of §5.9.
    """
    if overpressure_pct is None:
        return 1.0
    return _interpolate_points(max(overpressure_pct, 10.0), KP_FIGURE_39)


def calculate_kw_liquid(back_pressure_pct: float, valve_type: str = "conventional") -> float:
    """
    API 520 Part I 10th ed. Figure 32 — Capacity correction factor Kw due to
    backpressure on balanced spring-loaded PRVs in liquid service.

    Applicable for all overpressures. For conventional and pilot valves
    Kw = 1.0; for balanced bellows valves Kw is 1.0 up to ~15 % BP and then
    decreases (digitized Figure 32 values).
    """
    if back_pressure_pct < 0:
        raise ValidationError(
            f"Back pressure percentage must be non-negative (got {back_pressure_pct})"
        )
    if valve_type != "balanced_bellows":
        return 1.0
    return _interpolate_points(back_pressure_pct, KW_BALANCED_BELLOWS_LIQUID)


def calculate_reynolds(q_gpm, g, mu_cp, area_sq_in):
    if area_sq_in <= 0 or mu_cp <= 0:
        return float('inf')
    return (REYNOLDS_CONSTANT * q_gpm * g) / (mu_cp * math.sqrt(area_sq_in))


def calculate_kv(re):
    """
    API 520 Part I 10th ed. Eq. (34): Kv = (1 + 170/Re)^-0.5.

    The equation is applicable for Re >= 80; values below that are still
    returned (and are conservative) but should be reviewed.
    """
    if re <= 0 or math.isinf(re):
        return 1.0
    kv = (1.0 + KV_CONSTANT / re) ** KV_EXPONENT
    return min(kv, 1.0)


def viscosity_correction_factor(re, mu_cp):
    """
    Return (Kv, basis). API 520 Part I 5.8.1.3 allows Kv = 1.0 when the
    liquid viscosity is 100 cP or less; otherwise Figure 38 / Eq. (34).
    """
    if mu_cp <= KV_VISCOSITY_LIMIT_CP:
        return 1.0, "Kv = 1.0 (viscosity <= 100 cP per 5.8.1.3)"
    return calculate_kv(re), "Fig 38 / Eq 34"


def calculate_liquid_relief_area(
    q_gpm,
    p1_psia,
    p2_psia,
    g,
    mu_cp,
    kd=None,
    kw=None,
    kc=1.0,
    num_valves=1,
    kp=None,
    overpressure_pct=10.0,
    valve_type="conventional",
    set_pressure_psig=None,
    atm_psia=ATMOSPHERIC_PSIA,
    capacity_certified=True,
):
    """
    API 520 Part I 10th ed. liquid relief valve sizing.

    capacity_certified=True  -> 5.8, Eq (32):
        A = Q / (38 Kd Kw Kc Kv) * sqrt(G / (P1 - P2))
        preliminary Kd = 0.65; Kp does NOT apply.

    capacity_certified=False -> 5.9, Eq (42):
        A = Q / (38 Kd Kw Kc Kv Kp) * sqrt(G / (1.25 Ps - P2))
        Kd shall be 0.62; Kp from Figure 39 (1.0 at 25 % overpressure).

    Uses Reynolds-number-dependent iterative sizing with the 10th edition
    Kv viscosity correction factor (Kv = 1.0 when mu <= 100 cP).
    """
    method = "certified" if capacity_certified else "noncertified"

    if capacity_certified:
        if kd is None:
            kd = PRELIM_KD_LIQUID
        kp = 1.0
        kp_basis = "Not used in certified liquid service (5.8, Eq 32)"
        delta_p = p1_psia - p2_psia
    else:
        kd = NONCERTIFIED_KD_LIQUID
        if set_pressure_psig is not None and set_pressure_psig > 0:
            ps_psig = set_pressure_psig
        else:
            ps_psig = (p1_psia - atm_psia) / (1.0 + overpressure_pct / 100.0)
        delta_p = 1.25 * ps_psig - (p2_psia - atm_psia)
        if delta_p <= 0:
            raise ValueError(
                "Noncertified method requires 1.25 x set pressure to exceed the "
                f"total back pressure (got {delta_p:.2f} psi)."
            )
        if kp is None:
            kp = calculate_kp(overpressure_pct)
        kp_basis = "Figure 39 (noncertified, 25 % reference)"

    if kw is None:
        if valve_type == "balanced_bellows":
            if set_pressure_psig is not None and set_pressure_psig > 0:
                sp = set_pressure_psig
            else:
                p1_gauge = max(p1_psia - atm_psia, 0.0)
                sp = p1_gauge / (1.0 + overpressure_pct / 100.0) if overpressure_pct > -100 else 1.0
            bp_gauge = max(p2_psia - atm_psia, 0.0)
            bp_pct = (bp_gauge / sp * 100.0) if sp > 0 else 0.0
            kw = calculate_kw_liquid(bp_pct, valve_type)
        else:
            kw = 1.0

    validate_liquid_inputs(q_gpm, p1_psia, p2_psia, g, mu_cp, kd, kw, kp)
    if num_valves < 1:
        raise ValueError("num_valves must be >= 1")

    a_req_no_visc = (q_gpm / (LIQUID_FORMULA_CONSTANT * kd * kw * kc * kp)) * math.sqrt(g / delta_p)
    a_req_no_visc_per_valve = a_req_no_visc / num_valves

    letter, selected_area = select_orifice(a_req_no_visc_per_valve)

    re = calculate_reynolds(q_gpm / num_valves, g, mu_cp, selected_area)
    kv, kv_basis = viscosity_correction_factor(re, mu_cp)
    a_req_final = (q_gpm / (LIQUID_FORMULA_CONSTANT * kd * kw * kc * kv * kp)) * math.sqrt(g / delta_p)
    a_req_final_per_valve = a_req_final / num_valves
    final_letter, final_selected_area = select_orifice(a_req_final_per_valve)

    prev_letter = final_letter
    converged = False
    for iteration in range(10):
        re = calculate_reynolds(q_gpm / num_valves, g, mu_cp, final_selected_area)
        kv, kv_basis = viscosity_correction_factor(re, mu_cp)
        a_req_final = (q_gpm / (LIQUID_FORMULA_CONSTANT * kd * kw * kc * kv * kp)) * math.sqrt(g / delta_p)
        a_req_final_per_valve = a_req_final / num_valves
        new_letter, new_selected_area = select_orifice(a_req_final_per_valve)
        if new_letter == prev_letter:
            final_letter, final_selected_area = new_letter, new_selected_area
            converged = True
            break
        prev_letter = new_letter
        final_letter, final_selected_area = new_letter, new_selected_area

    loading_pct = (a_req_final_per_valve / final_selected_area * 100.0
                   if isinstance(final_selected_area, (int, float)) else None)

    return {
        'Required_Area_No_Visc_sqin': a_req_no_visc_per_valve,
        'Reynolds_Number': re,
        'Kv': kv,
        'Kp': kp,
        'Kw': kw,
        'Overpressure_Pct': overpressure_pct,
        'Required_Area_Final_sqin': a_req_final_per_valve,
        'Selected_Orifice_Letter': final_letter,
        'Selected_Orifice_Area_sqin': final_selected_area,
        'Orifice_Loading_Pct': loading_pct,
        'Kd': kd,
        'Kc': kc,
        'Num_Valves': num_valves,
        'Valve_Type': valve_type,
        'Kv_Basis': kv_basis,
        'Re_Below_80': re < KV_REYNOLDS_MIN,
        'Method': method,
        'Kd_Basis': 'API 520 5.9 (0.62)' if not capacity_certified else 'API 520 5.8 preliminary (0.65)',
        'Kp_Basis': kp_basis,
        'Orifice_Iteration_Converged': converged,
    }

