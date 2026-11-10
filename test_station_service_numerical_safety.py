import pytest
from kasp.services.station_service import calculate_station_process_model


def test_station_service_negative_and_zero_pressures():
    """Verify calculate_station_process_model survives negative or zero pressures without math domain error."""
    # Negative inlet pressure
    res_neg = calculate_station_process_model({"p_in": -5.0, "p_out": 10.0})
    assert res_neg["success"] is True
    assert res_neg["station_summary"]["suction_pressure_bar"] >= 0.5
    assert res_neg["station_summary"]["pressure_ratio"] >= 1.05
    assert res_neg["station_summary"]["total_power_kw"] > 0

    # Zero inlet and outlet pressures
    res_zero = calculate_station_process_model({"p_in": 0.0, "p_out": 0.0})
    assert res_zero["success"] is True
    assert res_zero["station_summary"]["suction_pressure_bar"] >= 0.5
    assert res_zero["station_summary"]["pressure_ratio"] >= 1.05


def test_station_service_extreme_subzero_temperature():
    """Verify sub-absolute zero temperature inputs do not crash with Rust panic."""
    res_subzero = calculate_station_process_model({"t_in": -300.0})
    assert res_subzero["success"] is True
    # Suction temperature should be clamped safely above absolute zero
    assert res_subzero["nodes"][0]["temp_c"] >= -100.0
    assert res_subzero["station_summary"]["suction_density_kgm3"] > 0


def test_station_service_invalid_strings_and_zero_efficiency():
    """Verify non-numeric strings and zero efficiency fall back safely without unhandled exceptions."""
    res_bad = calculate_station_process_model(
        {"p_in": "invalid_press", "t_in": "invalid_temp", "mass_flow": "invalid_flow"},
        design_results={"actual_poly_efficiency": 0.0},
    )
    assert res_bad["success"] is True
    assert res_bad["station_summary"]["total_mass_flow_kgs"] >= 0.5
    assert res_bad["station_summary"]["total_power_kw"] > 0
