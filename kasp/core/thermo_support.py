"""Shared helpers for the ThermoEngine facade."""

from __future__ import annotations

import datetime

from kasp.core.exceptions import UnitConversionError
from kasp.core.constants import R_UNIVERSAL_J_MOL_K
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


STANDARD_VOLUME_UNITS = {"Sm3/h", "Sm³/h", "SmÂ³/h"}
NORMAL_VOLUME_UNITS = {"Nm3/h", "Nm³/h", "NmÂ³/h"}
MOLAR_FLOW_UNITS = {"kgmol/h", "kmol/h"}


def convert_pressure_to_pa(value, unit, ambient_pressure_pa=None):
    try:
        UnitSystem.validate_pressure_value(value, unit)
        return UnitSystem.convert_pressure(value, unit, "Pa", ambient_pressure_pa)
    except UnitConversionError as error:
        raise UnitConversionError(f"Basinc donusum hatasi: {error}", value, unit)


def convert_temperature_to_k(value, unit):
    try:
        UnitSystem.validate_temperature_value(value, unit)
        return UnitSystem.convert_temperature(value, unit, "K")
    except UnitConversionError as error:
        raise UnitConversionError(f"Sicaklik donusum hatasi: {error}", value, unit)


def _resolve_reference_density(thermo_solver, pressure_pa, temperature_k, gas_obj, eos_method, *, prefer_mw=False):
    if prefer_mw:
        infer_mw = getattr(thermo_solver, "infer_mw_g_mol", None)
        mw_g_mol = infer_mw(gas_obj) if infer_mw is not None else None
        if mw_g_mol and mw_g_mol > 0 and temperature_k > 0:
            return pressure_pa * (mw_g_mol / 1000.0) / (R_UNIVERSAL_J_MOL_K * temperature_k)

    density = thermo_solver.get_properties(pressure_pa, temperature_k, gas_obj, eos_method).density
    if density <= 0:
        raise UnitConversionError("Referans yogunluk hesaplanamadi")
    return density


def _resolve_mixture_mw_g_mol(thermo_solver, gas_obj, eos_method, std_press_pa, standard_temp_k):
    mw = thermo_solver.infer_mw_g_mol(gas_obj)
    if mw is None:
        mw = thermo_solver.get_properties(std_press_pa, standard_temp_k, gas_obj, eos_method).MW
    if mw is None or mw <= 0:
        raise UnitConversionError("Mol debisi icin karisim molar kutlesi belirlenemedi")
    return mw


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
    try:
        value_float = float(value)

        if unit == "kg/s":
            return value_float
        if unit == "kg/h":
            return value_float / 3600.0

        if unit in STANDARD_VOLUME_UNITS or unit == "MMSCMD":
            density = _resolve_reference_density(
                thermo_solver, std_press_pa, standard_temp_k, gas_obj, eos_method, prefer_mw=True
            )
            if unit in STANDARD_VOLUME_UNITS:
                return (value_float * density) / 3600.0
            return (value_float * 1e6 / 86400.0) * density

        if unit in NORMAL_VOLUME_UNITS:
            density = _resolve_reference_density(
                thermo_solver, std_press_pa, normal_temp_k, gas_obj, eos_method, prefer_mw=True
            )
            return (value_float * density) / 3600.0

        if unit == "MMSCFD":
            t_std_k = convert_temperature_to_k(60, "°F")
            p_std_pa = convert_pressure_to_pa(14.73, "psia")
            density = _resolve_reference_density(
                thermo_solver, p_std_pa, t_std_k, gas_obj, eos_method, prefer_mw=True
            )
            vol_m3_sec = value_float * 1e6 * 0.0283168 / 86400.0
            return vol_m3_sec * density

        if unit in MOLAR_FLOW_UNITS:
            mw = _resolve_mixture_mw_g_mol(
                thermo_solver, gas_obj, eos_method, std_press_pa, standard_temp_k
            )
            return (value_float * mw) / 3600.0

    except UnitConversionError:
        raise
    except Exception as error:
        logger.error("Debi donusum hatasi: %s", error)
        raise UnitConversionError(f"Debi donusumu basarisiz: {error}", value, unit)

    raise UnitConversionError(f"Bilinmeyen akis birimi: {unit}", value, unit)


def _convert_power_value(value: float, from_unit: str, to_unit: str) -> float:
    kw_value = value
    if from_unit == "MW":
        kw_value = value * 1000.0
    elif from_unit == "hp":
        kw_value = value * 0.7457
    elif from_unit == "Btu/h":
        kw_value = value * 0.00029307107
    elif from_unit != "kW":
        raise UnitConversionError(f"Desteklenmeyen guc birimi: {from_unit}")

    if to_unit == "kW":
        return kw_value
    if to_unit == "MW":
        return kw_value / 1000.0
    if to_unit == "hp":
        return kw_value / 0.7457
    if to_unit == "Btu/h":
        return kw_value / 0.00029307107
    raise UnitConversionError(f"Desteklenmeyen hedef guc birimi: {to_unit}")


def _convert_head_value(value: float, from_unit: str, to_unit: str) -> float:
    if from_unit == "kJ/kg" and to_unit == "ft-lbf/lbm":
        return value * 334.55256555
    if from_unit == "ft-lbf/lbm" and to_unit == "kJ/kg":
        return value / 334.55256555
    raise UnitConversionError(f"Desteklenmeyen head donusumu: {from_unit} -> {to_unit}")


def _convert_heat_rate_value(value: float, from_unit: str, to_unit: str) -> float:
    base_value = value
    if from_unit == "Btu/kWh":
        base_value = value / 0.947817
    elif from_unit == "kcal/kWh":
        base_value = value / 0.239006
    elif from_unit == "Btu/hp-hr":
        base_value = value / 0.706787
    elif from_unit != "kJ/kWh":
        raise UnitConversionError(f"Desteklenmeyen isi orani birimi: {from_unit}")

    if to_unit == "kJ/kWh":
        return base_value
    if to_unit == "Btu/kWh":
        return base_value * 0.947817
    if to_unit == "kcal/kWh":
        return base_value * 0.239006
    if to_unit == "Btu/hp-hr":
        return base_value * 0.706787
    raise UnitConversionError(f"Desteklenmeyen hedef isi orani birimi: {to_unit}")


def _convert_heating_value(value: float, from_unit: str, to_unit: str) -> float:
    kj_per_kg = value
    if from_unit == "MJ/kg":
        kj_per_kg = value * 1000.0
    elif from_unit == "kcal/kg":
        kj_per_kg = value * 4.184
    elif from_unit == "Btu/lbm":
        kj_per_kg = value * 2.326
    elif from_unit != "kJ/kg":
        raise UnitConversionError(f"Desteklenmeyen isil deger birimi: {from_unit}")

    if to_unit == "kJ/kg":
        return kj_per_kg
    if to_unit == "MJ/kg":
        return kj_per_kg / 1000.0
    if to_unit == "kcal/kg":
        return kj_per_kg / 4.184
    if to_unit == "Btu/lbm":
        return kj_per_kg / 2.326
    raise UnitConversionError(f"Desteklenmeyen hedef isil deger birimi: {to_unit}")


def _convert_fuel_flow(
    value: float,
    from_unit: str,
    to_unit: str,
    *,
    gas_obj=None,
    eos_method=None,
    lhv_kj_kg=None,
    thermo_solver=None,
    std_press_pa=101325.0,
    standard_temp_k=288.15,
    normal_temp_k=273.15,
):
    kg_per_hour = value
    if from_unit == "kg/s":
        kg_per_hour = value * 3600.0
    elif from_unit == "lb/h":
        kg_per_hour = value * 0.45359237
    elif from_unit != "kg/h":
        raise UnitConversionError(f"Desteklenmeyen yakit debisi birimi: {from_unit}")

    if to_unit == "kg/h":
        return kg_per_hour
    if to_unit == "kg/s":
        return kg_per_hour / 3600.0
    if to_unit == "lb/h":
        return kg_per_hour / 0.45359237

    if to_unit in STANDARD_VOLUME_UNITS or to_unit in NORMAL_VOLUME_UNITS:
        if thermo_solver is None or gas_obj is None or eos_method is None:
            raise UnitConversionError(
                f"Yakit debisini {to_unit} birimine cevirmek icin gaz ozellikleri gerekli"
            )
        reference_temp = standard_temp_k if to_unit in STANDARD_VOLUME_UNITS else normal_temp_k
        density = thermo_solver.get_properties(std_press_pa, reference_temp, gas_obj, eos_method).density
        if density <= 0:
            raise UnitConversionError("Standart yogunluk hesaplanamadi")
        return kg_per_hour / density

    if to_unit == "J/h":
        if lhv_kj_kg is None:
            raise UnitConversionError("Enerji tabanli yakit donusumu icin LHV gerekli")
        return kg_per_hour * lhv_kj_kg * 1000.0

    if to_unit == "cal/h":
        if lhv_kj_kg is None:
            raise UnitConversionError("Enerji tabanli yakit donusumu icin LHV gerekli")
        return kg_per_hour * lhv_kj_kg * 239.005736

    raise UnitConversionError(f"Desteklenmeyen hedef yakit debisi birimi: {to_unit}")


def convert_result_value(
    value: float,
    from_unit: str,
    to_unit: str,
    quantity_type: str,
    gas_obj=None,
    eos_method=None,
    lhv_kj_kg=None,
    *,
    thermo_solver=None,
    logger=None,
    std_press_pa=101325.0,
    standard_temp_k=288.15,
    normal_temp_k=273.15,
) -> float:
    if from_unit == to_unit:
        return value

    try:
        if quantity_type == "temperature":
            return UnitSystem.convert_temperature(value, from_unit, to_unit)
        if quantity_type == "pressure":
            return UnitSystem.convert_pressure(value, from_unit, to_unit)
        if quantity_type == "power":
            return _convert_power_value(value, from_unit, to_unit)
        if quantity_type == "head":
            return _convert_head_value(value, from_unit, to_unit)
        if quantity_type == "heat_rate":
            return _convert_heat_rate_value(value, from_unit, to_unit)
        if quantity_type == "heating_value":
            return _convert_heating_value(value, from_unit, to_unit)
        if quantity_type == "fuel_flow":
            return _convert_fuel_flow(
                value,
                from_unit,
                to_unit,
                gas_obj=gas_obj,
                eos_method=eos_method,
                lhv_kj_kg=lhv_kj_kg,
                thermo_solver=thermo_solver,
                std_press_pa=std_press_pa,
                standard_temp_k=standard_temp_k,
                normal_temp_k=normal_temp_k,
            )
    except UnitConversionError:
        raise
    except Exception as error:
        if logger is not None:
            logger.error("Sonuc donusum hatasi (%s): %s", quantity_type, error)
        raise UnitConversionError(str(error), value, from_unit)

    raise UnitConversionError(f"Desteklenmeyen sonuc turu: {quantity_type}", value, from_unit)


def build_summary_report(inputs, results, selected_units, performance_stats, *, calculation_date=None):
    calculation_date = calculation_date or datetime.datetime.now().isoformat()
    recommended_turbines = []
    for index, unit in enumerate((selected_units or [])[:3]):
        recommended_turbines.append(
            {
                "rank": index + 1,
                "turbine": getattr(unit, "turbine_name", None)
                or unit.get("turbine_name")
                or unit.get("turbine"),
                "power": getattr(unit, "available_power_kw", None)
                if hasattr(unit, "available_power_kw")
                else unit.get("available_power_kw", 0),
                "efficiency": getattr(unit, "efficiency_rating", None)
                if hasattr(unit, "efficiency_rating")
                else unit.get("efficiency_rating"),
                "score": getattr(unit, "selection_score", None)
                if hasattr(unit, "selection_score")
                else unit.get("selection_score", 0),
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
            "description": "Ideal",
            "recommendation": "Mudahale gerekmez.",
        }
    if max_deviation <= 5.0:
        return {
            "status": "GOOD",
            "color": "blue",
            "description": "Iyi",
            "recommendation": "Gozlemleyin.",
        }
    if max_deviation <= 10.0:
        return {
            "status": "ACCEPTABLE",
            "color": "orange",
            "description": "Kabul edilebilir",
            "recommendation": "Bakim planlayin.",
        }
    return {
        "status": "POOR",
        "color": "red",
        "description": "Dusuk",
        "recommendation": "Acil bakim.",
    }
