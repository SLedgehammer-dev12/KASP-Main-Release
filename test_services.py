"""Unit and integration tests for the KASP Services Layer (`kasp/services/`)."""

import pytest
from kasp.services.gas_service import (
    standard_composition_for_gas,
    normalize_composition_dict,
    build_total_label_state,
    get_smart_eos_recommendation,
    get_smart_method_recommendation,
    get_kij_matrix_for_composition,
)
from kasp.services.validation_service import (
    validate_pressure,
    validate_temperature,
    validate_flow,
    validate_pressure_ratio,
    validate_design_inputs,
)
from kasp.services.design_input_service import (
    ENGINEERING_PRESETS,
    GUIDANCE_TEXTS,
    calculate_live_metrics,
)
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.performance_service import evaluate_field_performance
from kasp.services.chart_data_builder import build_all_chart_payloads


def test_gas_service_standards_and_normalization():
    ch4 = standard_composition_for_gas("methane")
    assert ch4 == {"METHANE": 100.0}

    air = standard_composition_for_gas("air")
    assert "NITROGEN" in air and "OXYGEN" in air

    comp = {"METHANE": 80.0, "ETHANE": 10.0, "CO2": 10.0}
    norm = normalize_composition_dict(comp)
    assert sum(norm.values()) == pytest.approx(100.0, 1e-4)

    text, state = build_total_label_state(100.0)
    assert state == "valid"

    text, state = build_total_label_state(99.5)
    assert state == "warning"

    text, state = build_total_label_state(85.0)
    assert state == "invalid"


def test_gas_service_smart_recommendations():
    rec_pure = get_smart_eos_recommendation({"METHANE": 100.0})
    assert rec_pure["category"] == "pure"
    assert rec_pure["recommended_eos"] == "coolprop"

    rec_polar = get_smart_eos_recommendation({"METHANE": 80.0, "WATER": 5.0, "HYDROGENSULFIDE": 15.0})
    assert rec_polar["category"] == "polar"
    assert rec_polar["recommended_eos"] == "neqsim"

    rec_method = get_smart_method_recommendation({"METHANE": 80.0, "ETHANE": 20.0}, p_in=10.0, p_out=45.0)
    assert "PR=" in rec_method["title"]


def test_gas_service_kij_matrix():
    comp = {"METHANE": 85.0, "CARBONDIOXIDE": 10.0, "NITROGEN": 5.0}
    kij_res = get_kij_matrix_for_composition(comp)
    assert kij_res["size"] == 3
    assert len(kij_res["matrix"]) == 3
    # Check symmetry
    for i in range(3):
        assert kij_res["matrix"][i][i] == 0.0
        for j in range(3):
            assert kij_res["matrix"][i][j] == kij_res["matrix"][j][i]

    # Test override
    override_res = get_kij_matrix_for_composition(comp, custom_overrides={"METHANE:CARBONDIOXIDE": 0.22})
    idx_m = kij_res["components"].index("METHANE")
    idx_c = kij_res["components"].index("CARBONDIOXIDE")
    assert override_res["matrix"][idx_m][idx_c] == 0.22


def test_validation_service():
    ok, msg, sev = validate_pressure("20.5", "bar(a)")
    assert ok and sev == "ok"

    ok, msg, sev = validate_pressure("-1.5", "bar(g)")
    assert not ok and sev == "error"

    ok, msg, sev = validate_temperature("25.0", "°C")
    assert ok and sev == "ok"

    ok, msg, sev = validate_temperature("-275.0", "°C")
    assert not ok and "mutlak sıfır" in msg.lower()

    ok, msg, sev = validate_flow("1500.0", "kg/h")
    assert ok and sev == "ok"

    ok, pr, msg, sev = validate_pressure_ratio(20.0, "bar(a)", 60.0, "bar(a)", num_stages=1)
    assert ok and pr == 3.0


def test_design_input_service():
    assert len(ENGINEERING_PRESETS) == 4
    assert "p_in" in GUIDANCE_TEXTS
    metrics = calculate_live_metrics(20.0, "bar(a)", 50.0, "bar(a)")
    assert metrics["valid"] is True
    assert metrics["pr"] == 2.5


def test_calculation_service_and_chart_builder():
    inputs = {
        "p_in": 25.0,
        "p_in_unit": "bar(a)",
        "p_out": 75.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "poly_eff": 80.0,
        "num_stages": 2,
        "intercooler_t": 35.0,
        "eos_model": "coolprop",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz"
    }

    results = execute_design_calculation(inputs)
    assert "actual_poly_efficiency" in results
    assert "selected_units" in results
    assert len(results["selected_units"]) > 0

    # Stage display fields must be bar(a) / °C while canonical fields stay Pa/K.
    first_stage = results["stages"][0]
    assert first_stage["p_in_bar"] == pytest.approx(first_stage["p_in"] / 1e5, rel=1e-6)
    assert first_stage["t_in_c"] == pytest.approx(first_stage["t_in"] - 273.15, abs=0.02)

    charts = build_all_chart_payloads(inputs, results, results["selected_units"])
    assert "ts_diagram" in charts
    assert "pv_diagram" in charts
    assert "hs_mollier" in charts
    assert "power_sankey" in charts
    assert "kz_path" in charts
    assert "stage_overview" in charts
    assert "turbine_radar" in charts
    assert "architecture_svg" in charts
    assert "<svg" in charts["architecture_svg"]
    # Chart payloads must expose bar(a), not Pa.
    assert 20.0 <= charts["ts_diagram"]["actual_path"]["p_bar"][0] <= 40.0
    assert charts["pv_diagram"]["polytropic_path"]["p"][0] == pytest.approx(25.0, abs=0.5)
    assert charts["pv_diagram"]["polytropic_path"]["p"][-1] == pytest.approx(75.0, abs=0.5)


def test_performance_service():
    field_data = {
        "p_in": 20.0,
        "p_in_unit": "bar(g)",
        "p_out": 55.0,
        "p_out_unit": "bar(g)",
        "t_in": 22.0,
        "t_in_unit": "°C",
        "t_out": 68.0,
        "t_out_unit": "°C",
        "flow": 15.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 100.0},
        "eos_method": "coolprop",
    }
    perf_res = evaluate_field_performance(field_data)
    assert "comparison" in perf_res
    assert len(perf_res["comparison"]) == 6
    assert any(c["parameter"] == "Giriş Basıncı" for c in perf_res["comparison"])
    # Web UI contract aliases and status labels must be present.
    for row in perf_res["comparison"]:
        assert "name" in row and "test_val" in row and "design_val" in row
        assert "dev_pct" in row and "tol_crit" in row
        assert row["status"] in {"OK", "WARNING", "CRITICAL"}
