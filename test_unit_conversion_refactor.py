import logging

import pytest

from kasp.core.exceptions import UnitConversionError
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver
from kasp.core.thermo_support import convert_flow_to_kgs, convert_result_value
from kasp.core.units import UnitSystem


class _DensityState:
    def __init__(self, density):
        self.density = density


class _FailingSolver:
    def infer_mw_g_mol(self, gas_obj):
        return None

    def get_properties(self, *args, **kwargs):
        raise RuntimeError("no properties")


class _DensitySolver:
    def __init__(self, density):
        self.density = density

    def get_properties(self, *args, **kwargs):
        return _DensityState(self.density)


class _MWSolver:
    def infer_mw_g_mol(self, gas_obj):
        return gas_obj.get("MW")

    def get_properties(self, *args, **kwargs):
        raise AssertionError("Standard volumetric flow should use inferred MW without property lookup")


def test_molar_flow_conversion_uses_mixture_mw():
    gas_obj = GasMixtureBuilder.build_thermo_data({"METHANE": 0.5, "NITROGEN": 0.5})
    solver = ThermodynamicSolver()

    converted = convert_flow_to_kgs(
        10,
        "kmol/h",
        gas_obj,
        "pr",
        thermo_solver=solver,
        logger=logging.getLogger("test"),
        std_press_pa=101325.0,
        standard_temp_k=288.15,
        normal_temp_k=273.15,
    )

    expected = (10 * gas_obj["MW"]) / 3600.0
    assert converted == pytest.approx(expected)


def test_molar_flow_conversion_raises_when_mw_is_unknown():
    with pytest.raises(UnitConversionError):
        convert_flow_to_kgs(
            1,
            "kmol/h",
            {"ids": ["unknown"], "mol_fractions": [1.0]},
            "pr",
            thermo_solver=_FailingSolver(),
            logger=logging.getLogger("test"),
            std_press_pa=101325.0,
            standard_temp_k=288.15,
            normal_temp_k=273.15,
        )


def test_mass_flow_conversion_wraps_invalid_numeric_values():
    with pytest.raises(UnitConversionError):
        convert_flow_to_kgs(
            "not-a-number",
            "kg/s",
            {},
            "pr",
            thermo_solver=_DensitySolver(1.0),
            logger=logging.getLogger("test"),
            std_press_pa=101325.0,
            standard_temp_k=288.15,
            normal_temp_k=273.15,
        )


def test_volumetric_flow_conversion_rejects_nonpositive_density():
    with pytest.raises(UnitConversionError, match="[yo]?[oö]?[ğg]unluk|yogunluk|yoğunluk"):
        convert_flow_to_kgs(
            100,
            "Sm3/h",
            {},
            "pr",
            thermo_solver=_DensitySolver(0.0),
            logger=logging.getLogger("test"),
            std_press_pa=101325.0,
            standard_temp_k=288.15,
            normal_temp_k=273.15,
        )


def test_standard_volumetric_flow_uses_inferred_mw_fast_path():
    converted = convert_flow_to_kgs(
        3600.0,
        "Sm3/h",
        {"MW": 16.04},
        "coolprop",
        thermo_solver=_MWSolver(),
        logger=logging.getLogger("test"),
        std_press_pa=101325.0,
        standard_temp_k=288.15,
        normal_temp_k=273.15,
    )

    expected_density = 101325.0 * 0.01604 / (8.314462 * 288.15)
    assert converted == pytest.approx(expected_density)


def test_pressure_validation_requires_explicit_gauge_units():
    with pytest.raises(UnitConversionError):
        UnitSystem.validate_pressure_value(-1, "psi")

    with pytest.raises(UnitConversionError):
        UnitSystem.validate_pressure_value(-1, "bar")

    assert UnitSystem.validate_pressure_value(-1, "psig") is True


def test_pressure_and_temperature_validation_reject_none_values():
    with pytest.raises(UnitConversionError, match="Gecersiz basinc"):
        UnitSystem.validate_pressure_value(None, "bar")

    with pytest.raises(UnitConversionError, match="Gecersiz sicaklik"):
        UnitSystem.validate_temperature_value(None, "K")


def test_direct_unit_conversions_wrap_non_numeric_values():
    with pytest.raises(UnitConversionError, match="Gecersiz basinc"):
        UnitSystem.convert_pressure(None, "bar", "Pa")

    with pytest.raises(UnitConversionError, match="Gecersiz sicaklik"):
        UnitSystem.convert_temperature(None, "°C", "K")


def test_pressure_conversion_respects_gauge_and_absolute_units():
    ambient = 100000.0

    assert UnitSystem.convert_pressure(1.0, "bar(g)", "Pa", ambient) == pytest.approx(200000.0)
    assert UnitSystem.convert_pressure(200000.0, "Pa", "bar(g)", ambient) == pytest.approx(1.0)
    assert UnitSystem.convert_pressure(2.0, "bar(a)", "bar(g)", ambient) == pytest.approx(1.0)


def test_temperature_conversion_respects_rankine_and_fahrenheit():
    assert UnitSystem.convert_temperature(32.0, "°F", "K") == pytest.approx(273.15, rel=1e-6)
    assert UnitSystem.convert_temperature(491.67, "°R", "K") == pytest.approx(273.15, rel=1e-6)


def test_result_conversion_supports_heating_value_and_fuel_flow():
    assert convert_result_value(50000.0, "kJ/kg", "MJ/kg", "heating_value") == pytest.approx(50.0)
    assert convert_result_value(3600.0, "kg/h", "kg/s", "fuel_flow") == pytest.approx(1.0)

    volumetric = convert_result_value(
        100.0,
        "kg/h",
        "Sm³/h",
        "fuel_flow",
        gas_obj={"MW": 16.0},
        eos_method="pr",
        thermo_solver=_DensitySolver(2.0),
    )
    assert volumetric == pytest.approx(50.0)


def test_result_conversion_rejects_unknown_quantity_types():
    with pytest.raises(UnitConversionError):
        convert_result_value(1.0, "kW", "MW", "unknown")
