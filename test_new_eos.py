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




def test_gerg2008_eos_state_solver():
    """GERG-2008 (pyaga8) must be a real, callable backend and match AGA8-DC92 closely."""
    solver = ThermodynamicSolver()
    gas_data = {
        "ids": ["methane", "ethane", "propane", "nitrogen", "carbon dioxide"],
        "mol_fractions": [0.88, 0.07, 0.03, 0.01, 0.01],
        "MW": 18.27,
    }

    gerg = solver.get_properties(20.0e5, 298.15, gas_data, "gerg2008")
    aga8 = solver.get_properties(20.0e5, 298.15, gas_data, "aga8")

    assert gerg.raw_props["fallback"] is False
    assert gerg.Z > 0.5
    assert gerg.density > 0.0
    # GERG-2008 and AGA8-DC92 are different correlations but should agree closely
    # for a lean natural-gas mixture.
    assert abs(gerg.Z - aga8.Z) / aga8.Z < 0.005
    assert abs(gerg.density - aga8.density) / aga8.density < 0.005
    # True isentropic exponent is stored separately from Cp/Cv.
    assert 1.0 < gerg.raw_props["isentropic_exponent"] < 2.0
    assert 1.0 < gerg.raw_props["cp_cv_ratio"] < 2.0


def test_gerg2008_design_calculation_runs():
    """Selecting GERG-2008 from the UI must not raise 'Bilinmeyen EOS metodu'."""
    inputs = {
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": {
            "METHANE": 88.0,
            "ETHANE": 7.0,
            "PROPANE": 3.0,
            "NITROGEN": 1.0,
            "CARBONDIOXIDE": 1.0,
        },
        "eos_method": "gerg2008",
        "method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        "poly_eff": 82.0,
        "num_stages": 2,
        "intercooler_t": 35.0,
    }
    results = ThermoEngine().calculate_design_performance(inputs)
    assert results["t_out"] > 0.0
    assert results["power_shaft_total_kw"] > 0.0
    assert results["_effective_eos"] == "gerg2008"


def test_true_isentropic_exponent_and_cp_cv_are_distinct():
    """k_s (a²ρ/P) must be stored separately from Cp/Cv for real gases."""
    solver = ThermodynamicSolver()
    gas_data = {
        "ids": ["methane", "ethane", "propane", "nitrogen", "carbon dioxide"],
        "mol_fractions": [0.88, 0.07, 0.03, 0.01, 0.01],
        "MW": 18.27,
    }
    state = solver.get_properties(20.0e5, 298.15, gas_data, "gerg2008")
    computed = state.speed_of_sound ** 2 * state.density / state.P
    assert state.k_s == pytest.approx(computed, rel=1e-6)
    assert state.k_s < state.k  # real-gas κ_s differs from Cp/Cv


def test_dak_z_factor_estimate():
    """DAK estimate must be physical and close to the GERG-2008 reference."""
    from kasp.core.z_factor import estimate_z_factor

    composition = {
        "METHANE": 88.0,
        "ETHANE": 7.0,
        "PROPANE": 3.0,
        "NITROGEN": 1.0,
        "CARBONDIOXIDE": 1.0,
    }
    estimate = estimate_z_factor(composition, 20.0e5, 298.15)
    assert estimate["valid"] is True
    assert 0.5 < estimate["z_factor"] < 1.05
    # GERG-2008 reference for the same state is ~0.95545.
    assert abs(estimate["z_factor"] - 0.95545) < 0.01
