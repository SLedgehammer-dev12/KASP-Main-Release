"""Support helpers for ThermoEngine design-performance calculations."""

from __future__ import annotations


ENGINE_VERSION = "1.2.0 (V4.5 — 4-Method Engine)"


def compute_stage_pressure_ratio(total_pressure_ratio, intercooler_dp, num_stages):
    if num_stages <= 1:
        return total_pressure_ratio
    return (
        total_pressure_ratio / ((1.0 - intercooler_dp) ** (num_stages - 1))
    ) ** (1.0 / num_stages)


def optimize_stage_pressure_ratios(
    p_in_pa: float,
    p_out_pa: float,
    num_stages: int,
    intercooler_dp: float = 0.0,
    t_in_k: float = 293.15,
    ic_t_k: float = 293.15,
    k_isen: float = 1.3,
) -> list[float]:
    """
    Çok kademeli kompresörler için kademe basınç oranlarını optimize eder.
    Ara soğutucu basınç kaybını (intercooler_dp) ve kademe giriş sıcaklıklarını dikkate alarak
    kademeler arası eşit iş (Equal Work) veya dengeli basınç dağılımı sağlar.
    """
    if num_stages <= 1:
        return [p_out_pa / p_in_pa]

    total_pr = p_out_pa / p_in_pa
    r_uniform = compute_stage_pressure_ratio(total_pr, intercooler_dp, num_stages)

    if abs(t_in_k - ic_t_k) < 1.0 or num_stages <= 1:
        return [r_uniform] * num_stages

    # Equal Work optimization when inlet temperatures differ (ambient vs intercooler)
    m = (k_isen - 1.0) / k_isen if k_isen > 1.05 else 0.25

    def eval_p_out(r1):
        w1_factor = (r1 ** m - 1.0)
        p_curr = p_in_pa
        for s in range(num_stages):
            t_s = t_in_k if s == 0 else ic_t_k
            r_s = max(1.001, (1.0 + (t_in_k / t_s) * w1_factor) ** (1.0 / m)) if s > 0 else r1
            p_out_s = p_curr * r_s
            if s < num_stages - 1:
                p_curr = p_out_s * (1.0 - intercooler_dp)
            else:
                p_curr = p_out_s
        return p_curr - p_out_pa

    try:
        # Simple bisection solver
        r_low, r_high = 1.001, max(2.0, total_pr)
        for _ in range(40):
            r_mid = 0.5 * (r_low + r_high)
            diff = eval_p_out(r_mid)
            if abs(diff) < 1.0:
                break
            if diff > 0:
                r_high = r_mid
            else:
                r_low = r_mid
        r1_opt = 0.5 * (r_low + r_high)
    except Exception:
        r1_opt = r_uniform

    w1_factor = (r1_opt ** m - 1.0)
    ratios = []
    for s in range(num_stages):
        t_s = t_in_k if s == 0 else ic_t_k
        r_s = max(1.001, (1.0 + (t_in_k / t_s) * w1_factor) ** (1.0 / m)) if s > 0 else r1_opt
        ratios.append(r_s)
    return ratios


def select_design_method_key(method_label):
    if "Metot 2" in method_label or "Endpoint" in method_label or "Uç Nokta" in method_label:
        return "endpoint"
    if "Metot 3" in method_label or "Artımlı" in method_label or "Incremental" in method_label:
        return "incremental"
    if "Metot 4" in method_label or "H-S" in method_label or "Doğrudan" in method_label:
        return "direct_hs"
    if "Metot 5" in method_label or "Huntington" in method_label or "RK45" in method_label or "Diferansiyel" in method_label:
        return "huntington_rk45"
    if "Metot 6" in method_label or "Schultz 3" in method_label or "3-Üslü" in method_label or "3-Exp" in method_label:
        return "schultz_3exp"
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
    fallback_used=False,
    fallback_sources=None,
    power_consistency_check_kw=0.0,
    compressor_selectable=True,
    selection_warnings=None,
    analysis_scope="IN_SCOPE",
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
        "power_consistency_check_kw": power_consistency_check_kw,
        "z_avg": z_avg,
        "method_history": method_history,
        "fallback_used": bool(fallback_used),
        "fallback_sources": list(fallback_sources or []),
        "compressor_selectable": bool(compressor_selectable),
        "selection_warnings": list(selection_warnings or []),
        "analysis_scope": analysis_scope,
    }


def calculate_total_actual_poly_efficiency(staged_results, total_poly_head_kj_kg, poly_eff_tgt):
    total_actual_delta_h_kj_kg = sum(stage["delta_h_kj_kg"] for stage in staged_results)
    if total_actual_delta_h_kj_kg > 0:
        return total_poly_head_kj_kg / total_actual_delta_h_kj_kg
    last_stage = staged_results[-1] if staged_results else {}
    return last_stage.get("poly_eff_diagnostic", poly_eff_tgt)


def summarize_method_convergence(staged_results):
    summaries = []
    for stage in staged_results:
        history = stage.get("method_history") or {}
        iterations = history.get("iteration") or history.get("step") or []
        iteration_count = max(len(iterations) - 1, 0) if isinstance(iterations, list) else 0
        summaries.append(
            {
                "stage": stage.get("stage"),
                "method_used": history.get("method_used", "unknown"),
                "converged": bool(history.get("converged", False)),
                "termination_reason": history.get("termination_reason"),
                "iteration_count": iteration_count,
                "iteration_limit": history.get("iteration_limit") or history.get("step_count"),
            }
        )
    return summaries


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
    method_convergence = summarize_method_convergence(staged_results)
    method_converged = all(item["converged"] for item in method_convergence) if method_convergence else False
    warnings = []
    if method_convergence and not method_converged:
        failed_stages = ", ".join(
            str(item["stage"]) for item in method_convergence if not item["converged"]
        )
        warnings.append(
            f"Hesaplama metodu tum kademelerde yakinsamadi; son tahmin kullanildi. Kademeler: {failed_stages}."
        )
    # Ağır C6+ / düşük verim seçilebilirlik kontrolü
    not_selectable_stages = [s for s in staged_results if not s.get("compressor_selectable", True)]
    overall_selectable = len(not_selectable_stages) == 0
    overall_scope = "NOT_SELECTABLE" if not overall_selectable else "IN_SCOPE"
    if not_selectable_stages:
        for st in not_selectable_stages:
            sw = "; ".join(st.get("selection_warnings", []))
            warnings.append(f"Kademe {st.get('stage')}: Kompresör seçilemez - {sw} (T_in artışı veya farklı akışkan önerilir)")
        warnings.append("Ağır C6+ hidrokarbonlarda düşük sıcaklık + yüksek PR kombinasyonu faz zarfına yakın - proses şartları gözden geçirilmeli")
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
        "method_convergence": method_convergence,
        "method_converged": method_converged,
        "calculation_method": method,
        "warnings": warnings,
        "compressor_selectable": overall_selectable,
        "analysis_scope": overall_scope,
        "not_selectable_stages": [s.get("stage") for s in not_selectable_stages],
        "fallback_used": False,
        "fallback_call_count": 0,
        "fallback_state_count": 0,
        "fallback_states": [],
        "fallback_stage_numbers": [],
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


def apply_fallback_tracking(results, fallback_tracking, staged_results, inlet_properties, outlet_properties):
    fallback_stage_numbers = [
        stage.get("stage")
        for stage in staged_results
        if stage.get("fallback_used", False)
    ]
    results["fallback_call_count"] = fallback_tracking.get("fallback_call_count", 0)
    results["fallback_state_count"] = fallback_tracking.get("fallback_state_count", 0)
    results["fallback_states"] = fallback_tracking.get("fallback_states", [])
    results["fallback_stage_numbers"] = fallback_stage_numbers
    results["fallback_used"] = bool(
        fallback_tracking.get("fallback_used", False)
        or fallback_stage_numbers
        or inlet_properties.get("fallback_used", False)
        or outlet_properties.get("fallback_used", False)
    )

    if results["fallback_used"]:
        warning_text = "Termodinamik kutuphane en az bir noktada fallback (ideal gaz) ile sonuc uretti."
        if results["fallback_stage_numbers"]:
            stage_text = ", ".join(str(stage) for stage in results["fallback_stage_numbers"])
            warning_text += f" Etkilenen kademeler: {stage_text}."
        if results["fallback_state_count"]:
            warning_text += f" Benzersiz fallback durum sayisi: {results['fallback_state_count']}."
        results.setdefault("warnings", []).append(warning_text)

    return results
