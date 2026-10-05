from __future__ import annotations

import math
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
        "pressure": [
            "bar(a)", "bar(g)", "bar", "barg", "Pa", "kPa", "kpa", "MPa", "mpa",
            "psia", "psig", "psi", "atm", "kg/cm²", "kg/cm2"
        ],
        "temperature": ["°C", "degC", "C", "K", "°F", "degF", "F", "°R"],
        "flow": ["kg/h", "kg/s", "m³/h", "Sm³/h", "Nm³/h", "MMSCFD", "MMSCMD", "ACMH", "kgmol/h", "kmol/h"],
        "power": ["kW", "MW", "hp", "Btu/h"],
        "length": ["mm", "m", "inch", "ft"],
        "energy": ["kJ", "J", "kcal", "Btu", "kWh"],
    }

    TEMPERATURE_ALIASES = {
        "Â°C": "°C",
        "Â°F": "°F",
        "Â°R": "°R",
        "°c": "°C",
        "c": "°C",
        "degc": "°C",
        "deg_c": "°C",
        "deg c": "°C",
        "celsius": "°C",
        "°f": "°F",
        "f": "°F",
        "degf": "°F",
        "deg_f": "°F",
        "deg f": "°F",
        "fahrenheit": "°F",
        "°r": "°R",
        "r": "°R",
        "degr": "°R",
        "deg_r": "°R",
        "deg r": "°R",
        "rankine": "°R",
        "k": "K",
        "kelvin": "K",
    }

    PRESSURE_ALIASES = {
        "kg/cmÂ²": "kg/cm²",
        "kg/cm²": "kg/cm²",
        "kg/cm2": "kg/cm²",
        "kg/cm^2": "kg/cm²",
        "kgf/cm2": "kg/cm²",
        "kgf/cm²": "kg/cm²",
        "bar": "bar",
        "bara": "bar",
        "bar(a)": "bar",
        "bar_a": "bar",
        "bar a": "bar",
        "barg": "bar(g)",
        "bar(g)": "bar(g)",
        "bar_g": "bar(g)",
        "bar g": "bar(g)",
        "pa": "Pa",
        "pascal": "Pa",
        "kpa": "kPa",
        "mpa": "MPa",
        "psi": "psi",
        "psia": "psi",
        "psi(a)": "psi",
        "psi_a": "psi",
        "psi a": "psi",
        "psig": "psig",
        "psi(g)": "psig",
        "psi_g": "psig",
        "psi g": "psig",
        "atm": "atm",
    }

    @classmethod
    def altitude_to_ambient_pressure(cls, altitude_m=0.0):
        """
        Uluslararası Standart Atmosfer (ISA) modeline göre rakımdan (metre)
        yerel atmosferik basıncı (Pa) hesaplar.
        """
        h = max(-500.0, float(altitude_m or 0.0))
        t0 = cls.STANDARD_TEMP_K  # 288.15 K
        l_rate = 0.0065  # K/m
        p0 = cls.STD_PRESS_PA  # 101325.0 Pa
        exponent = (cls.GRAVITATIONAL_ACCELERATION * 0.0289644) / (cls.R_UNIVERSAL_J_MOL_K * l_rate)
        if h > 11000.0:
            p_11k = p0 * ((1.0 - (l_rate * 11000.0) / t0) ** exponent)
            return p_11k * math.exp(
                -cls.GRAVITATIONAL_ACCELERATION * 0.0289644 * (h - 11000.0) / (cls.R_UNIVERSAL_J_MOL_K * 216.65)
            )
        return p0 * ((1.0 - (l_rate * h) / t0) ** exponent)

    @classmethod
    def _canonical_pressure_unit(cls, unit):
        if not unit:
            return "Pa"
        raw = str(unit).strip()
        if raw in cls.PRESSURE_ALIASES:
            return cls.PRESSURE_ALIASES[raw]
        low = raw.lower()
        return cls.PRESSURE_ALIASES.get(low, raw)

    @classmethod
    def _canonical_temperature_unit(cls, unit):
        if not unit:
            return "K"
        raw = str(unit).strip()
        if raw in cls.TEMPERATURE_ALIASES:
            return cls.TEMPERATURE_ALIASES[raw]
        low = raw.lower()
        return cls.TEMPERATURE_ALIASES.get(low, raw)

    @staticmethod
    def _coerce_numeric(value, quantity_name, unit=None):
        try:
            numeric = float(value)
        except (TypeError, ValueError) as error:
            raise UnitConversionError(f"Gecersiz {quantity_name} degeri: {value}", value, unit) from error
        if not math.isfinite(numeric):
            raise UnitConversionError(
                f"Gecersiz {quantity_name} degeri (NaN/sonsuz): {value}", value, unit
            )
        return numeric

    @classmethod
    def convert_pressure(cls, value, from_unit, to_unit="Pa", ambient_pressure_pa=None, altitude_m=None):
        if ambient_pressure_pa is not None:
            ambient = ambient_pressure_pa
        elif altitude_m is not None:
            ambient = cls.altitude_to_ambient_pressure(altitude_m)
        else:
            ambient = cls.STD_PRESS_PA
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
    def validate_pressure_value(cls, value, unit, ambient_pressure_pa=None, altitude_m=None):
        unit = cls._canonical_pressure_unit(unit)
        numeric_value = cls._coerce_numeric(value, "basinc", unit)

        if unit in {"bar(g)", "psig"}:
            pa_value = cls.convert_pressure(
                numeric_value,
                unit,
                "Pa",
                ambient_pressure_pa=ambient_pressure_pa,
                altitude_m=altitude_m,
            )
            if pa_value <= 0:
                raise UnitConversionError(
                    f"Mutlak vakum altinda basinc degeri ({numeric_value} {unit} -> {pa_value:.1f} Pa) gecersiz",
                    numeric_value,
                    unit,
                )
            return True

        if numeric_value <= 0:
            raise UnitConversionError(
                f"Pozitif olmayan mutlak basinc degeri ({numeric_value} {unit}) gecersiz",
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
