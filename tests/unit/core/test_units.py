import pytest
from kasp.core.units import UnitSystem


class TestPressureConversion:
    @pytest.mark.parametrize("value,unit,expected_pa", [
        (1.0, "bar(a)", 100000.0),
        (2.5, "bar(a)", 250000.0),
        (1.0, "kPa", 1000.0),
        (100.0, "kPa", 100000.0),
        (14.7, "psia", 101353.0),
        (1.0, "MPa", 1000000.0),
        (1.0, "atm", 101325.0),
    ])
    def test_pressure_to_pa(self, value, unit, expected_pa):
        result = UnitSystem.convert_pressure(value, unit, "Pa")
        assert result is not None
        if result is not None:
            assert abs(result - expected_pa) / max(expected_pa, 1.0) < 0.02

    def test_gauge_to_absolute(self):
        result = UnitSystem.convert_pressure(1.0, "bar(g)", "Pa", ambient_pressure_pa=101325)
        assert abs(result - 201325.0) < 1000.0

    def test_negative_absolute_pressure_rejected(self):
        with pytest.raises(ValueError):
            UnitSystem.validate_pressure_value(-1.0, "bar(a)")


class TestTemperatureConversion:
    @pytest.mark.parametrize("value,unit,expected_k", [
        (0.0, "\u00b0C", 273.15),
        (100.0, "\u00b0C", 373.15),
        (-40.0, "\u00b0C", 233.15),
        (32.0, "\u00b0F", 273.15),
        (212.0, "\u00b0F", 373.15),
        (300.0, "K", 300.0),
    ])
    def test_temperature_to_k(self, value, unit, expected_k):
        result = UnitSystem.convert_temperature(value, unit, "K")
        assert abs(result - expected_k) < 0.5

    def test_below_absolute_zero_rejected(self):
        with pytest.raises(ValueError):
            UnitSystem.validate_temperature_value(-300.0, "\u00b0C")
