import pytest

from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver


def test_cache_key_distinguishes_dict_gas_objects_with_ids_format():
    solver = ThermodynamicSolver()
    methane = GasMixtureBuilder.build_thermo_data({"METHANE": 1.0})
    nitrogen = GasMixtureBuilder.build_thermo_data({"NITROGEN": 1.0})

    methane_key = solver._build_cache_key(1.0e5, 300.0, methane, "pr")
    nitrogen_key = solver._build_cache_key(1.0e5, 300.0, nitrogen, "pr")

    assert methane_key != nitrogen_key


def test_fallback_uses_inferred_mixture_mw_when_explicit_mw_missing():
    solver = ThermodynamicSolver()
    gas_obj = {"ids": ["methane"], "mol_fractions": [1.0]}

    state = solver._solve_fallback(1.0e5, 300.0, gas_obj, "pr")

    assert state.raw_props["fallback"] is True
    assert state.MW == pytest.approx(16.04, rel=1e-3)
    assert state.MW != pytest.approx(28.96, rel=1e-3)


def test_cache_size_is_never_zero():
    solver = ThermodynamicSolver(max_cache_size=0)

    assert solver.get_cache_stats()["max_size"] == 1


def test_cache_size_uses_default_for_invalid_values():
    solver = ThermodynamicSolver(max_cache_size=None)

    assert solver.get_cache_stats()["max_size"] == 2000


def test_cache_miss_recording_updates_stats():
    solver = ThermodynamicSolver()

    solver._record_cache_miss()

    assert solver.get_cache_stats()["misses"] == 1


def test_build_state_populates_standard_raw_props():
    state = ThermodynamicSolver._build_state(
        P_pa=1.0e5,
        T_k=300.0,
        H=1.0,
        S=2.0,
        Z=1.0,
        k=1.3,
        MW=18.0,
        Cp=2200.0,
        Cv=1700.0,
        density=1.2,
        phase="gas",
    )

    assert state.raw_props["fallback"] is False
    assert state.raw_props["mu"] > 0.0
    assert state.raw_props["speed_of_sound"] > 0.0


def test_extract_thermo_components_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="ids"):
        ThermodynamicSolver._extract_thermo_components(
            {"ids": ["methane", "nitrogen"], "mol_fractions": [1.0]}
        )


def test_extract_thermo_components_accepts_legacy_uppercase_keys():
    ids, zs = ThermodynamicSolver._extract_thermo_components(
        {"IDs": ["methane"], "zs": [1.0]}
    )

    assert ids == ["methane"]
    assert zs == [1.0]
