from __future__ import annotations

from .exceptions import UnitConversionError


class UnitSystem:
    """Central unit conversion helpers."""

    STD_PRESS_PA = 101325.0
    NORMAL_TEMP_K = 273.15
    STANDARD_TEMP_K = 288.15
    GRAVITATIONAL_ACCELERATION = 9.80665
    R_UNIVERSAL_J_MOL_K = 8.314462
    KJ_PER_BTU = 1.055056
    KG_PER_LB = 0.45359237
    KJ_PER_KCAL = 4.184
    METER_TO_FOOT = 3.28084

    UNITS = {
        "pressure": ["bar(a)", "bar(g)", "bar", "Pa", "kPa", "MPa", "psia", "psig", "psi", "atm", "kg/cm²"],
        "temperature": ["°C", "K", "°F", "°R"],
        "flow": ["kg/h", "kg/s", "m³/h", "Sm³/h", "Nm³/h", "MMSCFD", "MMSCMD", "ACMH", "kgmol/h", "kmol/h"],
        "power": ["kW", "MW", "hp", "Btu/h"],
        "length": ["mm", "m", "inch", "ft"],
        "energy": ["kJ", "J", "kcal", "Btu", "kWh"],
    }

    TEMPERATURE_ALIASES = {
        "Â°C": "°C",
        "Â°F": "°F",
        "Â°R": "°R",
    }

    PRESSURE_ALIASES = {
        "kg/cmÂ²": "kg/cm²",
    }

    @classmethod
    def _canonical_pressure_unit(cls, unit):
        return cls.PRESSURE_ALIASES.get(unit, unit)

    @classmethod
    def _canonical_temperature_unit(cls, unit):
        return cls.TEMPERATURE_ALIASES.get(unit, unit)

    @staticmethod
    def _coerce_numeric(value, quantity_name, unit=None):
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise UnitConversionError(f"Gecersiz {quantity_name} degeri: {value}", value, unit) from error

    @classmethod
    def convert_pressure(cls, value, from_unit, to_unit="Pa", ambient_pressure_pa=None):
        ambient = ambient_pressure_pa if ambient_pressure_pa is not None else cls.STD_PRESS_PA
        value = cls._coerce_numeric(value, "basinc", from_unit)
        from_unit = cls._canonical_pressure_unit(from_unit)
        to_unit = cls._canonical_pressure_unit(to_unit)
        if from_unit == to_unit:
            return value

        is_gauge = False
        if from_unit in {"bar(g)", "psig"}:
            is_gauge = True
            from_unit = "bar" if from_unit == "bar(g)" else "psi"

        if from_unit.endswith("(a)"):
            from_unit = from_unit.replace("(a)", "")
        if from_unit == "psia":
            from_unit = "psi"

        if from_unit == "Pa":
            pa_value = value
        elif from_unit == "kPa":
            pa_value = value * 1000.0
        elif from_unit == "MPa":
            pa_value = value * 1e6
        elif from_unit == "bar":
            pa_value = value * 1e5
        elif from_unit == "psi":
            pa_value = value * 6894.76
        elif from_unit == "atm":
            pa_value = value * 101325.0
        elif from_unit == "kg/cm²":
            pa_value = value * 98066.5
        else:
            raise UnitConversionError(f"Bilinmeyen basinc birimi: {from_unit}")

        if is_gauge:
            pa_value += ambient

        if to_unit == "Pa":
            return pa_value
        if to_unit == "kPa":
            return pa_value / 1000.0
        if to_unit == "MPa":
            return pa_value / 1e6
        if to_unit in {"bar", "bar(a)"}:
            return pa_value / 1e5
        if to_unit in {"psi", "psia"}:
            return pa_value / 6894.76
        if to_unit == "atm":
            return pa_value / 101325.0
        if to_unit == "kg/cm²":
            return pa_value / 98066.5
        if to_unit == "bar(g)":
            return (pa_value - ambient) / 1e5
        if to_unit == "psig":
            return (pa_value - ambient) / 6894.76
        raise UnitConversionError(f"Bilinmeyen hedef basinc birimi: {to_unit}")

    @classmethod
    def convert_temperature(cls, value, from_unit, to_unit="K"):
        value = cls._coerce_numeric(value, "sicaklik", from_unit)
        from_unit = cls._canonical_temperature_unit(from_unit)
        to_unit = cls._canonical_temperature_unit(to_unit)
        if from_unit == to_unit:
            return value

        if from_unit == "K":
            k_value = value
        elif from_unit == "°C":
            k_value = value + 273.15
        elif from_unit == "°F":
            k_value = (value + 459.67) * 5.0 / 9.0
        elif from_unit == "°R":
            k_value = value * 5.0 / 9.0
        else:
            raise UnitConversionError(f"Bilinmeyen sicaklik birimi: {from_unit}")

        if to_unit == "K":
            return k_value
        if to_unit == "°C":
            return k_value - 273.15
        if to_unit == "°F":
            return k_value * 9.0 / 5.0 - 459.67
        if to_unit == "°R":
            return k_value * 9.0 / 5.0
        raise UnitConversionError(f"Bilinmeyen hedef sicaklik birimi: {to_unit}")

    @classmethod
    def validate_pressure_value(cls, value, unit):
        unit = cls._canonical_pressure_unit(unit)
        numeric_value = cls._coerce_numeric(value, "basinc", unit)

        if unit in {"bar(g)", "psig"}:
            return True

        if numeric_value < 0:
            raise UnitConversionError(
                f"Negatif basinc degeri ({numeric_value} {unit}) gecersiz",
                numeric_value,
                unit,
            )
        return True

    @classmethod
    def validate_temperature_value(cls, value, unit):
        unit = cls._canonical_temperature_unit(unit)
        numeric_value = cls._coerce_numeric(value, "sicaklik", unit)

        k_value = cls.convert_temperature(numeric_value, unit, "K")
        if k_value < 0:
            raise UnitConversionError(f"Mutlak sifirin altinda sicaklik: {numeric_value} {unit}")
        return True
