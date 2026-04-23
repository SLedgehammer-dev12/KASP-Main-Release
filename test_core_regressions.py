import json

import pytest

from kasp.core.contracts import normalize_design_inputs
from kasp.core.properties import COOLPROP_LOADED, ThermodynamicSolver
from kasp.core.thermo import ThermoEngine
from kasp.data.database import compressor_flow_kgh_to_kgs, compressor_flow_kgs_to_kgh
from kasp.utils.project_manager import ProjectManager


def build_design_inputs():
    return {
        "project_name": "Regression",
        "p_in": 5_066_325.0,
        "p_in_unit": "Pa",
        "t_in": 292.15,
        "t_in_unit": "K",
        "p_out": 7_500_000.0,
        "p_out_unit": "Pa",
        "flow": 20.0,
        "flow_unit": "kg/s",
        "num_units": 1,
        "num_stages": 1,
        "intercooler_dp_pct": 0.0,
        "intercooler_t": 313.15,
        "poly_eff": 90.0,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "gas_comp": {"METHANE": 100.0},
        "eos_method": "coolprop",
        "method": "Metot 1: Ortalama Özellikler",
        "use_consistency_iteration": False,
        "ambient_temp": 19.0,
        "ambient_pressure": 101.325,
        "altitude": 0,
        "humidity": 60,
        "enable_uncertainty": False,
    }


def test_thermo_cache_distinguishes_current_mixture_format():
    solver = ThermodynamicSolver(max_cache_size=10)
    gas_a = {"ids": ["methane"], "mol_fractions": [1.0]}
    gas_b = {"ids": ["ethane"], "mol_fractions": [1.0]}

    solver.get_properties(101325.0, 300.0, gas_a, "pr")
    solver.get_properties(101325.0, 300.0, gas_b, "pr")

    assert len(solver._property_cache) == 2


def test_compressor_flow_library_units_round_trip():
    flow_kgh = 18_000.0

    stored_kgs = compressor_flow_kgh_to_kgs(flow_kgh)

    assert stored_kgs == pytest.approx(5.0)
    assert compressor_flow_kgs_to_kgh(stored_kgs) == pytest.approx(flow_kgh)


def test_design_input_normalizer_applies_aliases_and_preserves_extra_fields():
    normalized = normalize_design_inputs(
        {
            "project_name": "Normalized",
            "ambient_press": 1013,
            "consistency_check": True,
            "enable_uncertainty": True,
            "gas_comp": {"METHANE": 100.0},
        }
    )

    assert normalized["project_name"] == "Normalized"
    assert normalized["ambient_pressure"] == pytest.approx(101.3)
    assert normalized["use_consistency_iteration"] is True
    assert normalized["enable_uncertainty"] is True
    assert normalized["lhv_source"] == "kasp"


@pytest.mark.skipif(not COOLPROP_LOADED, reason="CoolProp is required for design regression tests")
def test_design_performance_separates_design_and_actual_poly_efficiency():
    engine = ThermoEngine()

    results = engine.calculate_design_performance(build_design_inputs())

    assert results["design_poly_efficiency"] == pytest.approx(0.90)
    assert 0.0 < results["actual_poly_efficiency"] < 1.0
    assert results["actual_poly_efficiency"] != pytest.approx(
        results["design_poly_efficiency"], abs=1e-3
    )
    assert results["inlet_properties"]["a"] > 0.0


@pytest.mark.skipif(not COOLPROP_LOADED, reason="CoolProp is required for performance regression tests")
def test_performance_test_returns_reference_and_report_fields():
    engine = ThermoEngine()
    inputs = {
        "p_in": 5_066_325.0,
        "p_in_unit": "Pa",
        "t_in": 292.15,
        "t_in_unit": "K",
        "p_out": 7_500_000.0,
        "p_out_unit": "Pa",
        "t_out": 333.15,
        "t_out_unit": "K",
        "flow": 20.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 100.0},
        "eos_method": "coolprop",
        "fuel_flow": 900.0,
        "lhv_source": "kasp",
        "design_poly_eff": 0.90,
        "design_power_kw": 1200.0,
        "design_heat_rate": 10_000.0,
        "design_therm_eff": 0.35,
        "ambient_temp": 19.0,
        "ambient_pressure": 101.325,
        "humidity": 60.0,
        "altitude": 0.0,
    }

    results = engine.calculate_performance_test(inputs)

    assert results["design_poly_eff"] == pytest.approx(0.90)
    assert results["expected_power"] == pytest.approx(1200.0)
    assert results["expected_heat_rate"] == pytest.approx(10_000.0)
    assert results["deviation_power"] == pytest.approx(
        ((results["actual_power"] - 1200.0) / 1200.0) * 100.0
    )
    assert results["deviation_heat_rate"] == pytest.approx(
        ((results["actual_heat_rate"] - 10_000.0) / 10_000.0) * 100.0
    )
    assert results["test_conditions"]["mass_flow"] == pytest.approx(20.0)
    assert results["corrected_values"]["correction_factors"]["pressure"] == pytest.approx(101.325)


def test_project_manager_round_trip_preserves_stage_and_site_inputs(tmp_path):
    manager = ProjectManager()
    inputs = {
        "project_name": "RoundTrip",
        "notes": "Regression",
        "p_in": 49.65,
        "p_in_unit": "bar(g)",
        "t_in": 19.0,
        "t_in_unit": "°C",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "flow": 1_985_000.0,
        "flow_unit": "Sm³/h",
        "num_units": 2,
        "num_stages": 3,
        "intercooler_dp_pct": 1.5,
        "intercooler_t": 35.0,
        "gas_comp": {"METHANE": 95.0, "ETHANE": 5.0},
        "eos_method": "coolprop",
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 90.0,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "lhv_source": "thermo",
        "use_consistency_iteration": True,
        "max_consistency_iter": 12,
        "consistency_tolerance": 0.05,
        "ambient_temp": 22.0,
        "ambient_pressure": 98.7,
        "altitude": 123.0,
        "humidity": 45.0,
    }

    success, saved_path = manager.save_project(tmp_path / "roundtrip.kasp", inputs, {"ok": True})
    assert success

    success, loaded_inputs, loaded_results = manager.load_project(saved_path)
    assert success
    assert loaded_results == {"ok": True}
    assert loaded_inputs["num_stages"] == 3
    assert loaded_inputs["intercooler_dp_pct"] == pytest.approx(1.5)
    assert loaded_inputs["intercooler_t"] == pytest.approx(35.0)
    assert loaded_inputs["ambient_pressure"] == pytest.approx(98.7)
    assert loaded_inputs["lhv_source"] == "thermo"


def test_project_manager_converts_legacy_ambient_press_to_kpa(tmp_path):
    manager = ProjectManager()
    legacy_file = tmp_path / "legacy.kasp"
    legacy_payload = {
        "version": manager.VERSION,
        "inputs": {
            "project_name": "Legacy",
            "ambient_press": 1013,
        },
        "results": None,
    }
    legacy_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

    success, loaded_inputs, loaded_results = manager.load_project(legacy_file)

    assert success
    assert loaded_results is None
    assert loaded_inputs["ambient_pressure"] == pytest.approx(101.3)
