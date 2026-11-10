"""
Consistent units system with pint backend and fallback.

Uses pint if available, otherwise falls back to the existing
unit_converter module transparently.
"""
import sys
from typing import Union, Tuple

from .unit_converter import (
    barg_to_psia, bara_to_psia, psia_to_barg,
    kg_h_to_lb_h, lb_h_to_kg_h, kg_s_to_lb_h,
    m3_h_to_gpm, gpm_to_m3_h,
    c_to_rankine, c_to_f,
    m3_kg_to_ft3_lb, kg_m3_to_lb_ft3,
    kcal_h_to_btu_h, kw_to_btu_h,
    m2_to_sqft, sqft_to_m2,
    kcal_kg_to_btu_lb, kj_kgK_to_btu_lbF,
    actual_m3_h_to_lb_h, sm3_h_to_lb_h, nm3_h_to_lb_h,
    ATM_PSIA, PSI_PER_BAR, R_PSIA_FT3_LBMOL_R,
)

try:
    import pint
    HAS_PINT = True
    _ureg = pint.UnitRegistry()
    _ureg.define('api_orifice = 0.00064516 * m^2 = sqin_api')
    Q_ = _ureg.Quantity
except ImportError:
    HAS_PINT = False
    Q_ = None


_CONVERSION_CACHE: dict = {}


def convert(
    value: float,
    from_unit: str,
    to_unit: str,
) -> float:
    """Convert a value between units using pint if available."""
    if HAS_PINT:
        cache_key = (from_unit, to_unit)
        if cache_key not in _CONVERSION_CACHE:
            try:
                _CONVERSION_CACHE[cache_key] = (1.0 * _ureg(from_unit)).to(_ureg(to_unit)).magnitude
            except Exception:
                pass
        if cache_key in _CONVERSION_CACHE and value != 0:
            return value * _CONVERSION_CACHE[cache_key]
    
    return _fallback_convert(value, from_unit, to_unit)


def _fallback_convert(value: float, from_unit: str, to_unit: str) -> float:
    """Fallback unit conversions when pint is unavailable."""
    pairs = {
        ("barg", "psia"): barg_to_psia,
        ("psia", "barg"): psia_to_barg,
        ("bara", "psia"): bara_to_psia,
        ("kg/h", "lb/h"): kg_h_to_lb_h,
        ("lb/h", "kg/h"): lb_h_to_kg_h,
        ("kg/s", "lb/h"): kg_s_to_lb_h,
        ("m3/h", "US_gpm"): m3_h_to_gpm,
        ("US_gpm", "m3/h"): gpm_to_m3_h,
        ("m3/h", "gpm"): m3_h_to_gpm,
        ("gpm", "m3/h"): gpm_to_m3_h,
        ("degC", "degR"): c_to_rankine,
        ("degR", "degC"): lambda v: (v - 491.67) / 1.8,
        ("degC", "degF"): c_to_f,
        ("degF", "degC"): lambda v: (v - 32.0) / 1.8,
        ("m3/kg", "ft3/lb"): m3_kg_to_ft3_lb,
        ("ft3/lb", "m3/kg"): lambda v: v / 16.01846,
        ("m2", "sqft"): m2_to_sqft,
        ("sqft", "m2"): sqft_to_m2,
        ("kcal/h", "BTU/h"): kcal_h_to_btu_h,
        ("kW", "BTU/h"): kw_to_btu_h,
        ("kcal/kg", "Btu/lb"): kcal_kg_to_btu_lb,
        ("mm2", "sqin"): lambda v: v / 645.16,
        ("sqin", "mm2"): lambda v: v * 645.16,
        ("mm2", "in2"): lambda v: v / 645.16,
        ("in2", "mm2"): lambda v: v * 645.16,
        ("L/min", "gpm"): lambda v: v / 3.785411784,
        ("gpm", "L/min"): lambda v: v * 3.785411784,
        ("L/min", "US_gpm"): lambda v: v / 3.785411784,
        ("US_gpm", "L/min"): lambda v: v * 3.785411784,
        ("kJ/kg", "Btu/lb"): lambda v: v / 2.326,
        ("Btu/lb", "kJ/kg"): lambda v: v * 2.326,
    }

    key = (from_unit, to_unit)
    if key in pairs:
        return pairs[key](value)

    if from_unit == to_unit:
        return value

    raise ValueError(f"Unknown conversion: {from_unit} → {to_unit}")


def unit_info() -> dict:
    """Return info about the units system in use."""
    return {
        "backend": "pint" if HAS_PINT else "fallback",
        "atm_psia": ATM_PSIA,
        "psi_per_bar": PSI_PER_BAR,
        "r_psia_ft3_lbmol_R": R_PSIA_FT3_LBMOL_R,
    }


__all__ = [
    "convert",
    "unit_info",
    "HAS_PINT",
    "barg_to_psia",
    "bara_to_psia",
    "psia_to_barg",
    "kg_h_to_lb_h",
    "lb_h_to_kg_h",
    "m3_h_to_gpm",
    "gpm_to_m3_h",
    "c_to_rankine",
    "m3_kg_to_ft3_lb",
    "atm_psia",
    "ATM_PSIA",
    "PSI_PER_BAR",
]