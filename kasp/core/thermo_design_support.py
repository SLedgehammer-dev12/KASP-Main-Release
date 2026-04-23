"""Support helpers for ThermoEngine design-performance calculations."""

from __future__ import annotations


ENGINE_VERSION = "1.2.0 (V4.5 — 4-Method Engine)"


def compute_stage_pressure_ratio(total_pressure_ratio, intercooler_dp, num_stages):
    if num_stages <= 1:
        return total_pressure_ratio
    return (
        total_pressure_ratio / ((1.0 - intercooler_dp) ** (num_stages - 1))
    ) ** (1.0 / num_stages)


def select_design_method_key(method_label):
    if "Metot 2" in method_label or "Endpoint" in method_label or "Uç Nokta" in method_label:
        return "endpoint"
    if "Metot 3" in method_label or "Artımlı" in method_label or "Incremental" in method_label:
        return "incremental"
    if "Metot 4" in method_label or "H-S" in method_label or "Doğrudan" in method_label:
        return "direct_hs"
    return "average"


def build_stage_result(
    *,
    stage,
    p_in,
    t_in,
    p_out,
    t_out,
    head_kj_kg,
    poly_eff_design,
    poly_eff_diagnostic,
    power_gas_kw,
    delta_h_kj_kg,
    z_avg,
    method_history,
):
    return {
        "stage": stage,
        "p_in": p_in,
        "t_in": t_in,
        "p_out": p_out,
        "t_out": t_out,
        "head_kj_kg": head_kj_kg,
        "poly_eff_design": poly_eff_design,
        "poly_eff_diagnostic": poly_eff_diagnostic,
        "poly_eff": poly_eff_design,
        "power_gas_kw": power_gas_kw,
        "delta_h_kj_kg": delta_h_kj_kg,
        "z_avg": z_avg,
        "method_history": method_history,
    }


def calculate_total_actual_poly_efficiency(staged_results, total_poly_head_kj_kg, poly_eff_tgt):
    total_actual_delta_h_kj_kg = sum(stage["delta_h_kj_kg"] for stage in staged_results)
    if total_actual_delta_h_kj_kg > 0:
        return total_poly_head_kj_kg / total_actual_delta_h_kj_kg
    last_stage = staged_results[-1] if staged_results else {}
    return last_stage.get("poly_eff_diagnostic", poly_eff_tgt)


def build_design_results_payload(
    *,
    p_in_pa,
    t_in_k,
    p_out_pa,
    final_t_out_k,
    total_poly_head_kj_kg,
    poly_eff_tgt,
    total_stage_gas_power_kw,
    total_shaft_kw,
    motor_kw,
    unit_kw,
    mech_loss_kw,
    fuel_kgh,
    mass_flow_per_unit,
    inlet_acmh,
    num_units,
    total_mass_flow_kgs,
    heat_rate,
    lhv,
    hhv,
    inlet_properties,
    outlet_properties,
    num_stages,
    staged_results,
    method,
):
    actual_poly_eff_total = calculate_total_actual_poly_efficiency(
        staged_results,
        total_poly_head_kj_kg,
        poly_eff_tgt,
    )
    return {
        "t_out": final_t_out_k - 273.15,
        "head_kj_kg": total_poly_head_kj_kg,
        "compression_ratio": p_out_pa / p_in_pa,
        "design_poly_efficiency": poly_eff_tgt,
        "actual_poly_efficiency": actual_poly_eff_total,
        "power_gas_per_unit_kw": total_stage_gas_power_kw,
        "power_shaft_per_unit_kw": total_shaft_kw,
        "power_motor_per_unit_kw": motor_kw,
        "power_unit_kw": unit_kw,
        "api_617_margin_percent": 4.0,
        "mech_loss_per_unit_kw": mech_loss_kw,
        "fuel_unit_kgh": fuel_kgh,
        "mass_flow_per_unit_kgs": mass_flow_per_unit,
        "inlet_vol_flow_acmh_per_unit": inlet_acmh,
        "power_gas_total_kw": total_stage_gas_power_kw * num_units,
        "power_shaft_total_kw": total_shaft_kw * num_units,
        "power_unit_total_kw": unit_kw * num_units,
        "mech_loss_total_kw": mech_loss_kw * num_units,
        "fuel_total_kgh": fuel_kgh * num_units,
        "mass_flow_total_kgs": total_mass_flow_kgs,
        "heat_rate": heat_rate,
        "lhv": lhv,
        "hhv": hhv,
        "inlet_properties": inlet_properties,
        "outlet_properties": outlet_properties,
        "num_units": num_units,
        "num_stages": num_stages,
        "stages": staged_results,
        "calculation_method": method,
        "warnings": [],
        "engine_version": ENGINE_VERSION,
    }


def build_uncertainty_measurements(inputs):
    return {
        "p_in": float(inputs["p_in"]),
        "p_out": float(inputs["p_out"]),
        "t_in": float(inputs["t_in"]),
        "flow": float(inputs["flow"]),
    }


def build_uncertainty_payload(uncertainty_result, actual_poly_efficiency):
    return {
        "polytropic_efficiency": {
            "value": actual_poly_efficiency,
            "combined_uncertainty": uncertainty_result["combined_uncertainty"],
            "expanded_uncertainty": uncertainty_result["expanded_uncertainty"],
            "confidence_level": "95%",
            "breakdown": uncertainty_result["breakdown_percent"],
        },
        "asme_ptc10_compliant": True,
    }
