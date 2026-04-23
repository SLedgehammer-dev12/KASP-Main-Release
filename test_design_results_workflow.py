from dataclasses import dataclass

from kasp.ui.design_results_workflow import (
    build_consistency_info_html,
    build_design_summary_text,
    build_selected_turbine_labels,
    describe_selected_turbine,
    serialize_selected_units,
)


@dataclass
class DummyUnit:
    turbine_name: str
    available_power_kw: float
    site_heat_rate: float
    efficiency_rating: str
    surge_margin_percent: float
    selection_score: float
    recommendation_level: str
    iso_power_kw: float = 0.0
    power_margin_percent: float = 0.0


def test_build_consistency_info_html_returns_none_when_mode_disabled():
    assert build_consistency_info_html({"consistency_mode": False}) is None


def test_build_consistency_info_html_contains_warning_for_nonconverged_case():
    html = build_consistency_info_html(
        {
            "consistency_mode": True,
            "consistency_converged": False,
            "poly_eff_target": 78.0,
            "poly_eff_converged": 76.5,
            "actual_poly_efficiency": 0.761,
            "consistency_iterations": 12,
            "final_residual": 0.1432,
        }
    )

    assert "Self-Consistent" in html
    assert "76.10%" in html
    assert "Maksimum iter" in html


def test_build_design_summary_text_supports_fast_mode_summary():
    text = build_design_summary_text(
        {
            "project_name": "Demo",
            "basic_parameters": {"compression_ratio": 3.5, "total_power": 4200.0, "num_units": 2},
            "efficiency_metrics": {"poly_efficiency": 0.79},
            "recommended_turbines": [{"turbine": "GT-35"}],
        },
        {"consistency_mode": False},
    )

    assert "Mod: Hızlı" in text
    assert "Demo" in text
    assert "79.0%" in text
    assert "GT-35" in text


def test_describe_and_serialize_selected_units_support_objects_and_dicts():
    described = describe_selected_turbine(
        {
            "turbine": "GT-40",
            "available_power_kw": 5500.0,
            "iso_power": 6000.0,
            "site_heat_rate": 10450.0,
            "efficiency_rating": "A",
            "power_margin_percent": 8.2,
            "surge_margin": 15.1,
            "recommendation_level": "Önerilir",
        }
    )
    serialized = serialize_selected_units(
        [
            DummyUnit("GT-35", 4200.0, 10200.0, "A", 14.0, 91.0, "Önerilir"),
            {"turbine": "GT-40"},
            object(),
        ]
    )

    assert described["turbine_name"] == "GT-40"
    assert described["iso_power"] == 6000.0
    assert described["surge_margin"] == 15.1
    assert serialized[0]["turbine_name"] == "GT-35"
    assert serialized[1] == {"turbine": "GT-40"}
    assert serialized[2]["repr"].startswith("<object object")


def test_build_selected_turbine_labels_formats_detail_panel_values():
    labels = build_selected_turbine_labels(
        {
            "turbine_name": "GT-40",
            "available_power": 5500.0,
            "iso_power": 6000.0,
            "site_heat_rate": 10450.0,
            "efficiency_rating": "A",
            "power_margin": 8.2,
            "surge_margin": 15.1,
            "recommendation": "Önerilir",
        }
    )

    assert labels["turbine_name"] == "GT-40"
    assert labels["power"] == "5500 kW (ISO: 6000 kW)"
    assert labels["efficiency"] == "Isi Orani: 10450 kJ/kWh (A)"
    assert labels["margin"] == "Guc: 8.2%, Surge: 15.1%"
