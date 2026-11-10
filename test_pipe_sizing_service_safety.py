import pytest
from kasp.services.pipe_sizing_service import PipeSizingService
from kasp.core.pipe_sizing import calculate_pipe_weight_api5l


def test_calculate_pipe_weight_bounds():
    """Verify calculate_pipe_weight_api5l never returns negative weight when thickness >= OD or invalid."""
    assert calculate_pipe_weight_api5l(50.0, 60.0) == 0.0  # t > OD
    assert calculate_pipe_weight_api5l(50.0, 50.0) == 0.0  # t == OD
    assert calculate_pipe_weight_api5l(-10.0, 5.0) == 0.0
    assert calculate_pipe_weight_api5l(100.0, 5.0) > 0.0


def test_size_station_network_none_temperatures_and_bad_types():
    """Verify size_station_network does not crash on None or string temperature inputs."""
    res = PipeSizingService.size_station_network(
        mass_flow_kgs=50.0,
        p_in_bar=25.0,
        p_out_bar=75.0,
        t_in_c=None,
        t_discharge_c=None,
        t_cooled_c=None,
        comp_op_count=2,
        cyclone_op_count=2,
        filter_op_count=2,
        cooler_bays_count=2,
    )
    assert "lines" in res
    assert len(res["lines"]) >= 10
    assert res["lines"]["mainline_inlet"]["actual_velocity_ms"] > 0
