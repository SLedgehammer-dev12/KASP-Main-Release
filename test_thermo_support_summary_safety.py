import pytest
from kasp.core.thermo_support import build_summary_report, evaluate_performance_status


def test_thermo_support_build_summary_report_safety():
    """Verify build_summary_report in thermo_support handles None and normalized efficiencies."""
    # 1. None inputs must not raise AttributeError
    res_none = build_summary_report(None, None, None, {})
    assert isinstance(res_none, dict)
    assert res_none["project_name"] == "Bilinmiyor"

    # 2. Efficiencies already in 0-1 range (e.g. 0.82 poly_eff)
    inputs = {"poly_eff": 0.82, "therm_eff": 0.36, "project_name": "Pipeline CS"}
    results = {"compression_ratio": 3.0}
    res = build_summary_report(inputs, results, [], {})
    assert res["efficiency_metrics"]["poly_efficiency"] == pytest.approx(0.82, rel=1e-3)
    assert res["efficiency_metrics"]["thermal_efficiency"] == pytest.approx(0.36, rel=1e-3)


def test_thermo_support_evaluate_performance_status_missing_keys():
    """Verify evaluate_performance_status in thermo_support handles empty or partial dicts without KeyError."""
    # Empty dict
    res_empty = evaluate_performance_status({})
    assert "status" in res_empty

    # Partial dict
    res_partial = evaluate_performance_status({"deviation_poly_eff": 1.2})
    assert res_partial["status"] == "EXCELLENT"
