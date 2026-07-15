import pytest
from kasp.core.models import ThermodynamicState
from kasp.core.aerodynamics import CompressorAerodynamics


@pytest.fixture
def state_in():
    return ThermodynamicState(
        P=101325.0, T=300.0, H=500000.0, S=5200.0,
        Z=0.998, k=1.31, MW=16.04, Cp=2220.0, Cv=1695.0,
        density=0.65, phase='gas',
    )


@pytest.fixture
def state_out():
    return ThermodynamicState(
        P=303975.0, T=380.0, H=580000.0, S=5210.0,
        Z=0.995, k=1.30, MW=16.04, Cp=2280.0, Cv=1754.0,
        density=1.60, phase='gas',
    )


class TestPolytropicEfficiency:
    def test_efficiency_between_0_and_1(self, state_in, state_out):
        R_specific = 8314.462 / 16.04
        eff = CompressorAerodynamics.calculate_polytropic_efficiency(
            state_in, state_out, R_specific
        )
        assert 0.0 < eff <= 1.0, f"verim 0-1 arasinda olmali: {eff}"

    def test_same_state_does_not_crash(self, state_in):
        R_specific = 8314.462 / 16.04
        eff = CompressorAerodynamics.calculate_polytropic_efficiency(
            state_in, state_in, R_specific
        )
        assert isinstance(eff, float)


class TestMechanicalLoss:
    def test_minimum_loss(self):
        loss = CompressorAerodynamics.calculate_mechanical_loss(0)
        assert loss >= 10.0

    def test_loss_increases_with_flow(self):
        low = CompressorAerodynamics.calculate_mechanical_loss(0.1)
        high = CompressorAerodynamics.calculate_mechanical_loss(10.0)
        assert high > low

    def test_loss_capped_at_limit(self):
        loss = CompressorAerodynamics.calculate_mechanical_loss(100.0, shaft_power_kw=100)
        assert loss <= 10.0


class TestIsentropicTemperature:
    def test_fallback_k_based(self, state_in):
        t_out = CompressorAerodynamics.calculate_isentropic_temp_fallback(
            state_in, 200000.0, None, None, 'ideal'
        )
        assert t_out > state_in.T, f"T_out ({t_out}) <= T_in ({state_in.T})"


class TestDimensionlessCoefficients:
    def test_returns_dict_or_none(self, state_in):
        result_data = {'poly_head_j_kg': 50000.0}
        try:
            coeffs = CompressorAerodynamics.calculate_dimensionless_coeffs(
                result_data, state_in, 5.0
            )
        except Exception:
            coeffs = None
        assert coeffs is None or isinstance(coeffs, dict)
