import pytest
import math
from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.models import ThermodynamicState


def test_calculate_dimensionless_coeffs_resilience():
    """Verify calculate_dimensionless_coeffs handles None, negative head, and invalid inputs gracefully."""
    # 1. None inputs must not raise AttributeError and return None
    assert CompressorAerodynamics.calculate_dimensionless_coeffs(None, None, 50.0) is None
    assert CompressorAerodynamics.calculate_dimensionless_coeffs({}, None, 50.0) is None

    # 2. Negative head_kj_kg must not crash with TypeError (complex comparison)
    bad_results = {"head_kj_kg": -120.0, "num_stages": 2}
    inlet_props = {"rho": 1.2, "a": 340.0, "mu": 1.8e-5}
    res = CompressorAerodynamics.calculate_dimensionless_coeffs(bad_results, inlet_props, 25.0)
    # Negative head cannot produce valid compressor aerodynamics; should safely return None without crashing
    assert res is None

    # 3. Negative mass flow should not raise math domain error on sqrt or return negative flow coefficient
    res_neg_flow = CompressorAerodynamics.calculate_dimensionless_coeffs(
        {"head_kj_kg": 150.0, "num_stages": 1}, inlet_props, -10.0
    )
    assert res_neg_flow is None or res_neg_flow.get("phi") == 0.0


def test_calculate_schultz_factor_invalid_states():
    """Verify calculate_schultz_factor safely returns 1.0 on unphysical/negative pressure or temperature."""
    state_in = ThermodynamicState(
        P=0.0, T=300.0, H=500.0, S=2.0, Z=1.0, k=1.3, MW=16.0,
        Cp=2000.0, Cv=1500.0, density=1.0, phase="gas"
    )
    state_out = ThermodynamicState(
        P=100000.0, T=350.0, H=600.0, S=2.1, Z=1.0, k=1.3, MW=16.0,
        Cp=2000.0, Cv=1500.0, density=1.2, phase="gas"
    )
    # Should safely return 1.0 without unhandled math domain error
    f_t = CompressorAerodynamics.calculate_schultz_factor(
        state_in, state_out, 100000.0, None, None, "coolprop", 500.0
    )
    assert f_t == 1.0


def test_calculate_isentropic_temp_fallback_safety():
    """Verify calculate_isentropic_temp_fallback clamps zero or negative pressures."""
    state_in = ThermodynamicState(
        P=0.0, T=300.0, H=500.0, S=2.0, Z=1.0, k=1.3, MW=16.0,
        Cp=2000.0, Cv=1500.0, density=1.0, phase="gas"
    )
    t_out = CompressorAerodynamics.calculate_isentropic_temp_fallback(
        state_in, -50000.0, None, None, "coolprop"
    )
    assert math.isfinite(t_out)
    assert t_out >= 1.0
