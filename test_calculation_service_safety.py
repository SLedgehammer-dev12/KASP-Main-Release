import pytest
from kasp.services.calculation_service import serialize_turbine_recommendation


def test_serialize_turbine_recommendation_none():
    """Verify serialize_turbine_recommendation returns empty dict on None input."""
    assert serialize_turbine_recommendation(None) == {}


def test_serialize_turbine_recommendation_preserves_none_surge():
    """Verify serialize_turbine_recommendation does not invent fake 15.0% surge when surge is None."""
    # Recommendation dict with surge_margin_percent = None
    rec_dict = {
        "name": "Titan 130",
        "available_power_kw": 15000.0,
        "power_margin_pct": 12.5,
        "surge_margin_percent": None,
        "surge_margin_pct": None,
    }
    serialized = serialize_turbine_recommendation(rec_dict)
    assert serialized["surge_margin_pct"] is None

    # Recommendation object with surge_margin_percent = None
    class MockRec:
        turbine_name = "Centaur 50"
        available_power_kw = 4500.0
        power_margin_percent = 8.0
        surge_margin_percent = None
        surge_margin_pct = None

    serialized_obj = serialize_turbine_recommendation(MockRec())
    assert serialized_obj["surge_margin_pct"] is None


def test_serialize_turbine_recommendation_bad_strings():
    """Verify serialize_turbine_recommendation handles non-numeric strings safely."""
    rec_bad = {
        "name": "Mars 100",
        "power_margin_pct": "invalid_num",
        "available_power_kw": "invalid_pwr",
        "surge_margin_pct": "not_a_float",
    }
    serialized = serialize_turbine_recommendation(rec_bad)
    assert serialized["power_margin_pct"] == 0.0
    assert serialized["surge_margin_pct"] is None
