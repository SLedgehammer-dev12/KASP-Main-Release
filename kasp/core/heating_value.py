"""
KASP Heating Value Calculator (v2.1)

Extracted from ThermoEngine._calculate_heating_values().
Supports three calculation sources:
  - iso6976: ISO 6976:2016 molar gross/net values with real-gas Z correction
  - thermo: External 'thermo' library Hc values
  - kasp: Built-in LHV_DATA table (fast, no dependencies)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from kasp.core.constants import MOLAR_MASSES, LHV_DATA, WATER_PRODUCED
from kasp.core.mixture import GasMixtureBuilder

logger = logging.getLogger(__name__)

ISO6976_VALUES = {
    'METHANE':        (891.56, 802.62),
    'ETHANE':         (1562.14, 1429.35),
    'PROPANE':        (2221.10, 2044.20),
    'ISOBUTANE':      (2870.58, 2650.88),
    'BUTANE':         (2880.44, 2660.74),
    'ISOPENTANE':     (3531.68, 3270.28),
    'PENTANE':        (3538.60, 3277.20),
    'HEXANE':         (4197.20, 3894.10),
    'HEPTANE':        (4855.80, 4511.00),
    'OCTANE':         (5514.40, 5127.90),
    'NONANE':         (6173.00, 5744.80),
    'DECANE':         (6831.60, 6361.70),
    'HYDROGEN':       (285.83, 241.83),
    'HYDROGENSULFIDE':(561.43, 517.93),
    'NITROGEN':       (0.0, 0.0),
    'CARBONDIOXIDE':  (0.0, 0.0),
    'WATER':          (0.0, 0.0),
    'ARGON':          (0.0, 0.0),
    'HELIUM':         (0.0, 0.0),
    'OXYGEN':         (0.0, 0.0),
    'NEON':           (0.0, 0.0),
    'KRYPTON':        (0.0, 0.0),
    'XENON':          (0.0, 0.0),
    'AIR':            (0.0, 0.0),
}

THERMO_CHEM_NAME_MAP = {
    "CARBONDIOXIDE": "Carbon dioxide",
    "HYDROGENSULFIDE": "Hydrogen sulfide",
    "ISOPENTANE": "Isopentane",
    "ISOBUTANE": "Isobutane",
}

LHV_WATER_LATENT_HEAT = 2441.7  # kJ/kg at 25°C per ISO 6976


def calculate(
    composition: Dict[str, float],
    source: str = 'kasp',
    *,
    thermo_solver=None,
    gas_obj=None,
    eos_method: Optional[str] = None,
) -> Tuple[float, float]:
    """
    Return (LHV, HHV) in kJ/kg.

    Parameters
    ----------
    composition : dict
        Mole fraction gas composition (will be normalized).
    source : str
        'iso6976', 'thermo', or 'kasp' (default).
    thermo_solver : ThermodynamicSolver, optional
        Required for real-gas Z correction in iso6976 mode.
    gas_obj : optional
        Gas object for property lookup.
    eos_method : str, optional
        EOS method for property lookup.
    """
    comp_frac = GasMixtureBuilder.validate_and_normalize(composition)

    if source == 'iso6976':
        return _calc_iso6976(comp_frac, thermo_solver, gas_obj, eos_method)
    elif source == 'thermo':
        return _calc_thermo(comp_frac)
    else:
        return _calc_kasp(comp_frac)


def _calc_iso6976(comp_frac, thermo_solver, gas_obj, eos_method):
    total_hhv = 0.0
    total_lhv = 0.0
    total_mw = 0.0

    for comp, fraction in comp_frac.items():
        comp_upper = comp.upper()
        mw = MOLAR_MASSES.get(comp_upper, 0)
        total_mw += fraction * mw
        hhv_molar, lhv_molar = ISO6976_VALUES.get(comp_upper, (0.0, 0.0))
        total_hhv += hhv_molar * fraction
        total_lhv += lhv_molar * fraction

    if total_mw == 0:
        return 0.0, 0.0

    avg_mw_kg = total_mw / 1000.0
    lhv_mass = total_lhv / avg_mw_kg
    hhv_mass = total_hhv / avg_mw_kg

    if thermo_solver is not None and gas_obj is not None and eos_method is not None:
        try:
            state_std = thermo_solver.get_properties(101325.0, 288.15, gas_obj, eos_method)
            z_std = state_std.Z
            if z_std > 0.1:
                lhv_mass = lhv_mass / z_std
                hhv_mass = hhv_mass / z_std
        except Exception as e:
            logger.warning(f"ISO 6976 Z düzeltmesi hesaplanamadı: {e}")

    return lhv_mass, hhv_mass


def _calc_thermo(comp_frac):
    total_lhv_energy = 0.0
    total_mw = 0.0
    total_water_moles = 0.0

    for comp, fraction in comp_frac.items():
        comp_upper = comp.upper()
        mw = MOLAR_MASSES.get(comp_upper, 0)
        total_mw += fraction * mw
        total_water_moles += fraction * WATER_PRODUCED.get(comp_upper, 0)

        lhv = _get_thermo_lhv(comp_upper, mw)
        total_lhv_energy += lhv * (mw / 1000.0) * fraction

    if total_mw == 0:
        return 0.0, 0.0

    avg_mw_kg = total_mw / 1000.0
    lhv_mass = total_lhv_energy / avg_mw_kg

    water_kg_per_kg = (
        (total_water_moles * 0.018015) / avg_mw_kg if avg_mw_kg > 0 else 0.0
    )
    hhv_mass = lhv_mass + water_kg_per_kg * LHV_WATER_LATENT_HEAT

    return lhv_mass, hhv_mass


def _calc_kasp(comp_frac):
    total_lhv_energy = 0.0
    total_mw = 0.0
    total_water_moles = 0.0

    for comp, fraction in comp_frac.items():
        comp_upper = comp.upper()
        mw = MOLAR_MASSES.get(comp_upper, 0)
        lhv = LHV_DATA.get(comp_upper, 0)
        total_lhv_energy += lhv * (mw / 1000.0) * fraction
        total_mw += fraction * mw
        total_water_moles += fraction * WATER_PRODUCED.get(comp_upper, 0)

    if total_mw == 0:
        return 0.0, 0.0

    avg_mw_kg = total_mw / 1000.0
    lhv_mass = total_lhv_energy / avg_mw_kg

    water_kg_per_kg = (
        (total_water_moles * 0.018015) / avg_mw_kg if avg_mw_kg > 0 else 0.0
    )
    hhv_mass = lhv_mass + water_kg_per_kg * LHV_WATER_LATENT_HEAT

    return lhv_mass, hhv_mass


def _get_thermo_lhv(comp_upper: str, mw: float) -> float:
    try:
        import thermo
        from thermo.chemical import Chemical
        chem_name = THERMO_CHEM_NAME_MAP.get(
            comp_upper, comp_upper.lower().capitalize()
        )
        chem = Chemical(chem_name)
        if chem.Hc:
            hhv_kj_kg = abs(chem.Hc) / 1000.0
            water_moles = WATER_PRODUCED.get(comp_upper, 0)
            mw_fuel_kg = mw / 1000.0
            mass_h2o = (
                (water_moles * 0.018015) / mw_fuel_kg if mw_fuel_kg > 0 else 0.0
            )
            return hhv_kj_kg - (mass_h2o * LHV_WATER_LATENT_HEAT)
    except Exception as e:
        logger.debug(f"Thermo Hc alinmadi ({comp_upper}): {e}")
    return LHV_DATA.get(comp_upper, 0)
