"""Gas-turbine site performance correction helpers.

The model is intentionally transparent: it applies user-entered site
correction factors instead of embedding proprietary OEM/standard curves.
"""

from __future__ import annotations

import math

ISO_TEMPERATURE_C = 15.0
ISO_TEMPERATURE_K = 288.15
ISO_PRESSURE_KPA = 101.325
ISO_RELATIVE_HUMIDITY_PCT = 60.0
EXHAUST_REFERENCE_LOSS_KPA = 0.4903  # approximately 50 mmH2O
STANDARD_ASME_PTC10 = "ASME PTC 10"
STANDARD_ASME_PTC22 = "ASME PTC 22"
STANDARD_ISO_2314 = "ISO 2314"
SUPPORTED_PERFORMANCE_STANDARDS = (STANDARD_ASME_PTC10, STANDARD_ASME_PTC22, STANDARD_ISO_2314)


def coerce_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def ambient_pressure_from_altitude_kpa(altitude_m):
    altitude = coerce_float(altitude_m, 0.0)
    if altitude <= 0:
        return ISO_PRESSURE_KPA
    return ISO_PRESSURE_KPA * math.pow(max(0.0, 1.0 - 2.25577e-5 * altitude), 5.25588)


def normalize_correction_inputs(values):
    values = values or {}
    altitude_m = coerce_float(values.get("altitude_m", values.get("altitude", 0.0)), 0.0)
    ambient_pressure = coerce_float(values.get("ambient_pressure_kpa", values.get("ambient_pressure")), 0.0)
    if ambient_pressure <= 0:
        ambient_pressure = ambient_pressure_from_altitude_kpa(altitude_m)

    return {
        "standard": values.get("standard", STANDARD_ASME_PTC22),
        "ambient_temp_c": coerce_float(values.get("ambient_temp_c", values.get("ambient_temp")), ISO_TEMPERATURE_C),
        "ambient_pressure_kpa": ambient_pressure,
        "relative_humidity_pct": coerce_float(
            values.get("relative_humidity_pct", values.get("humidity")), ISO_RELATIVE_HUMIDITY_PCT
        ),
        "altitude_m": altitude_m,
        "inlet_pressure_loss_kpa": max(0.0, coerce_float(values.get("inlet_pressure_loss_kpa"), 0.0)),
        "exhaust_pressure_loss_kpa": max(0.0, coerce_float(values.get("exhaust_pressure_loss_kpa"), 0.0)),
        "manual_power_factor": coerce_float(values.get("manual_power_factor"), 1.0),
        "manual_heat_rate_factor": coerce_float(values.get("manual_heat_rate_factor"), 1.0),
    }


def calculate_site_correction_factors(values):
    inputs = normalize_correction_inputs(values)
    standard = inputs["standard"] if inputs["standard"] in SUPPORTED_PERFORMANCE_STANDARDS else STANDARD_ASME_PTC22
    ambient_temp_k = inputs["ambient_temp_c"] + 273.15
    ambient_pressure = max(inputs["ambient_pressure_kpa"], 1e-9)

    temperature_factor = ISO_TEMPERATURE_K / max(ambient_temp_k, 1e-9)
    pressure_factor = ambient_pressure / ISO_PRESSURE_KPA
    altitude_factor = ambient_pressure_from_altitude_kpa(inputs["altitude_m"]) / ISO_PRESSURE_KPA
    inlet_factor = clamp((ambient_pressure - inputs["inlet_pressure_loss_kpa"]) / ambient_pressure, 0.50, 1.0)
    exhaust_factor = clamp(
        1.0 - 0.005 * (inputs["exhaust_pressure_loss_kpa"] / EXHAUST_REFERENCE_LOSS_KPA),
        0.50,
        1.0,
    )
    humidity_factor = clamp(1.0 - 0.0002 * (inputs["relative_humidity_pct"] - ISO_RELATIVE_HUMIDITY_PCT), 0.97, 1.03)
    manual_power_factor = max(inputs["manual_power_factor"], 1e-9)
    manual_heat_rate_factor = max(inputs["manual_heat_rate_factor"], 1e-9)

    if standard == STANDARD_ASME_PTC10:
        # PTC 10 evaluates compressor performance. Gas-turbine ambient/site
        # corrections are not applied unless the user supplies OEM multipliers.
        applied_temperature_factor = 1.0
        applied_pressure_factor = 1.0
        applied_altitude_factor = 1.0
        applied_inlet_factor = 1.0
        applied_exhaust_factor = 1.0
        applied_humidity_factor = 1.0
    else:
        applied_temperature_factor = temperature_factor
        applied_pressure_factor = pressure_factor
        applied_altitude_factor = altitude_factor
        applied_inlet_factor = inlet_factor
        applied_exhaust_factor = exhaust_factor
        applied_humidity_factor = humidity_factor

    power_factor = (
        applied_temperature_factor
        * applied_pressure_factor
        * applied_inlet_factor
        * applied_exhaust_factor
        * applied_humidity_factor
        * manual_power_factor
    )
    heat_rate_factor = (1.0 / max(power_factor, 1e-9)) * manual_heat_rate_factor

    return {
        "inputs": inputs,
        "standard": standard,
        "temperature_factor": temperature_factor,
        "pressure_factor": pressure_factor,
        "altitude_factor": altitude_factor,
        "inlet_loss_factor": inlet_factor,
        "exhaust_loss_factor": exhaust_factor,
        "humidity_factor": humidity_factor,
        "applied_temperature_factor": applied_temperature_factor,
        "applied_pressure_factor": applied_pressure_factor,
        "applied_altitude_factor": applied_altitude_factor,
        "applied_inlet_loss_factor": applied_inlet_factor,
        "applied_exhaust_loss_factor": applied_exhaust_factor,
        "applied_humidity_factor": applied_humidity_factor,
        "manual_power_factor": manual_power_factor,
        "manual_heat_rate_factor": manual_heat_rate_factor,
        "power_factor": power_factor,
        "heat_rate_factor": heat_rate_factor,
        "corrected_to": (
            "ASME PTC 10 compressor performance basis"
            if standard == STANDARD_ASME_PTC10
            else f"{standard} reference-style conditions"
        ),
    }


def apply_site_corrections(actual_power_kw, actual_heat_rate_kj_kwh, values):
    factors = calculate_site_correction_factors(values)
    power_factor = max(factors["power_factor"], 1e-9)
    heat_rate_factor = max(factors["heat_rate_factor"], 1e-9)
    return {
        "corrected_power_kw": coerce_float(actual_power_kw, 0.0) / power_factor,
        "corrected_heat_rate_kj_kwh": coerce_float(actual_heat_rate_kj_kwh, 0.0) / heat_rate_factor,
        "correction_factors": factors,
    }
