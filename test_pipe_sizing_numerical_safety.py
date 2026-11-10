import pytest
from kasp.core.pipe_sizing import (
    churchill_friction_factor,
    size_single_pipe,
    calculate_erosion_velocity,
)


def test_churchill_friction_factor_low_reynolds_bounded():
    """Friction factor must not diverge to millions for very small creeping Re numbers."""
    f_tiny = churchill_friction_factor(Re=0.0001, relative_roughness=0.001)
    assert f_tiny <= 0.10, f"Expected friction factor <= 0.10, got {f_tiny}"
    assert f_tiny >= 0.005


def test_size_single_pipe_extreme_temperatures():
    """size_single_pipe must clamp absolute temperatures to avoid ZeroDivisionError or negative densities."""
    res = size_single_pipe(
        flow_kgs=10.0,
        p_bar=50.0,
        t_c=-350.0,  # Below absolute zero
        mw=18.2,
    )
    assert res["gas_density_kgm3"] > 0
    assert res["actual_velocity_ms"] > 0


def test_size_single_pipe_zero_and_negative_mw():
    """size_single_pipe must guard against mw <= 0 causing ZeroDivisionError in R_gas."""
    res = size_single_pipe(
        flow_kgs=10.0,
        p_bar=50.0,
        t_c=25.0,
        mw=0.0,
    )
    assert res["gas_density_kgm3"] > 0
    assert res["nominal_size_in"] != ""


def test_calculate_erosion_velocity_zero_c_empirical():
    """C_empirical <= 0 must fallback to standard continuous service constant."""
    v_e = calculate_erosion_velocity(density_kg_m3=35.0, C_empirical=0.0)
    assert v_e > 0
