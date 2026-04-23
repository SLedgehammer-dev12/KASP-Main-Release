from kasp.ui.gas_composition_workflow import (
    build_total_label_state,
    extract_gas_composition,
    normalize_percentage_values,
    standard_composition_for_gas,
)


def test_standard_composition_for_gas_maps_known_and_fallback_cases():
    assert standard_composition_for_gas("Methane (CH4)") == {"METHANE": 100.0}
    assert standard_composition_for_gas("Air") == {"NITROGEN": 78.0, "OXYGEN": 21.0, "ARGON": 1.0}
    assert standard_composition_for_gas("Unknown Gas")["METHANE"] == 85.0


def test_normalize_percentage_values_scales_positive_values_to_100():
    normalized, total = normalize_percentage_values([50.0, 30.0, 20.0])

    assert total == 100.0
    assert normalized == [50.0, 30.0, 20.0]

    normalized, total = normalize_percentage_values([5.0, 0.0, 5.0])
    assert total == 10.0
    assert normalized == [50.0, 0.0, 50.0]


def test_build_total_label_state_covers_exact_near_and_invalid_totals():
    success_text, success_style = build_total_label_state(100.0)
    warning_text, warning_style = build_total_label_state(99.5)
    error_text, error_style = build_total_label_state(87.0)

    assert "✔" in success_text
    assert "#27ae60" in success_style
    assert "yakın" in warning_text
    assert "#e67e22" in warning_style
    assert "olmalı" in error_text
    assert "#c0392b" in error_style


def test_extract_gas_composition_skips_invalid_rows_and_maps_display_names():
    composition = extract_gas_composition(
        [
            ("Methane (CH4)", "98.5"),
            ("Ethane (C2H6)", "1,5"),
            ("Nitrogen (N2)", "0"),
            ("", "12"),
            ("Bad", "abc"),
        ],
        {"Methane (CH4)": "METHANE", "Ethane (C2H6)": "ETHANE", "Nitrogen (N2)": "NITROGEN"},
    )

    assert composition == {"METHANE": 98.5, "ETHANE": 1.5}
