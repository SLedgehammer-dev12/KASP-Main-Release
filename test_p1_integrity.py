"""P1 regression tests: input & selection integrity fixes."""

import pytest

from kasp.core.exceptions import UnitConversionError
from kasp.core.selection import TurbineSelector
from kasp.core.units import UnitSystem


# ── P1-9: gas composition mapping / duplicates / rejection ───────────────────

def test_hydrogen_sulfide_maps_correctly():
    from kasp.ui.gas_composition_workflow import standard_composition_for_gas

    assert standard_composition_for_gas("Hydrogen Sulfide") == {"HYDROGENSULFIDE": 100.0}
    assert standard_composition_for_gas("H2S") == {"HYDROGENSULFIDE": 100.0}
    assert standard_composition_for_gas("Hydrogen") == {"HYDROGEN": 100.0}


def test_duplicate_components_sum_and_invalid_rejected():
    from kasp.ui.gas_composition_workflow import extract_gas_composition

    entries = [("Methane (CH₄)", "40"), ("Methane (CH₄)", "10")]
    assert extract_gas_composition(entries, {"Methane (CH₄)": "METHANE"}) == {"METHANE": 50.0}

    with pytest.raises(ValueError):
        extract_gas_composition([("Methane (CH₄)", "abc")], {}, strict=True)


# ── P1-11: finite numeric validation ─────────────────────────────────────────

def test_nan_and_inf_rejected():
    with pytest.raises(UnitConversionError):
        UnitSystem.convert_temperature(float("nan"), "°C", "K")
    with pytest.raises(UnitConversionError):
        UnitSystem.convert_temperature(float("inf"), "°C", "K")


# ── P1-7: surge/stonewall margins not silently zeroed ────────────────────────

def test_aero_margins_none_without_flow():
    turbine = {"surge_flow": 2.5, "stonewall_flow": 12.0}
    margins = TurbineSelector._calculate_aero_margins(turbine, 0)
    assert margins["surge_margin_pct"] is None
    assert margins["stonewall_margin_pct"] is None
    assert margins["available"] is False


def test_aero_margins_computed_with_flow():
    turbine = {"surge_flow": 2.5, "stonewall_flow": 12.0}
    margins = TurbineSelector._calculate_aero_margins(turbine, 6.0)
    assert margins["surge_margin_pct"] == pytest.approx((6.0 - 2.5) / 2.5 * 100.0)
    assert margins["stonewall_margin_pct"] == pytest.approx((12.0 - 6.0) / 6.0 * 100.0)


# ── P1-8: OEM curves + score clamp ───────────────────────────────────────────

def test_correction_uses_oem_curve_when_present():
    turbine = {
        "performance_correction_data": {
            "temperature_correction": {
                "points": [0, 15, 30],
                "power_factor": [1.08, 1.0, 0.91],
                "hr_factor": [0.985, 1.0, 1.02],
            },
            "altitude_correction": {"points": [0, 1000], "power_factor": [1.0, 0.9]},
        }
    }
    power, hr, source = TurbineSelector._correct_performance(1000.0, 10000.0, 15.0, 101.325, 0, turbine)
    assert source == "oem_curve"
    assert power == pytest.approx(1000.0 * 1.0)
    assert hr == pytest.approx(10000.0 * 1.0)


def test_correction_avoids_double_counting_pressure_and_altitude():
    power, hr, source = TurbineSelector._correct_performance(1000.0, 10000.0, 15.0, 90.0, 1000, {})
    assert source == "generic_formula"
    # explicit pressure wins; altitude must not be applied a second time
    assert power == pytest.approx(1000.0 * (90.0 / 101.325))


def test_turbine_score_is_clamped_to_100():
    score = TurbineSelector._calculate_turbine_score(
        turbine_type="Industrial",
        corrected_heat_rate=7000.0,  # better than HR_REF_BEST -> would exceed 100 unclamped
        power_margin_pct=10.0,
        surge_margin_pct=25.0,
        stonewall_margin_pct=25.0,
    )
    assert 0.0 <= score <= 100.0


# ── P1-10: compressor dialog unit conversion ─────────────────────────────────

def test_compressor_dialog_converts_kg_h_to_kg_s():
    pytest.importorskip("PyQt5", reason="PyQt5 required")
    from PyQt5.QtWidgets import QApplication

    from kasp.ui.dialogs import CompressorEditDialog

    app = QApplication.instance() or QApplication([])
    dialog = CompressorEditDialog()
    dialog.manufacturer_edit.setText("Acme")
    dialog.model_edit.setText("T1")
    dialog.min_flow_spin.setValue(3600.0)
    dialog.max_flow_spin.setValue(7200.0)

    data = dialog.get_compressor_data()
    assert data["min_flow_kgs"] == pytest.approx(1.0)
    assert data["max_flow_kgs"] == pytest.approx(2.0)
