import pytest
from kasp.core.thermo import ThermoEngine


def test_calculate_design_energy_context_string_therm_eff():
    """Verify _calculate_design_energy_context handles string therm_eff without TypeError."""
    engine = ThermoEngine()
    
    # Minimal mock context and stage_loop
    gas_comp = {"CH4": 1.0}
    gas_obj = engine._create_gas_object(gas_comp, "pr")
    context = {
        "p_in_pa": 2000000.0,
        "p_out_pa": 6000000.0,
        "t_in_k": 300.0,
        "gas_obj": gas_obj,
        "eos": "pr",
        "mass_flow_per_unit": 25.0,
    }
    stage_loop = {
        "final_t_out_k": 400.0,
        "total_stage_gas_power_kw": 3000.0,
        "total_poly_head_kj_kg": 120.0,
        "staged_results": [],
    }
    
    # Input with string therm_eff (which triggered TypeError: '>' not supported between 'str' and 'float')
    inputs = {
        "therm_eff": "38.5",
        "mech_eff": "98.0",
        "gas_comp": gas_comp,
    }
    energy_ctx = engine._calculate_design_energy_context(inputs, context, stage_loop)
    assert energy_ctx["total_shaft_kw"] > 3000.0
    assert energy_ctx["fuel_kgh"] > 0


def test_generate_summary_report_safety_and_fractions():
    """Verify generate_summary_report handles None inputs and normalizes 0-1 / 0-100 efficiencies."""
    engine = ThermoEngine()

    # None inputs must return empty dict or default structure without crashing
    res_none = engine.generate_summary_report(None, None, None)
    assert isinstance(res_none, dict)

    # Fractions already in 0-1 range (e.g., 0.85 poly_eff and 0.35 therm_eff)
    inputs = {"poly_eff": 0.85, "therm_eff": 0.35, "project_name": "Test Project"}
    results = {"compression_ratio": 2.5, "power_unit_kw": 5000.0}
    rep = engine.generate_summary_report(inputs, results, [])
    assert rep["efficiency_metrics"]["poly_efficiency"] == pytest.approx(0.85, rel=1e-3)
    assert rep["efficiency_metrics"]["thermal_efficiency"] == pytest.approx(0.35, rel=1e-3)
