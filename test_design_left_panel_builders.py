import pytest

from kasp.ui.design_left_panel_builders import (
    get_default_gas_rows,
    get_design_flow_units,
    get_design_method_options,
    get_eos_display_items,
    get_pressure_unit_options,
    get_temperature_unit_options,
)


def test_design_left_panel_option_helpers_preserve_supported_values():
    assert get_pressure_unit_options() == ["bar(a)", "bar(g)", "psia", "psig", "kPa", "MPa", "Pa"]
    assert get_temperature_unit_options() == ["°C", "°F", "K"]
    assert get_design_flow_units() == ["kg/h", "kg/s", "Sm³/h", "Nm³/h", "MMSCFD", "MMSCMD"]
    assert get_design_method_options()[-1] == "Metot 4: Doğrudan H-S"


def test_eos_display_items_follow_library_availability():
    assert get_eos_display_items(True, False) == ["🎯 Yüksek Doğruluk (CoolProp)"]
    assert get_eos_display_items(False, True) == [
        "📊 Peng-Robinson (thermo)",
        "📈 SRK (thermo)",
    ]
    assert get_eos_display_items(False, False) == ["❌ Kütüphane Yok"]


def test_default_gas_rows_match_seed_composition():
    rows = get_default_gas_rows()

    assert rows[0] == ("Methane (CH₄)", 98.00)
    assert rows[-1] == ("Nitrogen (N₂)", 0.50)
    assert sum(percentage for _, percentage in rows) == pytest.approx(100.0)
