import pytest
from kasp.core.settings import EngineSettings
from kasp.core.selection import TurbineSelector


def test_get_turbine_type_score_case_and_separator_variants():
    """get_turbine_type_score must match variants with spaces, hyphens, and mixed cases."""
    # Aero variants (100)
    assert EngineSettings.get_turbine_type_score("Aero-Derivative") == 100
    assert EngineSettings.get_turbine_type_score("Aero Derivative") == 100
    assert EngineSettings.get_turbine_type_score("aero-derivative") == 100
    assert EngineSettings.get_turbine_type_score("aero") == 100

    # Heavy-Duty variants (70)
    assert EngineSettings.get_turbine_type_score("Heavy-Duty") == 70
    assert EngineSettings.get_turbine_type_score("Heavy Duty") == 70
    assert EngineSettings.get_turbine_type_score("heavy-duty") == 70
    assert EngineSettings.get_turbine_type_score("heavy duty") == 70

    # Industrial/Aero (90)
    assert EngineSettings.get_turbine_type_score("Industrial/Aero") == 90
    assert EngineSettings.get_turbine_type_score("industrial-aero") == 90

    # Industrial (80)
    assert EngineSettings.get_turbine_type_score("Industrial") == 80
    assert EngineSettings.get_turbine_type_score("industrial") == 80

    # Centrifugal (60)
    assert EngineSettings.get_turbine_type_score("Centrifugal") == 60
    assert EngineSettings.get_turbine_type_score("centrifugal") == 60


def test_get_turbine_type_score_none_or_unknown():
    """None, empty, or unknown turbine types must return 65."""
    assert EngineSettings.get_turbine_type_score(None) == 65
    assert EngineSettings.get_turbine_type_score("") == 65
    assert EngineSettings.get_turbine_type_score("Unknown Experimental") == 65


def test_turbine_selector_uses_normalized_score():
    """TurbineSelector._calculate_turbine_score must score variants without falling back to 65."""
    score_standard = TurbineSelector._calculate_turbine_score(
        turbine_type="Aero-Derivative",
        corrected_heat_rate=9000.0,
        power_margin_pct=10.0,
        surge_margin_pct=15.0,
        stonewall_margin_pct=10.0,
    )
    score_spaced = TurbineSelector._calculate_turbine_score(
        turbine_type="Aero Derivative",
        corrected_heat_rate=9000.0,
        power_margin_pct=10.0,
        surge_margin_pct=15.0,
        stonewall_margin_pct=10.0,
    )
    assert score_standard == score_spaced
    assert score_standard > 85.0
