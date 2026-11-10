import pytest
from kasp.core.z_factor import estimate_z_factor, dak_z_factor


def test_estimate_z_factor_returns_warning_instead_of_crash_when_out_of_bounds():
    """estimate_z_factor must return valid=False with warning and physical Z when out of bounds."""
    # Natural gas composition
    comp = {"Methane": 0.90, "Ethane": 0.07, "Propane": 0.03}

    # Extremely high pressure leading to ppr > 30.0 or low temperature tpr < 1.0
    res = estimate_z_factor(comp, pressure_pa=200e6, temperature_k=150.0)

    assert isinstance(res, dict)
    assert res["valid"] is False
    assert len(res["warnings"]) > 0
    assert "gecerlilik araligi disinda" in res["warnings"][0]
    # Z-factor must be a valid, positive finite number
    assert 0.2 < res["z_factor"] < 5.0


def test_dak_z_factor_clamp_bounds_option():
    """dak_z_factor with clamp_bounds=True must evaluate safely without raising ValueError."""
    # Without clamp_bounds: raises ValueError
    with pytest.raises(ValueError):
        dak_z_factor(ppr=35.0, tpr=1.5, clamp_bounds=False)

    # With clamp_bounds: calculates safely
    z_clamped = dak_z_factor(ppr=35.0, tpr=1.5, clamp_bounds=True)
    assert 0.2 < z_clamped < 5.0
