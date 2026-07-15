"""
Pure methane known thermodynamic values (NIST REFPROP reference).

Validates that CoolProp GERG-2008 returns physically correct properties
at standard conditions.
"""

import pytest
from kasp.core.properties import ThermodynamicSolver
from kasp.core.mixture import GasMixtureBuilder


@pytest.fixture(scope="module")
def methane_gas():
    from kasp.core.mixture import GasMixtureBuilder
    builder = GasMixtureBuilder()
    normalized = builder.validate_and_normalize({'METHANE': 100.0})
    return builder.build_coolprop_string(normalized)


@pytest.fixture(scope="module")
def methane_gas_data():
    from kasp.core.mixture import GasMixtureBuilder
    builder = GasMixtureBuilder()
    normalized = builder.validate_and_normalize({'METHANE': 100.0})
    return builder.build_thermo_data(normalized)


@pytest.fixture(scope="module")
def solver():
    return ThermodynamicSolver()


class TestMethaneAtStandardConditions:
    """P=1 bar, T=300K — bilinen referans degerler."""

    COOLPROP_TOLERANCE = {
        'Cp_min': 2000,     # J/kg.K (~2225 +- tolerans)
        'Cp_max': 3000,
        'Z_lo': 0.95,       # (~0.998)
        'Z_hi': 1.05,
        'k_gt': 1.0,
    }

    def test_cp_at_1bar_300k(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        assert self.COOLPROP_TOLERANCE['Cp_min'] < state.Cp < self.COOLPROP_TOLERANCE['Cp_max'], \
            f"Cp = {state.Cp} J/kg.K"

    def test_z_at_1bar_300k(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        lo = self.COOLPROP_TOLERANCE['Z_lo']
        hi = self.COOLPROP_TOLERANCE['Z_hi']
        assert lo < state.Z < hi, f"Z = {state.Z}"

    def test_k_greater_than_1(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        assert state.k > self.COOLPROP_TOLERANCE['k_gt'], f"k = {state.k}"

    def test_z_decreases_with_pressure(self, methane_gas, solver):
        state_low = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_high = solver.get_properties(5_000_000, 300.0, methane_gas, 'coolprop')
        assert state_high.Z < state_low.Z, \
            f"Z_low={state_low.Z}, Z_high={state_high.Z}"

    def test_h_increases_with_temperature(self, methane_gas, solver):
        state_300 = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_400 = solver.get_properties(100000, 400.0, methane_gas, 'coolprop')
        assert state_400.H > state_300.H

    def test_phase_is_valid(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        assert state.phase in ('gas', 'supercritical', 'ideal_fallback'), \
            f"phase = {state.phase}"


class TestMultiEOSConsistency:
    """Farkli EOS motorlarinin tutarliligi."""

    @pytest.mark.parametrize("eos", ["coolprop", "pr", "srk"])
    def test_multiple_eos_return_valid_state(self, methane_gas, solver, eos):
        state = solver.get_properties(100000, 300.0, methane_gas, eos)
        assert state is not None
        assert state.Z > 0
        assert state.Cp > 0
        assert state.k > 1.0

    def test_pr_close_to_coolprop(self, methane_gas, solver):
        state_cp = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_pr = solver.get_properties(100000, 300.0, methane_gas, 'pr')
        diff_z = abs(state_cp.Z - state_pr.Z) / state_cp.Z
        assert diff_z < 0.05, f"PR Z sapmasi: {diff_z*100:.1f}%"


class TestFallbackBehavior:
    """Fallback zinciri dogru calismali."""

    def test_fallback_returns_state(self, methane_gas_data, solver):
        state = solver._solve_fallback(100000, 300.0, methane_gas_data, 'coolprop')
        assert state is not None
        assert state.phase == 'ideal_fallback'
        assert state.Z == 1.0
