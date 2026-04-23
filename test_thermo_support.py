from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from kasp.core.thermo_support import (
    build_summary_report,
    convert_flow_to_kgs,
    convert_pressure_to_pa,
    convert_result_value,
    convert_temperature_to_k,
    evaluate_performance_status,
    normalize_efficiency_reference,
    percent_deviation,
    safe_float,
)


class DummyLogger:
    def __init__(self):
        self.messages = []

    def warning(self, message):
        self.messages.append(("warning", message))

    def error(self, message):
        self.messages.append(("error", message))


class DummyThermoSolver:
    def infer_mw_g_mol(self, gas_obj):
        return 20.0

    def get_properties(self, pressure, temperature, gas_obj, eos_method):
        if pressure == 101325 and temperature == 288.15:
            return SimpleNamespace(density=0.9, MW=20.0)
        if pressure == 101325 and temperature == 273.15:
            return SimpleNamespace(density=1.1, MW=20.0)
        return SimpleNamespace(density=0.75, MW=20.0)


@dataclass
class DummyUnit:
    turbine_name: str
    available_power_kw: float
    efficiency_rating: str
    selection_score: float


def test_numeric_helpers_preserve_existing_engine_behavior():
    assert safe_float("12.5") == 12.5
    assert safe_float("bad", 3.0) == 3.0
    assert normalize_efficiency_reference(82.0) == 0.82
    assert normalize_efficiency_reference(0.82) == 0.82
    assert percent_deviation(105.0, 100.0) == 5.0
    assert percent_deviation(10.0, 0) == 0.0


def test_unit_conversion_helpers_cover_pressure_temperature_and_result_units():
    assert convert_pressure_to_pa(1.0, "bar(a)") == pytest.approx(100000.0)
    assert convert_temperature_to_k(25.0, "°C") == pytest.approx(298.15)
    assert convert_result_value(1.0, "MW", "kW", "power") == pytest.approx(1000.0)
    assert convert_result_value(334.55256555, "ft-lbf/lbm", "kJ/kg", "head") == pytest.approx(1.0)
    assert convert_result_value(1000.0, "kJ/kWh", "Btu/kWh", "heat_rate") == pytest.approx(947.817)


def test_flow_conversion_helper_supports_mass_standard_volume_and_molar_units():
    logger = DummyLogger()
    solver = DummyThermoSolver()

    assert convert_flow_to_kgs(
        3600.0,
        "kg/h",
        {"gas": "x"},
        "coolprop",
        thermo_solver=solver,
        logger=logger,
        std_press_pa=101325,
        standard_temp_k=288.15,
        normal_temp_k=273.15,
    ) == pytest.approx(1.0)
    assert convert_flow_to_kgs(
        3600.0,
        "Sm³/h",
        {"gas": "x"},
        "coolprop",
        thermo_solver=solver,
        logger=logger,
        std_press_pa=101325,
        standard_temp_k=288.15,
        normal_temp_k=273.15,
    ) == pytest.approx(0.9)
    assert convert_flow_to_kgs(
        3600.0,
        "kgmol/h",
        {"gas": "x"},
        "coolprop",
        thermo_solver=solver,
        logger=logger,
        std_press_pa=101325,
        standard_temp_k=288.15,
        normal_temp_k=273.15,
    ) == pytest.approx(20.0)


def test_summary_report_and_performance_status_helpers_remain_stable():
    report = build_summary_report(
        {"project_name": "Demo", "num_units": 2, "poly_eff": 81.0, "therm_eff": 34.0},
        {"compression_ratio": 3.2, "power_unit_kw": 1200.0, "power_unit_total_kw": 2400.0, "t_out": 88.0},
        [DummyUnit("GT-35", 4200.0, "A", 92.0), {"turbine": "GT-40", "available_power_kw": 5000.0, "efficiency_rating": "B", "selection_score": 88.0}],
        {"calls": 7},
        calculation_date="2026-04-21T12:00:00",
    )

    assert report["project_name"] == "Demo"
    assert report["calculation_date"] == "2026-04-21T12:00:00"
    assert report["recommended_turbines"][0]["turbine"] == "GT-35"
    assert report["recommended_turbines"][1]["turbine"] == "GT-40"
    assert report["system_performance"] == {"calls": 7}

    assert evaluate_performance_status(
        {"deviation_poly_eff": 1.0, "deviation_therm_eff": 0.5, "deviation_heat_rate": 0.4, "deviation_power": 0.9}
    )["status"] == "EXCELLENT"
    assert evaluate_performance_status(
        {"deviation_poly_eff": 7.0, "deviation_therm_eff": 1.0, "deviation_heat_rate": 0.4, "deviation_power": 0.9}
    )["status"] == "ACCEPTABLE"
