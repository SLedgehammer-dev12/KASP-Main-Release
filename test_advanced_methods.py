"""
Tests for Metot 5 (Huntington-RK45) and Metot 6 (Schultz 3-Exponent) Integration in KASP
"""

import pytest
import math
import numpy as np

from kasp.core.thermo import ThermoEngine
from kasp.core.thermo_methods import ThermoMethodSuite
from kasp.core.thermo_design_support import select_design_method_key


def test_select_design_method_key_routing():
    assert select_design_method_key("Metot 1: Ortalama Özellikler") == "average"
    assert select_design_method_key("Metot 2: Uç Nokta") == "endpoint"
    assert select_design_method_key("Metot 3: Artımlı Basınç") == "incremental"
    assert select_design_method_key("Metot 4: Doğrudan H-S") == "direct_hs"
    assert select_design_method_key("Metot 5: Huntington-RK45 Diferansiyel") == "huntington_rk45"
    assert select_design_method_key("Metot 6: Schultz 3-Üslü Gerçek Gaz") == "schultz_3exp"


def test_huntington_rk45_methane():
    engine = ThermoEngine()
    suite = engine.method_suite
    gas_comp = {"METHANE": 100.0}
    gas_obj = engine._create_gas_object(gas_comp, "coolprop")
    
    p_in = 30.0 * 1e5
    p_out = 60.0 * 1e5
    t_in = 298.15
    poly_eff = 0.82
    
    t_out, poly_head, z_avg, history = suite.method_huntington_rk45(
        p_in, t_in, p_out, poly_eff, gas_obj, "coolprop", step_count=15
    )

    assert t_out > t_in
    assert poly_head > 0.0
    assert 0.7 < z_avg < 1.1
    assert history["converged"] is True
    assert history["method_used"] == "huntington_rk45"
    assert len(history["temperature"]) >= 2

    # Test fixed-step mode
    t_fixed, poly_fixed, z_fixed, hist_fixed = suite.method_huntington_rk45(
        p_in, t_in, p_out, poly_eff, gas_obj, "coolprop", step_count=15, adaptive=False
    )
    assert len(hist_fixed["temperature"]) == 16
    assert abs(t_out - t_fixed) < 1.0  # Adaptive and fixed should match closely


def test_schultz_3exp_methane():
    engine = ThermoEngine()
    suite = engine.method_suite
    gas_comp = {"METHANE": 100.0}
    gas_obj = engine._create_gas_object(gas_comp, "coolprop")
    
    p_in = 30.0 * 1e5
    p_out = 60.0 * 1e5
    t_in = 298.15
    poly_eff = 0.82
    
    t_out, poly_head, z_avg, history = suite.method_schultz_3exp(
        p_in, t_in, p_out, poly_eff, gas_obj, "coolprop", max_iter=50, tolerance=0.01
    )
    
    assert t_out > t_in
    assert poly_head > 0.0
    assert 0.7 < z_avg < 1.1
    assert history["converged"] is True
    assert history["method_used"] == "schultz_3exp"
    assert "X" in history
    assert "Y" in history
    assert "n_v" in history


def test_full_design_performance_with_metot5_and_metot6():
    engine = ThermoEngine()
    gas_comp = {
        "METHANE": 85.0,
        "ETHANE": 8.0,
        "PROPANE": 4.0,
        "BUTANE": 2.0,
        "NITROGEN": 1.0,
    }
    
    inputs_base = {
        "p_in": 30.0,
        "p_in_unit": "bar",
        "p_out": 55.0,
        "p_out_unit": "bar",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 500000.0,
        "flow_unit": "Sm³/h",
        "gas_comp": gas_comp,
        "eos_method": "thermopack",
        "num_units": 1,
        "num_stages": 1,
        "poly_eff": 82.0,
        "mech_eff": 98.0,
        "solver_method": "auto",
        "enable_uncertainty": False,
    }
    
    # Run Metot 4
    res_m4 = engine.calculate_design_performance({**inputs_base, "method": "Metot 4: Doğrudan H-S"})
    # Run Metot 5
    res_m5 = engine.calculate_design_performance({**inputs_base, "method": "Metot 5: Huntington-RK45 Diferansiyel"})
    # Run Metot 6
    res_m6 = engine.calculate_design_performance({**inputs_base, "method": "Metot 6: Schultz 3-Üslü Gerçek Gaz"})
    
    h4 = res_m4["stages"][0]["head_kj_kg"]
    h5 = res_m5["stages"][0]["head_kj_kg"]
    h6 = res_m6["stages"][0]["head_kj_kg"]
    
    assert h4 > 0 and h5 > 0 and h6 > 0
    delta_h5_h4_pct = abs(h5 - h4) / h4 * 100.0
    assert delta_h5_h4_pct < 6.0, f"M5 vs M4 delta too high: {delta_h5_h4_pct:.2f}%"
    
    delta_h6_h4_pct = abs(h6 - h4) / h4 * 100.0
    assert delta_h6_h4_pct < 6.0, f"M6 vs M4 delta too high: {delta_h6_h4_pct:.2f}%"


def test_multistage_with_metot5():
    engine = ThermoEngine()
    inputs = {
        "p_in": 15.0,
        "p_in_unit": "bar",
        "p_out": 60.0,
        "p_out_unit": "bar",
        "t_in": 30.0,
        "t_in_unit": "°C",
        "flow": 300000.0,
        "flow_unit": "Sm³/h",
        "gas_comp": {"METHANE": 95.0, "ETHANE": 5.0},
        "eos_method": "thermopack",
        "method": "Metot 5: Huntington-RK45 Diferansiyel",
        "num_units": 1,
        "num_stages": 2,
        "intercooler_dp": 0.02,
        "intercooler_t": 35.0,
        "poly_eff": 80.0,
        "mech_eff": 98.0,
        "solver_method": "auto",
        "enable_uncertainty": False,
    }
    
    res = engine.calculate_design_performance(inputs)
    assert len(res["stages"]) == 2
    assert res["stages"][0]["head_kj_kg"] > 0
    assert res["stages"][1]["head_kj_kg"] > 0
    assert res["power_shaft_per_unit_kw"] > 0


def test_smart_method_recommendation():
    from kasp.ui.gas_composition_workflow import get_smart_method_recommendation
    
    # Pure fluid
    rec_pure = get_smart_method_recommendation({"METHANE": 100.0})
    assert "Saf Akışkan" in rec_pure
    assert "Metot 4" in rec_pure or "Metot 5" in rec_pure
    
    # Polar fluid
    rec_polar = get_smart_method_recommendation({"METHANE": 80.0, "WATER": 5.0, "CO2": 15.0})
    assert "Polar / Asit Gazı" in rec_polar
    assert "Metot 4" in rec_polar
    
    # Rich hydrocarbon
    rec_rich = get_smart_method_recommendation({
        "METHANE": 75.0, "ETHANE": 10.0, "PROPANE": 8.0, "HEXANE": 2.0, "HEPTANE": 1.0
    })
    assert "Zengin Gaz" in rec_rich
    assert "Metot 5" in rec_rich
    
    # Lean sales gas
    rec_lean = get_smart_method_recommendation({"METHANE": 92.0, "ETHANE": 5.0, "NITROGEN": 3.0})
    assert "Kuru Satış Gazı" in rec_lean
    assert "Metot 5" in rec_lean or "Metot 4" in rec_lean


def test_design_method_options_ordering():
    from kasp.ui.design_left_panel_builders import get_design_method_options
    options = get_design_method_options()
    
    # Ensure 6 methods are present
    assert len(options) == 6
    # Ensure Metot 5 and Metot 4 are at the top
    assert "Metot 5" in options[0]
    assert "Metot 4" in options[1]
    assert "Metot 6" in options[2]

