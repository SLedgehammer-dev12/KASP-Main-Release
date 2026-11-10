import pytest
from kasp.services.gas_service import (
    get_smart_eos_recommendation,
    get_smart_method_recommendation,
    get_kij_matrix_for_composition,
    normalize_composition_dict,
)


def test_smart_recommendations_string_values_and_none():
    """Verify smart recommendations handle string percentages and None without crashing."""
    # Dict with string values (common from HTML form / JSON)
    str_comp = {"METHANE": "90.0", "ETHANE": "10.0"}
    eos_rec = get_smart_eos_recommendation(str_comp)
    assert eos_rec["recommended_eos"] in ("coolprop", "pr")

    # String pressures
    method_rec = get_smart_method_recommendation(str_comp, p_in="25.0", p_out="75.0")
    assert "recommended_method" in method_rec

    # None input
    assert get_smart_eos_recommendation(None)["category"] == "default"
    assert "recommended_method" in get_smart_method_recommendation(None)


def test_kij_matrix_none_and_bad_overrides():
    """Verify get_kij_matrix_for_composition survives None and bad float overrides."""
    res_none = get_kij_matrix_for_composition(None)
    assert res_none["size"] == 0
    assert len(res_none["matrix"]) == 0

    # Bad override string
    res_bad = get_kij_matrix_for_composition(
        {"METHANE": 90.0, "CARBONDIOXIDE": 10.0},
        custom_overrides={"METHANE:CARBONDIOXIDE": "not_a_number"},
    )
    assert res_bad["size"] == 2
    # Should safely fallback to literature value or 0.0 without crashing
    assert isinstance(res_bad["matrix"][0][1], float)


def test_normalize_composition_dict_non_numeric():
    """Verify normalize_composition_dict filters out non-numeric or invalid entries."""
    mixed = {"METHANE": 80.0, "ETHANE": "20.0", "BAD": "invalid", "ZERO": 0.0}
    norm = normalize_composition_dict(mixed)
    assert "METHANE" in norm
    assert "ETHANE" in norm
    assert "BAD" not in norm
    assert sum(norm.values()) == pytest.approx(100.0, rel=1e-3)
