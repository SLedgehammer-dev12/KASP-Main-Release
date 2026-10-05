"""Tests for the Petrobras ccp integration adapter (CCPAdapter)."""

import pytest


def test_ccp_adapter_calculate_performance_pure_methane():
    """Verify CCPAdapter.calculate_performance successfully computes compressor state."""
    pytest.importorskip("ccp", reason="petrobras/ccp library required")
    from kasp.core.ccp_interface import CCPAdapter, is_ccp_available

    assert is_ccp_available() is True

    adapter = CCPAdapter()
    inputs = {
        "gas_comp": {"METHANE": 100.0},
        "p_in": 1.5,
        "p_in_unit": "bar",
        "t_in": 25.0,
        "t_in_unit": "degC",
        "p_out": 4.5,
        "p_out_unit": "bar",
        "flow": 5.0,
        "flow_unit": "kg/s",
        "poly_eff": 80.0,
        "speed": 8000.0,
        "blade_height": 0.03,
        "impeller_diameter": 0.35,
    }

    results = adapter.calculate_performance(inputs)

    assert results["t_out"] > 298.15
    assert results["p_out"] == pytest.approx(450000.0, rel=1e-2)
    assert results["head_kj_kg"] > 50.0
    assert results["power_kw"] > 0.0
    assert 0.0 < results["efficiency"] < 1.5
    assert 0.8 < results["z_avg"] < 1.2
    assert "CCP" in results["calculation_backend"]


def test_ccp_adapter_missing_optional_units():
    """Verify CCPAdapter safely handles inputs where p_out_unit is omitted."""
    pytest.importorskip("ccp", reason="petrobras/ccp library required")
    from kasp.core.ccp_interface import CCPAdapter

    adapter = CCPAdapter()
    inputs = {
        "gas_comp": {"methane": 1.0},  # 0-1 scale mole fraction
        "p_in": 2.0,
        "p_unit": "bar",
        "p_out": 5.0,
        # p_out_unit intentionally omitted
        "t_in": 30.0,
        "t_unit": "degC",
        "flow": 2.5,
        "flow_unit": "kg/s",
    }

    results = adapter.calculate_performance(inputs)
    assert results["p_out"] == pytest.approx(500000.0, rel=1e-2)
    assert results["head_kj_kg"] > 0.0
    assert results["power_kw"] > 0.0


def test_ccp_adapter_comparison_with_kasp():
    """Verify compare_with_kasp produces accurate delta percentages without errors."""
    pytest.importorskip("ccp", reason="petrobras/ccp library required")
    from kasp.core.ccp_interface import CCPAdapter

    adapter = CCPAdapter()
    kasp_results = {
        "t_out": 85.0,  # °C -> 358.15 K
        "head_kj_kg": 150.0,
        "power_unit_kw": 800.0,
        "actual_poly_efficiency": 0.82,
    }
    ccp_results = {
        "t_out": 360.0,
        "head_kj_kg": 153.0,
        "power_kw": 810.0,
        "efficiency": 0.83,
    }

    comp = adapter.compare_with_kasp(kasp_results, ccp_results)

    assert "t_out_diff_percent" in comp
    assert "head_diff_percent" in comp
    assert "power_diff_percent" in comp
    assert "efficiency_diff_percent" in comp
    assert "max_deviation_percent" in comp
    assert comp["agreement_status"] in ("Excellent", "Good", "Acceptable", "Poor")
    assert abs(comp["t_out_diff_percent"]) < 5.0
