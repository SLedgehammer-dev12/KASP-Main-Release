import pytest
from kasp.core.pipe_sizing import get_sorted_pipes, size_single_pipe


def test_get_sorted_pipes_zero_and_negative_factors():
    """Verify get_sorted_pipes does not crash with ZeroDivisionError when factors are zero or negative."""
    # F = 0.0 or negative
    pipes_zero_f = get_sorted_pipes(5000000.0, SMYS_mpa=483.0, F=0.0)
    assert len(pipes_zero_f) > 0

    pipes_neg_f = get_sorted_pipes(5000000.0, SMYS_mpa=483.0, F=-0.5)
    assert len(pipes_neg_f) > 0

    # SMYS = 0.0
    pipes_zero_smys = get_sorted_pipes(5000000.0, SMYS_mpa=0.0, F=0.50)
    assert len(pipes_zero_smys) > 0


def test_size_single_pipe_zero_design_factor():
    """Verify size_single_pipe survives design_factor_F = 0.0 gracefully."""
    res = size_single_pipe(
        flow_kgs=30.0,
        p_bar=50.0,
        t_c=25.0,
        design_factor_F=0.0,
    )
    assert "nominal_size_in" in res
    assert res["actual_velocity_ms"] > 0
