import os
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


def test_placeholder_turbine_aero_margins_none():
    turbec = {
        "manufacturer": "Turbec (Ansaldo)",
        "model": "T100-PH",
        "min_flow_kgs": 0,
        "max_flow_kgs": 1000,
        "surge_flow": 0.03,
        "stonewall_flow": 0.3,
    }
    margins = TurbineSelector._calculate_aero_margins(turbec, 1.09716)
    assert margins["surge_margin_pct"] is None
    assert margins["stonewall_margin_pct"] is None
    assert margins["available"] is False


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


def test_turbine_selection_zero_and_negative_power_safety():
    """Verify that select_units handles zero, negative, or non-finite power safely without ZeroDivisionError."""
    turbines = [{"iso_power_kw": 1000.0, "iso_heat_rate_kj_kwh": 9000.0, "type": "Industrial"}]
    
    # 0.0 power must not crash
    recs_zero = TurbineSelector.select_units(0.0, {}, turbines)
    assert recs_zero == []

    # Negative power must not crash
    recs_neg = TurbineSelector.select_units(-500.0, {}, turbines)
    assert recs_neg == []

    # NaN / Inf power must not crash
    recs_nan = TurbineSelector.select_units(float("nan"), {}, turbines)
    assert recs_nan == []


def test_turbine_correction_extreme_temperature_and_pressure_safety():
    """Verify that _correct_performance never divides by zero at absolute zero or zero ambient pressure."""
    # Absolute zero temperature (-273.15 °C)
    power, hr, source = TurbineSelector._correct_performance(1000.0, 9000.0, -273.15, 101.325, 0, {})
    assert power >= 0.0
    assert hr >= 0.0

    # Zero ambient pressure
    power_p0, hr_p0, _ = TurbineSelector._correct_performance(1000.0, 9000.0, 15.0, 0.0, 0, {})
    assert power_p0 >= 0.0
    assert hr_p0 >= 0.0


def test_calculation_worker_unit_selection_resilience():
    """Verify that CalculationWorker._run_body unit selection step does not crash with KeyError or TypeError
    when results_raw or inputs lack power_motor_per_unit_kw, power_unit_kw, ambient_temp, or altitude."""
    from unittest.mock import MagicMock
    from kasp.utils.workers import CalculationWorker

    engine_mock = MagicMock()
    # Case 1: results_raw without power_motor_per_unit_kw and without power_unit_kw
    engine_mock.calculate_design_performance_with_mode.return_value = {
        "mass_flow_per_unit_kgs": 1.5,
    }
    engine_mock.select_units.return_value = []

    worker = CalculationWorker(engine_mock, {}, [])
    # _run_body should complete without raising KeyError or TypeError
    worker._run_body()
    assert engine_mock.select_units.called
    args, kwargs = engine_mock.select_units.call_args
    assert args[0] == 0.0  # fallback required_power_per_unit_kw
    assert args[1]["ambient_temp"] == 15.0
    assert args[1]["altitude"] == 0.0
    assert args[1]["ambient_pressure"] == 101.325

    # Case 2: results_raw with power_motor_per_unit_kw = None
    engine_mock.reset_mock()
    engine_mock.calculate_design_performance_with_mode.return_value = {
        "power_motor_per_unit_kw": None,
        "power_unit_kw": 520.0,
        "mass_flow_per_unit_kgs": 1.5,
    }
    engine_mock.select_units.return_value = []

    worker2 = CalculationWorker(engine_mock, {"ambient_temp": 20.0}, [])
    worker2._run_body()
    args2, _ = engine_mock.select_units.call_args
    assert args2[0] == pytest.approx(500.0)  # 520 / 1.04
    assert args2[1]["ambient_temp"] == 20.0


def test_report_generator_minimal_inputs_resilience(tmp_path):
    """Verify that ReportGenerator.generate_design_report does not crash with KeyError
    when inputs dict lacks optional metadata fields like ambient_temp, project_name, etc."""
    from unittest.mock import MagicMock
    from kasp.utils.reporting import ReportGenerator

    engine_mock = MagicMock()
    engine_mock._create_gas_object.return_value = None
    engine_mock.convert_result_value.side_effect = lambda val, *args, **kwargs: float(val) if val is not None else 0.0
    out_pdf = str(tmp_path / "minimal_report.pdf")
    rg = ReportGenerator(out_pdf, engine_mock)
    
    minimal_inputs = {
        "p_in": 10.0,
        "p_out": 20.0,
        "t_in": 25.0,
        "p_in_unit": "bar",
        "t_in_unit": "°C",
        "flow": 5000.0,
        "flow_unit": "kg/h",
    }
    minimal_results = {
        "t_out": 85.0,
        "compression_ratio": 2.0,
        "head_kj_kg": 150.0,
        "power_unit_kw": 300.0,
        "power_unit_total_kw": 300.0,
        "power_shaft_total_kw": 300.0,
        "power_motor_total_kw": 312.0,
        "power_gas_total_kw": 280.0,
        "actual_poly_efficiency": 0.82,
        "fuel_total_kgh": 50.0,
        "heat_rate": 9500.0,
        "inlet_properties": {},
        "outlet_properties": {},
        "stages": [],
    }
    
    rg.generate_design_report(minimal_inputs, minimal_results)
    assert os.path.exists(out_pdf)
    assert os.path.getsize(out_pdf) > 0


