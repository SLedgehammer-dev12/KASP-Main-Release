import pytest

from kasp.core.performance_corrections import (
    STANDARD_ASME_PTC10,
    STANDARD_ASME_PTC22,
    STANDARD_ISO_2314,
    ambient_pressure_from_altitude_kpa,
    apply_site_corrections,
    calculate_site_correction_factors,
)
from kasp.ui.performance_workflow import build_performance_report_payload, convert_pressure_delta_to_kpa
from kasp.ui.performance_workflow import PerformanceInputBinder


class _TextWidget:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value


class _ComboWidget:
    def __init__(self, value):
        self._value = value

    def currentText(self):
        return self._value


class _RadioWidget:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


class _PerfWindow:
    def __init__(self):
        self.eos_method_combo = _ComboWidget("Peng-Robinson")
        self.perf_p1_edit = _TextWidget("101.325")
        self.perf_p1_unit_combo = _ComboWidget("kPa")
        self.perf_t1_edit = _TextWidget("298.15")
        self.perf_t1_unit_combo = _ComboWidget("K")
        self.perf_p2_edit = _TextWidget("2.0")
        self.perf_p2_unit_combo = _ComboWidget("bar(a)")
        self.perf_t2_edit = _TextWidget("77.0")
        self.perf_t2_unit_combo = _ComboWidget("°F")
        self.perf_flow_edit = _TextWidget("3600")
        self.perf_flow_unit_combo = _ComboWidget("kg/h")
        self.perf_rpm_edit = _TextWidget("10000")
        self.perf_mech_eff_edit = _TextWidget("98.0")
        self.radio_turb_eff = _RadioWidget(True)
        self.perf_turb_eff_edit = _TextWidget("35.0")
        self.perf_fuel_cons_edit = _TextWidget("")
        self.perf_lhv_source_combo = _ComboWidget("KASP Sabitleri (Hizli/Varsayilan)")
        self.perf_standard_combo = _ComboWidget(STANDARD_ASME_PTC22)
        self.perf_ambient_temp_edit = _TextWidget("59.0")
        self.perf_ambient_temp_unit_combo = _ComboWidget("°F")
        self.perf_ambient_pressure_edit = _TextWidget("1.0")
        self.perf_ambient_pressure_unit_combo = _ComboWidget("bar(a)")
        self.perf_humidity_edit = _TextWidget("60.0")
        self.perf_altitude_edit = _TextWidget("0.0")
        self.perf_inlet_loss_edit = _TextWidget("0.01")
        self.perf_inlet_loss_unit_combo = _ComboWidget("bar(g)")
        self.perf_exhaust_loss_edit = _TextWidget("1000")
        self.perf_exhaust_loss_unit_combo = _ComboWidget("Pa")
        self.perf_manual_power_factor_edit = _TextWidget("1.0")
        self.perf_manual_heat_rate_factor_edit = _TextWidget("1.0")

    def _get_gas_composition(self):
        return {"METHANE": 100.0}


class _PerfEngine:
    def _create_gas_object(self, gas_comp, eos_method):
        return {"gas_comp": gas_comp, "eos_method": eos_method}

    def convert_pressure_to_pa(self, value, unit):
        if unit == "kPa":
            return value * 1000.0
        if unit == "bar(a)":
            return value * 100000.0
        return value

    def convert_temperature_to_k(self, value, unit):
        if unit == "K":
            return value
        if unit == "°F":
            return (value - 32.0) * 5.0 / 9.0 + 273.15
        return value + 273.15

    def convert_flow_to_kgs(self, value, flow_unit, gas_obj, eos_method):
        assert flow_unit == "kg/h"
        return value / 3600.0


def test_altitude_pressure_decreases_with_height():
    assert ambient_pressure_from_altitude_kpa(0) == 101.325
    assert ambient_pressure_from_altitude_kpa(1000) < 101.325


def test_site_correction_factors_include_losses_and_manual_factors():
    factors = calculate_site_correction_factors(
        {
            "standard": STANDARD_ASME_PTC22,
            "ambient_temp_c": 30.0,
            "ambient_pressure_kpa": 95.0,
            "relative_humidity_pct": 70.0,
            "altitude_m": 500.0,
            "inlet_pressure_loss_kpa": 1.0,
            "exhaust_pressure_loss_kpa": 0.5,
            "manual_power_factor": 0.98,
            "manual_heat_rate_factor": 1.02,
        }
    )

    assert factors["temperature_factor"] < 1.0
    assert factors["pressure_factor"] < 1.0
    assert factors["inlet_loss_factor"] < 1.0
    assert factors["exhaust_loss_factor"] < 1.0
    assert factors["power_factor"] < 1.0
    assert factors["heat_rate_factor"] > 1.0


def test_ptc10_keeps_gas_turbine_site_factors_manual_only():
    factors = calculate_site_correction_factors(
        {
            "standard": STANDARD_ASME_PTC10,
            "ambient_temp_c": 40.0,
            "ambient_pressure_kpa": 90.0,
            "inlet_pressure_loss_kpa": 2.0,
            "exhaust_pressure_loss_kpa": 1.0,
            "manual_power_factor": 0.95,
            "manual_heat_rate_factor": 1.03,
        }
    )

    assert factors["standard"] == STANDARD_ASME_PTC10
    assert factors["applied_temperature_factor"] == 1.0
    assert factors["applied_pressure_factor"] == 1.0
    assert factors["applied_inlet_loss_factor"] == 1.0
    assert factors["applied_exhaust_loss_factor"] == 1.0
    assert factors["power_factor"] == pytest.approx(0.95)
    assert factors["heat_rate_factor"] == pytest.approx((1.0 / 0.95) * 1.03)


def test_iso2314_applies_reference_style_site_factors():
    factors = calculate_site_correction_factors(
        {
            "standard": STANDARD_ISO_2314,
            "ambient_temp_c": 35.0,
            "ambient_pressure_kpa": 93.0,
            "inlet_pressure_loss_kpa": 1.5,
        }
    )

    assert factors["standard"] == STANDARD_ISO_2314
    assert factors["applied_temperature_factor"] < 1.0
    assert factors["applied_pressure_factor"] < 1.0
    assert factors["applied_inlet_loss_factor"] < 1.0


def test_pressure_delta_units_are_converted_to_kpa():
    assert convert_pressure_delta_to_kpa(1000.0, "Pa") == 1.0
    assert convert_pressure_delta_to_kpa(0.01, "bar(g)") == 1.0
    assert round(convert_pressure_delta_to_kpa(1.0, "psig"), 5) == 6.89476


def test_performance_binder_uses_selected_units_and_standard():
    inputs, flow_unit = PerformanceInputBinder(_PerfWindow(), engine=_PerfEngine()).collect()

    assert flow_unit == "kg/h"
    assert inputs["p1_pa"] == pytest.approx(101325.0)
    assert inputs["t1_k"] == pytest.approx(298.15)
    assert inputs["p2_pa"] == pytest.approx(200000.0)
    assert inputs["t2_k"] == pytest.approx(298.15)
    assert inputs["flow_kgs"] == pytest.approx(1.0)
    assert inputs["site_correction_inputs"]["standard"] == STANDARD_ASME_PTC22
    assert inputs["site_correction_inputs"]["ambient_temp_c"] == pytest.approx(15.0)
    assert inputs["site_correction_inputs"]["ambient_pressure_kpa"] == pytest.approx(100.0)
    assert inputs["site_correction_inputs"]["inlet_pressure_loss_kpa"] == pytest.approx(1.0)
    assert inputs["site_correction_inputs"]["exhaust_pressure_loss_kpa"] == pytest.approx(1.0)


def test_apply_site_corrections_corrects_power_and_heat_rate_to_reference():
    corrected = apply_site_corrections(
        1000.0,
        10000.0,
        {"ambient_temp_c": 30.0, "ambient_pressure_kpa": 95.0, "inlet_pressure_loss_kpa": 1.0},
    )

    assert corrected["corrected_power_kw"] > 1000.0
    assert corrected["corrected_heat_rate_kj_kwh"] < 10000.0


def test_performance_payload_exposes_corrected_values():
    report_inputs, payload = build_performance_report_payload(
        {
            "flow_kgs": 10.0,
            "fuel_flow": 100.0,
            "p1_pa": 100.0,
            "p2_pa": 200.0,
            "site_correction_inputs": {"ambient_temp_c": 30.0, "ambient_pressure_kpa": 95.0},
        },
        {
            "poly_eff": 80.0,
            "turb_eff": 35.0,
            "actual_heat_rate": 10000.0,
            "shaft_power_kw": 1000.0,
            "corrected_power_kw": 1100.0,
            "corrected_heat_rate": 9500.0,
        },
        design_inputs={"therm_eff": 35.0},
        design_results={"power_shaft_per_unit_kw": 1000.0, "heat_rate": 10000.0},
    )

    assert report_inputs["site_correction_inputs"]["ambient_temp_c"] == 30.0
    assert payload["corrected_power"] == 1100.0
    assert payload["corrected_heat_rate"] == 9500.0
    assert payload["corrected_values"]["correction_factors"]["inputs"]["ambient_pressure_kpa"] == 95.0
