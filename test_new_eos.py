import pytest
import numpy as np
from kasp.core.thermo import ThermoEngine
from kasp.core.properties import ThermodynamicSolver

def test_thermopack_eos_state_solver():
    """Verify that the SINTEF thermopack EoS state solver is working correctly."""
    solver = ThermodynamicSolver()
    
    # Composition representation for thermo/thermopack (dict format)
    # 90% Methane, 8% Ethane, 2% Propane
    gas_data = {
        "ids": ["methane", "ethane", "propane"],
        "mol_fractions": [0.90, 0.08, 0.02],
        "MW": 16.04 * 0.90 + 30.07 * 0.08 + 44.10 * 0.02
    }
    
    # Solve at 10 bar (1.0e6 Pa) and 25C (298.15 K)
    state = solver.get_properties(1.0e6, 298.15, gas_data, 'thermopack')
    
    assert state is not None
    assert state.Z > 0.0
    assert state.Z < 1.05
    assert state.density > 0.0
    assert state.H != 0.0
    assert state.S != 0.0
    assert state.Cp > 0.0
    assert state.Cv > 0.0
    assert state.k > 1.0
    assert state.raw_props["fallback"] is False
    assert state.raw_props["speed_of_sound"] > 100.0

def test_ccp_eos_state_solver():
    """Verify that the Petrobras ccp EoS state solver is working correctly."""
    solver = ThermodynamicSolver()
    
    gas_data = {
        "ids": ["methane", "ethane", "propane"],
        "mol_fractions": [0.90, 0.08, 0.02],
        "MW": 16.04 * 0.90 + 30.07 * 0.08 + 44.10 * 0.02
    }
    
    # Solve at 10 bar and 25C
    state = solver.get_properties(1.0e6, 298.15, gas_data, 'ccp')
    
    assert state is not None
    assert state.Z > 0.0
    assert state.Z < 1.05
    assert state.density > 0.0
    assert state.H != 0.0
    assert state.S != 0.0
    assert state.Cp > 0.0
    assert state.Cv > 0.0
    assert state.k > 1.0
    assert state.raw_props["fallback"] is False
    assert state.raw_props["speed_of_sound"] > 100.0

def test_thermo_engine_integration():
    """Verify that the full ThermoEngine runs successfully with thermopack and ccp."""
    engine = ThermoEngine()
    
    inputs = {
        "p_in": 10.0,
        "p_in_unit": "bar",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "p_out": 25.0,
        "p_out_unit": "bar",
        "flow": 10000.0,
        "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 8.0, "PROPANE": 2.0},
        "eos_method": "thermopack",  # Test thermopack integration
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 85.0,
        "num_units": 1,
        "num_stages": 1,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0,
        "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    
    # Calculate performance using thermopack
    results_tp = engine.calculate_design_performance(inputs)
    assert results_tp["t_out"] > 25.0
    assert results_tp["power_gas_total_kw"] > 0.0
    assert results_tp["head_kj_kg"] > 0.0
    
    # Calculate performance using ccp
    inputs["eos_method"] = "ccp"
    results_ccp = engine.calculate_design_performance(inputs)
    assert results_ccp["t_out"] > 25.0
    assert results_ccp["power_gas_total_kw"] > 0.0
    assert results_ccp["head_kj_kg"] > 0.0


def test_solver_method_ui_binding():
    """Verify that UI solver method options are correctly translated and mapped."""
    from kasp.ui.design_input_binding import solver_method_from_ui_text
    
    assert solver_method_from_ui_text("Analitik Jakobiyen NR (AJ-NR - Hızlı)") == "aj_nr"
    assert solver_method_from_ui_text("Sonlu Farklar NR (FD-NR - Standart)") == "fd_nr"
    assert solver_method_from_ui_text("Brent Hibrit Yöntemi (Brent - Kararlı)") == "brent"
    assert solver_method_from_ui_text("Otomatik Karşılaştırmalı Benchmark (Auto)") == "auto"
    assert solver_method_from_ui_text("Bilinmeyen Metot") == "auto"


def test_dwsim_eos_fallback():
    """Verify that if DWSIM is not fully initialized, requesting 'dwsim' falls back safely to PR."""
    solver = ThermodynamicSolver()
    
    gas_data = {
        "ids": ["methane", "ethane", "propane"],
        "mol_fractions": [0.90, 0.08, 0.02],
        "MW": 16.04 * 0.90 + 30.07 * 0.08 + 44.10 * 0.02
    }
    
    # Solve at 10 bar (1.0e6 Pa) and 25C (298.15 K) using 'dwsim'
    # Even if DWSIM DLL is not loaded, it should fall back to PR and succeed without crashing.
    state = solver.get_properties(1.0e6, 298.15, gas_data, 'dwsim')
    
    assert state is not None
    assert state.Z > 0.0
    assert state.Z < 1.05
    assert state.density > 0.0


def test_dwsim_ui_binding():
    """Verify that UI EoS options for DWSIM map and parse correctly."""
    from kasp.ui.design_input_binding import eos_method_from_ui_text
    
    # Active mapping
    method, err = eos_method_from_ui_text("🇩🇪 DWSIM Thermodynamics (PR)")
    assert method == "dwsim"
    assert err is None
    
    # Missing mapping
    method, err = eos_method_from_ui_text("🇩🇪 DWSIM (.NET / pythonnet Eksik)")
    assert method is None
    assert "pythonnet" in err


