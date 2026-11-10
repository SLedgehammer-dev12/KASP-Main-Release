import math
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# API 520 Part I 10th ed. Figure 31 — Backpressure correction factor Kb for
# balanced spring-loaded PRVs (vapors and gases). Separate curves are given
# for 10 %, 16 %, and 21 % allowable overpressure (see 5.3.3.2.2).
# Curves digitized from Figure 31 (PDF page 59). For 21 % overpressure,
# NOTE 3 states Kb = 1.0 up to P_B/P_S = 50 %.
# Values are valid for set pressures >= 50 psig and subcritical backpressure
# below the critical flow pressure; consult the manufacturer otherwise.
KB_BALANCED_BELLOWS_10PCT: Dict[float, float] = {
    0.0: 1.000,
    30.0: 1.000,
    32.0: 0.990,
    33.0: 0.978,
    34.0: 0.964,
    35.0: 0.950,
    36.0: 0.937,
    37.0: 0.921,
    38.0: 0.903,
    39.0: 0.888,
    40.0: 0.871,
    42.0: 0.836,
    44.0: 0.800,
    46.0: 0.763,
    48.0: 0.723,
    50.0: 0.685,
}

KB_BALANCED_BELLOWS_16PCT: Dict[float, float] = {
    0.0: 1.000,
    36.0: 1.000,
    37.0: 0.990,
    38.0: 0.980,
    40.0: 0.963,
    42.5: 0.945,
    45.0: 0.930,
    47.5: 0.918,
    50.0: 0.908,
}

# For 21 % overpressure Kb = 1.0 up to 50 % backpressure (Figure 31, NOTE 3).
KB_BALANCED_BELLOWS_21PCT: Dict[float, float] = {
    0.0: 1.000,
    50.0: 1.000,
}

# Conventional valves have Kb = 1.0 (see Figure 37 for the alternate
# critical-flow procedure).
KB_CONVENTIONAL: Dict[float, float] = {}


def select_kb_curve(overpressure_pct: float) -> Tuple[Dict[float, float], str]:
    """Return the Figure 31 curve applicable to the overpressure scenario."""
    if overpressure_pct <= 13.0:
        return KB_BALANCED_BELLOWS_10PCT, "10%"
    if overpressure_pct <= 18.5:
        return KB_BALANCED_BELLOWS_16PCT, "16%"
    return KB_BALANCED_BELLOWS_21PCT, "21%"


def get_backpressure_percent(back_pressure_psia, set_pressure_psig, atm_psia=14.6959):
    """Back pressure as percentage of set (gauge) pressure."""
    if set_pressure_psig <= 0:
        return 0.0
    bp_gauge = max(back_pressure_psia - atm_psia, 0.0)
    return (bp_gauge / set_pressure_psig) * 100.0


def check_backpressure_limit(bp_pct, valve_type="conventional"):
    """
    Check whether the back pressure is within the recommended operating
    limit for the valve type (API 520 Part I 5.3.3.2).

    Returns (passes: bool, message: str).
    """
    if valve_type == "balanced_bellows":
        if bp_pct > 50.0:
            return (False, f"Back pressure {bp_pct:.1f}% exceeds the 50% limit for balanced bellows valves (API 520 Part I 5.3.3.2.3). Consult the manufacturer.")
    elif valve_type == "conventional":
        if bp_pct > 50.0:
            return (False, f"Back pressure {bp_pct:.1f}% exceeds the ~50% limit for conventional valves — flow becomes subcritical; consult the manufacturer (API 520 Part I 5.3.3.2.4).")
    elif valve_type == "pilot":
        if bp_pct > 50.0:
            return (True, f"Back pressure {bp_pct:.1f}% is high for a pilot-operated valve — verify the pilot and outlet piping with the manufacturer (API 520 Part I 5.3.4.3).")
    return (True, "")


def interpolate_kb(bp_pct: float, curve: Dict[float, float]) -> float:
    """
    Linear interpolation between digitized Kb curve points.

    Parameters
    ----------
    bp_pct : Back pressure as percentage of set gauge pressure (0-100)
    curve : Dict of {bp_pct: Kb} digitized points

    Returns
    -------
    Kb value at the given back pressure percentage
    """
    if not curve:
        return 1.0

    sorted_points = sorted(curve.items())
    points: List[Tuple[float, float]] = [(k, v) for k, v in sorted_points]

    if bp_pct <= points[0][0]:
        return points[0][1]
    if bp_pct >= points[-1][0]:
        return points[-1][1]

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if x1 <= bp_pct <= x2:
            ratio = (bp_pct - x1) / (x2 - x1)
            return y1 + ratio * (y2 - y1)

    return 1.0


def get_kb(
    back_pressure_psia: float,
    set_pressure_psig: float,
    valve_type: str = "conventional",
    overpressure_pct: float = 10.0,
    atm_psia: float = 14.6959,
) -> float:
    """
    Calculate back pressure correction factor Kb per API 520 Part I 10th ed.
    Figure 31 for balanced bellows valves (10 %, 16 %, 21 % overpressure).

    Conventional and pilot-operated valves use Kb = 1.0 (see 5.3.3.2.1
    and 5.3.4.3).

    Parameters
    ----------
    back_pressure_psia : Total back pressure at relieving conditions (psia)
    set_pressure_psig : Set pressure (psig)
    valve_type : "conventional", "balanced_bellows", or "pilot"
    overpressure_pct : Percent overpressure (10, 16 or 21)
    atm_psia : Site atmospheric pressure (default sea level 14.6959 psia)

    Returns
    -------
    Kb capacity correction factor (dimensionless)
    """
    if set_pressure_psig <= 0:
        return 1.0

    bp_pct = get_backpressure_percent(back_pressure_psia, set_pressure_psig, atm_psia)

    if valve_type in ("conventional", "pilot"):
        if valve_type == "conventional" and bp_pct > 50.0:
            logger.warning(
                "Conventional valve back pressure %.1f%% exceeds the ~50%% limit of set pressure.",
                bp_pct,
            )
        return 1.0

    curve, basis = select_kb_curve(overpressure_pct)
    if overpressure_pct > 21.5:
        logger.warning(
            "Backpressure correction for %.1f%% overpressure is outside Figure 31 "
            "(10/16/21%%); the 21%% curve (Kb = 1.0) is used only up to 50%% — "
            "consult the manufacturer.",
            overpressure_pct,
        )
    if bp_pct > 50.0:
        logger.warning(
            "Balanced bellows back pressure %.1f%% is above the Figure 31 range (50%%). "
            "Kb is clamped to the curve endpoint — consult the manufacturer.",
            bp_pct,
        )
    return interpolate_kb(bp_pct, curve)


# Gas critical back pressure ratio per API 520
def get_critical_back_pressure_ratio(valve_type: str = "conventional") -> float:
    """
    Return the critical back pressure ratio (P2/P1) for flow regime determination.

    Conventional: 0.5 (50% of set gauge)
    Balanced bellows: 0.6 (60% of set gauge)
    """
    if valve_type == "balanced_bellows":
        return 0.6
    return 0.5
