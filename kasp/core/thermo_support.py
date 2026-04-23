"""Shared helpers for the ThermoEngine facade."""

from __future__ import annotations

import datetime

from kasp.core.exceptions import UnitConversionError
from kasp.core.units import UnitSystem


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_efficiency_reference(value, default=0.0):
    try:
        efficiency = float(value)
    except (TypeError, ValueError):
        return default
    return efficiency / 100.0 if efficiency > 1.0 else efficiency


def percent_deviation(actual, expected):
    if expected in (None, 0):
        return 0.0
    return ((actual - expected) / expected) * 100.0


def convert_pressure_to_pa(value, unit, ambient_pressure_pa=None):
    try:
        UnitSystem.validate_pressure_value(value, unit)
        return UnitSystem.convert_pressure(value, unit, "Pa", ambient_pressure_pa)
    except UnitConversionError as error:
        raise UnitConversionError(f"Basınç dönüşüm hatası: {error}", value, unit)


def convert_temperature_to_k(value, unit):
    try:
        UnitSystem.validate_temperature_value(value, unit)
        return UnitSystem.convert_temperature(value, unit, "K")
    except UnitConversionError as error:
        raise UnitConversionError(f"Sıcaklık dönüşüm hatası: {error}", value, unit)


def convert_flow_to_kgs(
    value,
    unit,
    gas_obj,
    eos_method,
    *,
    thermo_solver,
    logger,
    std_press_pa,
    standard_temp_k,
    normal_temp_k,
):
    """Convert volumetric or molar flow values to mass flow in kg/s."""
    if unit == "kg/s":
        return float(value)
    if unit == "kg/h":
        return float(value) / 3600.0

    try:
        value_float = float(value)
        if unit in ["Sm³/h", "MMSCMD"]:
            state_std = thermo_solver.get_properties(std_press_pa, standard_temp_k, gas_obj, eos_method)
            if unit == "Sm³/h":
                return (value_float * state_std.density) / 3600.0
            return (value_float * 1e6 / 86400) * state_std.density

        if unit == "Nm³/h":
            state_norm = thermo_solver.get_properties(std_press_pa, normal_temp_k, gas_obj, eos_method)
            return (value_float * state_norm.density) / 3600.0

        if unit == "MMSCFD":
            t_std_k = convert_temperature_to_k(60, "°F")
            p_std_pa = convert_pressure_to_pa(14.73, "psia")
            state_scfd = thermo_solver.get_properties(p_std_pa, t_std_k, gas_obj, eos_method)
            vol_m3_sec = value_float * 1e6 * 0.0283168 / 86400
            return vol_m3_sec * state_scfd.density

        if unit in ["kgmol/h", "kmol/h"]:
            mw = thermo_solver.infer_mw_g_mol(gas_obj)
            if mw is None:
                try:
                    mw = thermo_solver.get_properties(101325, 298.15, gas_obj, eos_method).MW
                except Exception:
                    mw = 16.04
                    logger.warning(
                        "MW inference failed for molar flow conversion, methane fallback used"
                    )
            return (value_float * mw) / 3600.0

    except Exception as error:
        logger.error(f"Debi dönüşüm hatası: {error}")
        raise UnitConversionError(f"Debi dönüşümü başarısız: {error}", value, unit)

    raise UnitConversionError(f"Bilinmeyen akış birimi: {unit}", value, unit)


def convert_result_value(value: float, from_unit: str, to_unit: str, quantity_type: str) -> float:
    if from_unit == to_unit:
        return value

    if quantity_type == "temperature":
        return UnitSystem.convert_temperature(value, from_unit, to_unit)
    if quantity_type == "pressure":
        return UnitSystem.convert_pressure(value, from_unit, to_unit)
    if quantity_type == "power":
        kw_value = value
        if from_unit == "MW":
            kw_value = value * 1000
        elif from_unit == "hp":
            kw_value = value * 0.7457

        if to_unit == "kW":
            return kw_value
        if to_unit == "MW":
            return kw_value / 1000
        if to_unit == "hp":
            return kw_value / 0.7457
    if quantity_type == "head":
        if from_unit == "kJ/kg" and to_unit == "ft-lbf/lbm":
            return value * 334.55256555
        if from_unit == "ft-lbf/lbm" and to_unit == "kJ/kg":
            return value / 334.55256555
    if quantity_type == "heat_rate":
        base_value = value
        if from_unit == "Btu/kWh":
            base_value = value / 0.947817
        elif from_unit == "kcal/kWh":
            base_value = value / 0.239006
        elif from_unit == "Btu/hp-hr":
            base_value = value / 0.706787

        if to_unit == "kJ/kWh":
            return base_value
        if to_unit == "Btu/kWh":
            return base_value * 0.947817
        if to_unit == "kcal/kWh":
            return base_value * 0.239006
        if to_unit == "Btu/hp-hr":
            return base_value * 0.706787
    return value


def build_summary_report(inputs, results, selected_units, performance_stats, *, calculation_date=None):
    calculation_date = calculation_date or datetime.datetime.now().isoformat()
    recommended_turbines = []
    for index, unit in enumerate((selected_units or [])[:3]):
        recommended_turbines.append(
            {
                "rank": index + 1,
                "turbine": getattr(unit, "turbine_name", None) or unit.get("turbine_name") or unit.get("turbine"),
                "power": getattr(unit, "available_power_kw", None) if hasattr(unit, "available_power_kw") else unit.get("available_power_kw", 0),
                "efficiency": getattr(unit, "efficiency_rating", None) if hasattr(unit, "efficiency_rating") else unit.get("efficiency_rating"),
                "score": getattr(unit, "selection_score", None) if hasattr(unit, "selection_score") else unit.get("selection_score", 0),
            }
        )

    return {
        "project_name": inputs.get("project_name", "Bilinmiyor"),
        "calculation_date": calculation_date,
        "basic_parameters": {
            "num_units": inputs.get("num_units", 1),
            "compression_ratio": results.get("compression_ratio", 1.0),
            "power_per_unit": results.get("power_unit_kw", 0),
            "total_power": results.get("power_unit_total_kw", 0),
            "outlet_temperature": results.get("t_out", 0),
        },
        "efficiency_metrics": {
            "poly_efficiency": float(inputs.get("poly_eff", 85)) / 100.0,
            "actual_poly_efficiency": results.get("actual_poly_efficiency", 0),
            "thermal_efficiency": float(inputs.get("therm_eff", 35)) / 100.0,
            "heat_rate": results.get("heat_rate", 0),
        },
        "recommended_turbines": recommended_turbines,
        "system_performance": performance_stats,
    }


def evaluate_performance_status(deviations):
    max_deviation = max(
        abs(deviations["deviation_poly_eff"]),
        abs(deviations["deviation_therm_eff"]),
        abs(deviations["deviation_heat_rate"]),
        abs(deviations["deviation_power"]),
    )

    if max_deviation <= 2.0:
        return {
            "status": "EXCELLENT",
            "color": "green",
            "description": "İdeal",
            "recommendation": "Müdahale gerekmez.",
        }
    if max_deviation <= 5.0:
        return {
            "status": "GOOD",
            "color": "blue",
            "description": "İyi",
            "recommendation": "Gözlemleyin.",
        }
    if max_deviation <= 10.0:
        return {
            "status": "ACCEPTABLE",
            "color": "orange",
            "description": "Kabul edilebilir",
            "recommendation": "Bakım planlayın.",
        }
    return {
        "status": "POOR",
        "color": "red",
        "description": "Düşük",
        "recommendation": "Acil bakım.",
    }
