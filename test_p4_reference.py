"""P4 reference tests: engine results checked against independent physical references.

These are assertion-based (not print-only), so they fail the build if the engine
diverges from an independent CoolProp calculation or from basic thermodynamic
invariants.
"""

import pytest

CP = pytest.importorskip("CoolProp.CoolProp", reason="CoolProp required for reference checks")

from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver


def _mixture():
    comp = GasMixtureBuilder.validate_and_normalize(
        {"METHANE": 90.0, "ETHANE": 7.0, "PROPANE": 3.0}
    )
    return GasMixtureBuilder.build_coolprop_string(comp)


def test_engine_coolprop_matches_direct_reference():
    gas = _mixture()
    P, T = 30e5, 320.0

    solver = ThermodynamicSolver()
    state = solver.get_properties(P, T, gas, "coolprop")

    h_ref = CP.PropsSI("Hmass", "P", P, "T", T, gas)
    s_ref = CP.PropsSI("Smass", "P", P, "T", T, gas)
    z_ref = CP.PropsSI("Z", "P", P, "T", T, gas)

    assert state.H == pytest.approx(h_ref, rel=1e-3)
    assert state.S == pytest.approx(s_ref, rel=1e-3)
    assert state.Z == pytest.approx(z_ref, rel=1e-4)


def test_isentropic_outlet_conserves_entropy():
    from kasp.core.fallback import FallbackTracker, SolverChain

    gas = _mixture()
    solver = ThermodynamicSolver()
    state_in = solver.get_properties(20e5, 300.0, gas, "coolprop")
    p_out = 60e5

    chain = SolverChain(FallbackTracker())
    t_out = chain.find_isentropic_temp(
        state_in, p_out, solver, gas, "coolprop", solver_method="auto"
    )
    state_out = solver.get_properties(p_out, t_out, gas, "coolprop")

    # Thermodynamic invariant: isentropic compression keeps entropy constant
    assert abs(state_out.S - state_in.S) < 5.0  # J/kg/K
    assert state_out.T > state_in.T


def test_textbook_and_independent_reference_scripts():
    from verify_textbook import calculate_textbook_compressor_power
    from verify_independent import independent_verification
    from verify_stability import run_test as run_stability_test

    tb = calculate_textbook_compressor_power()
    ind = independent_verification()
    stab = run_stability_test()

    # Textbook and independent PTC-10 polytropic head for the same 20->60 bar methane-rich gas
    # must agree within ~10%
    assert abs(tb["head_kj_kg"] - ind["head_poly_kj_kg"]) / ind["head_poly_kj_kg"] < 0.10
    assert stab["power_unit_kw"] > stab["power_shaft_per_unit_kw"] > stab["power_gas_per_unit_kw"] > 0

