import pytest
from kasp.core.thermo import ThermoEngine


def test_analyze_operating_envelope_p17_compliance():
    """Verify missing surge/stonewall data returns None instead of 0.0 per P1-7."""
    engine = ThermoEngine()

    # 1. None inputs must not raise AttributeError
    res_none = engine.analyze_operating_envelope(None, None)
    assert res_none["operating_region"] == "UNKNOWN"
    assert res_none["surge_distance_percent"] is None
    assert res_none["stonewall_distance_percent"] is None
    assert res_none["safe_operating_margin"] is None

    # 2. Compressor with stonewall but no surge data (surge_flow = 0)
    comp_no_surge = {"surge_flow": 0, "stonewall_flow": 120.0}
    op_cond = {"flow": 50.0}
    res_no_surge = engine.analyze_operating_envelope(comp_no_surge, op_cond)
    # surge_distance_percent must be None (NOT 0.0 which would indicate 0% critical surge!)
    assert res_no_surge["surge_distance_percent"] is None
    assert res_no_surge["stonewall_distance_percent"] is not None
    assert res_no_surge["safe_operating_margin"] == res_no_surge["stonewall_distance_percent"]

    # 3. Placeholder values (1000.0, 9999.0, <= 0.05) must be treated as missing
    comp_placeholder = {"surge_flow": 0.02, "stonewall_flow": 9999.0}
    res_ph = engine.analyze_operating_envelope(comp_placeholder, op_cond)
    assert res_ph["operating_region"] == "UNKNOWN"
    assert res_ph["surge_distance_percent"] is None
    assert res_ph["stonewall_distance_percent"] is None


def test_evaluate_performance_status_missing_keys():
    """Verify _evaluate_performance_status handles partial or empty deviation dicts without KeyError."""
    engine = ThermoEngine()

    # Empty dict
    status_empty = engine._evaluate_performance_status({})
    assert "status" in status_empty

    # Partial dict missing heat_rate and power
    status_partial = engine._evaluate_performance_status({"deviation_poly_eff": 1.5})
    assert status_partial["status"] == "EXCELLENT"
