import pytest
from kasp.services.chart_data_builder import (
    build_turbine_derate_chart_data,
    build_operating_envelope_data,
    build_convergence_chart_data,
)


def test_turbine_derate_chart_none_and_strings():
    """Verify build_turbine_derate_chart_data tolerates None, empty dicts, and invalid string values."""
    # When inputs and results are None
    data = build_turbine_derate_chart_data(None, None, None)
    assert isinstance(data, dict)
    assert "data" in data or "traces" in data or "layout" in data

    # When inputs contain non-numeric strings
    bad_inputs = {
        "site_temp": "invalid_temp",
        "altitude": "bad_alt",
        "ambient_pressure": "bad_press",
    }
    bad_results = {
        "power_unit_kw": "bad_pwr",
        "selected_units": [
            {"model": "TestTurbine", "iso_power_kw": "bad_iso", "iso_heat_rate_kj_kwh": "bad_hr"}
        ]
    }
    data2 = build_turbine_derate_chart_data(bad_inputs, bad_results)
    assert isinstance(data2, dict)
    assert len(data2.get("data", [])) > 0


def test_operating_envelope_none_and_zero():
    """Verify build_operating_envelope_data handles None and zero values safely."""
    data = build_operating_envelope_data(None, None, None)
    assert isinstance(data, dict)
    assert "data" in data

    zero_results = {
        "inlet_vol_flow_acmh_per_unit": 0.0,
        "rho_in": 0.0,
        "mass_flow_per_unit_kgs": 0.0,
        "head_kj_kg": 0.0,
        "compression_ratio": 0.0,
    }
    data_zero = build_operating_envelope_data({}, zero_results)
    assert isinstance(data_zero, dict)
    assert len(data_zero.get("data", [])) > 0


def test_convergence_chart_none():
    """Verify build_convergence_chart_data handles None results safely."""
    data = build_convergence_chart_data(None)
    assert isinstance(data, dict)
    assert data.get("iterations") == []
    assert data.get("residuals") == []
