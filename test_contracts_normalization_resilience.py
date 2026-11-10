import pytest
from kasp.core.contracts import normalize_design_inputs


def test_normalize_ambient_pressure_direct_mbar():
    """ambient_pressure > 200 (e.g. 1013.25 mbar) must be normalized to kPa (101.325)."""
    raw_inputs = {
        "ambient_pressure": 1013.25,
    }
    normalized = normalize_design_inputs(raw_inputs)
    assert normalized["ambient_pressure"] == pytest.approx(101.325, rel=1e-4)


def test_normalize_num_stages_and_units_positive_integer():
    """num_stages and num_units must be at least 1."""
    raw_inputs = {
        "num_stages": 0,
        "num_units": -5,
    }
    normalized = normalize_design_inputs(raw_inputs)
    assert normalized["num_stages"] == 1
    assert normalized["num_units"] == 1


def test_normalize_num_stages_valid_preserved():
    """Valid positive num_stages and num_units must be preserved."""
    raw_inputs = {
        "num_stages": 3,
        "num_units": 2,
    }
    normalized = normalize_design_inputs(raw_inputs)
    assert normalized["num_stages"] == 3
    assert normalized["num_units"] == 2
