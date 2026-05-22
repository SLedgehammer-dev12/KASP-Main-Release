"""
Tests for thermodynamic boundaries and limit situations in KASP.
This suite ensures the robustness and graceful fallback behavior of different EoS engines
under extreme temperature, pressure, phase, and gas mixture parameters.
"""

import pytest
import logging
from kasp.core.thermo import ThermoEngine
from kasp.core.properties import ThermodynamicSolver
from kasp.core.mixture import GasMixtureBuilder

logger = logging.getLogger(__name__)

@pytest.fixture
def thermo_solver():
    return ThermodynamicSolver()

def test_extreme_high_pressure_coolprop():
    """Ensure CoolProp behaves gracefully or raises an exception that triggers fallback at high pressure."""
    pytest.importorskip("CoolProp", reason="Test requires CoolProp library.")
    solver = ThermodynamicSolver()
    
    # 2000 bar (2e8 Pa) pressure, 50 °C (323.15 K) - extremely high pressure
    p_pa = 2.0e8
    t_k = 323.15
    gas_comp = {"METHANE": 1.0} # Pure methane
    gas_obj = GasMixtureBuilder.build_coolprop_string(GasMixtureBuilder.validate_and_normalize(gas_comp))
    
    state = solver.get_properties(p_pa, t_k, gas_obj, "coolprop")
    
    assert state.P == p_pa
    assert state.T == t_k
    assert state.Z > 0.0
    assert state.density > 0.0

def test_extreme_low_temperature_fallback():
    """Ensure extremely low temperature (near or below absolute zero) falls back to ideal gas safely."""
    solver = ThermodynamicSolver()
    
    p_pa = 1.01325e5
    t_k = 0.01 # Near absolute zero Kelvin
    gas_comp = {"METHANE": 1.0}
    gas_obj = GasMixtureBuilder.build_thermo_data(GasMixtureBuilder.validate_and_normalize(gas_comp))
    
    # This should either succeed or fall back to ideal_fallback phase gracefully
    state = solver.get_properties(p_pa, t_k, gas_obj, "pr")
    
    assert state.Z > 0.0
    assert state.density > 0.0
    # If standard equation of state fails, fallback phase is marked
    if state.raw_props.get("fallback", False):
        assert state.phase in ["ideal_fallback", "liquid", "gas", "ideal"]

def test_negative_temperature_handling():
    """Ensure negative Kelvin input (which is physically impossible) is handled without crashing, by reverting to fallback."""
    solver = ThermodynamicSolver()
    
    p_pa = 1.0e5
    t_k = -50.0 # Negative Kelvin
    gas_comp = {"METHANE": 1.0}
    gas_obj = GasMixtureBuilder.build_thermo_data(GasMixtureBuilder.validate_and_normalize(gas_comp))
    
    # Negative temperature will cause equations of state to fail, verifying fallback triggers
    state = solver.get_properties(p_pa, t_k, gas_obj, "pr")
    
    assert state.raw_props.get("fallback") is True
    assert state.phase == "ideal_fallback"
    assert state.Z > 0.0
    assert state.density > 0.0

def test_unsupported_gas_for_aga8_fallback():
    """Ensure that unsupported gases in pyaga8 (like neon) successfully trigger fallback to Peng-Robinson."""
    solver = ThermodynamicSolver()
    
    # Neon is supported in KASP but not in pyaga8
    gas_comp = {"METHANE": 95.0, "NEON": 5.0}
    normalized = GasMixtureBuilder.validate_and_normalize(gas_comp)
    gas_obj = GasMixtureBuilder.build_thermo_data(normalized)
    
    p_pa = 1.0e6
    t_k = 298.15
    
    # Should fall back to Peng-Robinson because neon is unsupported
    state = solver.get_properties(p_pa, t_k, gas_obj, "aga8")
    
    assert state.raw_props.get("fallback") is True
    assert state.raw_props.get("fallback_type") == "pr_fallback"
    assert state.Z > 0.0
    assert state.density > 0.0

def test_extreme_z_factor_warning(caplog):
    """Ensure warnings are emitted when the Z-factor is exceptionally low or high."""
    solver = ThermodynamicSolver()
    
    # Mocking extremely high pressure to trigger a weird state or mock get_properties to force warning
    p_pa = 5.0e7
    t_k = 150.0
    gas_comp = {"METHANE": 0.8, "ETHANE": 0.2}
    gas_obj = GasMixtureBuilder.build_thermo_data(GasMixtureBuilder.validate_and_normalize(gas_comp))
    
    with caplog.at_level(logging.WARNING):
        state = solver.get_properties(p_pa, t_k, gas_obj, "pr")
        # Check if extremely high pressure / low T yields unusual Z and issues a warning
        if state.Z < 0.5 or state.Z > 1.5:
            assert any("olağandışı z faktörü" in record.message.lower() for record in caplog.records)
