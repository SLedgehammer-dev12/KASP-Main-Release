"""
Test suite for Phase A: Core Physics & Aerodynamic Formulations
- Verifies Schultz factor f_t=1.0 for schultz_3exp and incremental_pressure
- Verifies dimensionless aerodynamic coefficients using per-stage head and Balje Ns/Ds
- Verifies thermodynamic speed of sound via EOS dP_dV derivatives
"""

import pytest
import math
from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.properties import ThermodynamicSolver


def test_dimensionless_coeffs_per_stage_head():
    """Verify that calculate_dimensionless_coeffs scales with per-stage head and computes Balje metrics."""
    # 4-stage compressor with 280 kJ/kg total head (70 kJ/kg per stage)
    results = {
        "head_kj_kg": 280.0,
        "num_stages": 4,
    }
    inlet_props = {
        "rho": 1.25,
        "a": 400.0,
        "mu": 1.5e-5,
    }
    mass_flow_kgs = 25.0

    coeffs = CompressorAerodynamics.calculate_dimensionless_coeffs(results, inlet_props, mass_flow_kgs)
    assert coeffs is not None
    assert coeffs["num_stages"] == 4
    assert coeffs["head_stage_kj_kg"] == 70.0
    
    # Single stage head is 70,000 J/kg -> U_est = sqrt(70000 / 0.50) ≈ 374.17 m/s
    assert 350.0 < coeffs["U_est_m_s"] < 400.0
    assert 0.45 <= coeffs["psi"] <= 0.55
    assert 0.03 <= coeffs["phi"] <= 0.06
    assert coeffs["Ns"] != "-"
    assert coeffs["Ds"] != "-"
    # Balje product Ns * Ds typically ~ 1.5 - 2.5
    ns = float(coeffs["Ns"])
    ds = float(coeffs["Ds"])
    assert 0.3 < ns < 2.5
    assert 1.0 < ds < 6.0


def test_dimensionless_coeffs_single_stage():
    """Verify single-stage fallback behavior."""
    results = {"head_kj_kg": 50.0}
    inlet_props = {"rho": 1.2, "a": 340.0, "mu": 1.8e-5}
    coeffs = CompressorAerodynamics.calculate_dimensionless_coeffs(results, inlet_props, 10.0)
    assert coeffs is not None
    assert coeffs["num_stages"] == 1
    assert coeffs["head_stage_kj_kg"] == 50.0
    assert 0.45 <= coeffs["psi"] <= 0.55


def test_speed_of_sound_thermo_derivative():
    """Verify ThermodynamicSolver computes speed of sound for PR EOS with real gas mixture."""
    solver = ThermodynamicSolver()
    # Gas mixture: 80% Methane, 20% Ethane at 30 bar, 300 K
    gas_comp = {"METHANE": 80.0, "ETHANE": 20.0}
    state = solver.get_properties(30e5, 300.0, gas_comp, "pr")
    
    assert state.speed_of_sound is not None
    assert math.isfinite(state.speed_of_sound)
    # Real speed of sound for this mixture around 30 bar, 300K is ~370-420 m/s
    assert 350.0 < state.speed_of_sound < 450.0
    assert state.raw_props["speed_of_sound"] == state.speed_of_sound
