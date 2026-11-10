"""
Reaction force estimation for pressure relief devices.

API 520 Part II (7th ed.) Section 5.8.2 — Determining Reaction Forces in an
Open Discharge System.

Vapor discharge (5.8.2.1, Equation 1, USC units):

    F = (W / 366) * sqrt( k * T / ((k - 1) * M) ) + A * P

where
    F   reaction force at the point of discharge [lbf]
    W   flow of gas or vapor [lbm/h]
    k   ratio of specific heats (Cp/Cv) at outlet conditions [-]
    T   stagnation temperature at the pipe outlet [degR]
        (relieving temperature is a conservative approximation)
    M   molecular weight of the process fluid
    A   area of the outlet at the point of discharge [in2]
    P   static pressure within the outlet pipe immediately before terminal
        expansion to atmosphere [psig]

Two-phase discharge (5.8.2.2, Equation 2, USC units):

    F = (W^2 / (2.898e6 * A)) * ( x / rho_g + (1 - x) / rho_l ) + A * P

where x is the weight fraction vapor and rho_g / rho_l are the vapor and
liquid densities at exit conditions.

Note: the gas equation gives the force at the point of discharge when the
vent discharges through an elbow and a vertical pipe. API 520 Part II cautions
that it is not a substitute for a piping flexibility/stress analysis.
"""
import math
from .constants import ATMOSPHERIC_PSIA

# API 520 Part II Eq (1) momentum constant (USC).
REACTION_MOMENTUM_CONSTANT = 366.0
# API 520 Part II Eq (2) two-phase momentum constant (USC).
REACTION_TWO_PHASE_CONSTANT = 2.898e6


def calculate_gas_reaction_force(
    w_lb_h,
    k,
    t_rankine,
    mw,
    outlet_pressure_psia,
    outlet_area_sqin,
    atmospheric_psia=ATMOSPHERIC_PSIA,
):
    """
    Estimate the reaction force [lbf] for a gas/vapor relief valve venting
    to atmosphere per API 520 Part II 5.8.2.1, Equation (1).

    Parameters
    ----------
    w_lb_h : Mass flow rate (lb/h)
    k : Specific heat ratio (Cp/Cv) at outlet conditions
    t_rankine : Stagnation temperature at the pipe outlet (degR)
    mw : Molecular weight (lb/lbmol)
    outlet_pressure_psia : Static pressure within the outlet pipe immediately
        before terminal expansion to atmosphere (psia)
    outlet_area_sqin : Area of the outlet at the point of discharge (in2)
    atmospheric_psia : Atmospheric pressure (psia)
    """
    if w_lb_h <= 0:
        raise ValueError("Mass flow rate must be positive.")
    if k <= 1.0:
        raise ValueError("Specific heat ratio k must be greater than 1.0 for the reaction force equation.")
    if mw <= 0:
        raise ValueError("MW must be positive.")
    if t_rankine <= 0:
        raise ValueError("Temperature must be positive.")
    if outlet_area_sqin <= 0:
        raise ValueError("Outlet area must be positive.")

    momentum_term = (w_lb_h / REACTION_MOMENTUM_CONSTANT) * math.sqrt(
        k * t_rankine / ((k - 1.0) * mw)
    )
    pressure_term = (outlet_pressure_psia - atmospheric_psia) * outlet_area_sqin
    if pressure_term < 0:
        pressure_term = 0.0

    total_force = momentum_term + pressure_term
    return {
        'Total_Reaction_Force_lbf': total_force,
        'Momentum_Term_lbf': momentum_term,
        'Pressure_Term_lbf': pressure_term,
    }


def calculate_two_phase_reaction_force(
    w_lb_h,
    vapor_mass_fraction,
    vapor_density_lb_ft3,
    liquid_density_lb_ft3,
    outlet_pressure_psia,
    outlet_area_sqin,
    atmospheric_psia=ATMOSPHERIC_PSIA,
):
    """
    Estimate the reaction force [lbf] for a homogeneous (no-slip) two-phase
    discharge to atmosphere per API 520 Part II 5.8.2.2, Equation (2).

    Parameters
    ----------
    w_lb_h : Mass flow rate (lb/h)
    vapor_mass_fraction : Weight fraction vapor at exit conditions [-]
    vapor_density_lb_ft3 : Vapor density at exit conditions (lb/ft3)
    liquid_density_lb_ft3 : Liquid density at exit conditions (lb/ft3)
    outlet_pressure_psia : Static pressure at the outlet (psia)
    outlet_area_sqin : Outlet area at the point of discharge (in2)
    """
    if w_lb_h <= 0:
        raise ValueError("Mass flow rate must be positive.")
    if not 0.0 <= vapor_mass_fraction <= 1.0:
        raise ValueError("Vapor mass fraction must be between 0 and 1.")
    if outlet_area_sqin <= 0:
        raise ValueError("Outlet area must be positive.")

    x = vapor_mass_fraction
    specific_volume_mix = 0.0
    if x > 0:
        if vapor_density_lb_ft3 <= 0:
            raise ValueError("Vapor density must be positive when vapor is present.")
        specific_volume_mix += x / vapor_density_lb_ft3
    if x < 1:
        if liquid_density_lb_ft3 <= 0:
            raise ValueError("Liquid density must be positive when liquid is present.")
        specific_volume_mix += (1.0 - x) / liquid_density_lb_ft3

    momentum_term = (
        w_lb_h ** 2 * specific_volume_mix
        / (REACTION_TWO_PHASE_CONSTANT * outlet_area_sqin)
    )
    pressure_term = max(outlet_pressure_psia - atmospheric_psia, 0.0) * outlet_area_sqin

    return {
        'Total_Reaction_Force_lbf': momentum_term + pressure_term,
        'Momentum_Term_lbf': momentum_term,
        'Pressure_Term_lbf': pressure_term,
        'Mixture_Specific_Volume_ft3_lb': specific_volume_mix,
    }


def calculate_liquid_reaction_force(
    q_gpm,
    fluid_density_lb_ft3,
    outlet_area_sqin,
    discharge_velocity_fps=None,
):
    """
    Estimate the reaction force [lbf] for a liquid relief valve (momentum term).

    F = rho * Q * v / gc

    Parameters
    ----------
    q_gpm : Volumetric flow (US gpm)
    fluid_density_lb_ft3 : Fluid density (lb/ft3)
    outlet_area_sqin : Effective outlet area (in2)
    discharge_velocity_fps : Discharge velocity (ft/s). If None, computed
        from the volumetric flow and outlet area.
    """
    if q_gpm <= 0:
        raise ValueError("Flow rate must be positive.")
    if fluid_density_lb_ft3 <= 0 or outlet_area_sqin <= 0:
        raise ValueError("Density and outlet area must be positive.")

    q_ft3_s = q_gpm / (7.48052 * 60.0)
    outlet_area_ft2 = outlet_area_sqin / 144.0
    if discharge_velocity_fps is None:
        discharge_velocity_fps = q_ft3_s / outlet_area_ft2 if outlet_area_ft2 > 0 else 0.0

    mass_flow_lb_s = q_ft3_s * fluid_density_lb_ft3
    force = mass_flow_lb_s * discharge_velocity_fps / 32.174
    return {
        'Total_Reaction_Force_lbf': force,
        'Discharge_Velocity_fps': discharge_velocity_fps,
    }
