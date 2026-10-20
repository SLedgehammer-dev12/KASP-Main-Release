"""Support helpers for ThermoEngine design-performance calculations."""

from __future__ import annotations

import math

from kasp.core.constants import API_617_DRIVER_MARGIN_PCT


ENGINE_VERSION = "1.3.0 (V4.5 — 6-Method Engine)"


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        val = float(value)
        return val if math.isfinite(val) else default
    except (TypeError, ValueError):
        return default


def compute_stage_pressure_ratio(total_pressure_ratio, intercooler_dp, num_stages):
    try:
        pr = float(total_pressure_ratio)
        dp = float(intercooler_dp or 0.0)
        n = int(num_stages)
    except (TypeError, ValueError):
        return 1.0

    if n <= 1:
        return max(1.0, pr) if math.isfinite(pr) else 1.0

    if not math.isfinite(pr) or pr <= 0.0:
        return 1.0

    # Auto-convert percentage input (e.g. 2.0% -> 0.02)
    if dp > 1.0:
        dp = dp / 100.0

    # Clamp dp safely to [0.0, 0.50] to avoid non-physical pressure drop or division by zero
    dp = max(0.0, min(0.50, dp if math.isfinite(dp) else 0.0))
    denom = (1.0 - dp) ** (n - 1)
    if denom <= 0.0:
        return 1.0
    return (pr / denom) ** (1.0 / n)


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
    try:
        p_in = float(p_in_pa)
        p_out = float(p_out_pa)
        n_stages = int(num_stages)
    except (TypeError, ValueError):
        return []

    if n_stages <= 0:
        return []

    if not math.isfinite(p_in) or p_in <= 0.0 or not math.isfinite(p_out) or p_out <= 0.0:
        return [1.0] * n_stages

    total_pr = max(1.0, p_out / p_in)
    if n_stages <= 1:
        return [total_pr]

    dp = float(intercooler_dp or 0.0)
    if dp > 1.0:
        dp = dp / 100.0
    dp = max(0.0, min(0.50, dp if math.isfinite(dp) else 0.0))

    r_uniform = compute_stage_pressure_ratio(total_pr, dp, n_stages)

    t_in = _coerce_float(t_in_k, 293.15)
    t_in = max(100.0, min(2000.0, t_in))
    ic_t = _coerce_float(ic_t_k, 293.15)
    ic_t = max(100.0, min(2000.0, ic_t))

    if abs(t_in - ic_t) < 1.0:
        return [r_uniform] * n_stages

    # Equal Work optimization when inlet temperatures differ (ambient vs intercooler)
    k = _coerce_float(k_isen, 1.3)
    m = (k - 1.0) / k if k > 1.05 else 0.25

    def eval_p_out(r1):
        w1_factor = (r1 ** m - 1.0)
        p_curr = p_in
        for s in range(n_stages):
            t_s = t_in if s == 0 else ic_t
            r_s = max(1.001, (1.0 + (t_in / t_s) * w1_factor) ** (1.0 / m)) if s > 0 else r1
            p_out_s = p_curr * r_s
            if s < n_stages - 1:
                p_curr = p_out_s * (1.0 - dp)
            else:
                p_curr = p_out_s
        return p_curr - p_out

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
    for s in range(n_stages):
        t_s = t_in if s == 0 else ic_t
        r_s = max(1.001, (1.0 + (t_in / t_s) * w1_factor) ** (1.0 / m)) if s > 0 else r1_opt
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
    energy_balance_ok=True,
    delta_h_source="enthalpy",
    invalid_stage_power=False,
    liquid_knockout_kg_h=0.0,
    mass_flow_kgs=None,
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
        "delta_h_source": delta_h_source,
        "energy_balance_ok": bool(energy_balance_ok),
        "invalid_stage_power": bool(invalid_stage_power),
        "liquid_knockout_kg_h": float(liquid_knockout_kg_h or 0.0),
        "mass_flow_kgs": float(mass_flow_kgs) if mass_flow_kgs is not None else None,
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
    total_actual_delta_h_kj_kg = sum(
        _coerce_float(stage.get("delta_h_kj_kg"), 0.0)
        for stage in (staged_results or [])
        if isinstance(stage, dict)
    )
    head = _coerce_float(total_poly_head_kj_kg, 0.0)
    if total_actual_delta_h_kj_kg > 0:
        return max(0.0, min(1.0, head / total_actual_delta_h_kj_kg))
    last_stage = staged_results[-1] if (staged_results and isinstance(staged_results[-1], dict)) else {}
    raw_eff = _coerce_float(last_stage.get("poly_eff_diagnostic", poly_eff_tgt), 0.75)
    if raw_eff > 1.0:
        raw_eff = raw_eff / 100.0
    return max(0.0, min(1.0, raw_eff))


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
    # Enerji dengesi bozuk kademeler sonucu gecersiz sayar (INVALID, NOT_SELECTABLE'dan ustun)
    invalid_stages = [s for s in staged_results if not s.get("energy_balance_ok", True)]
    energy_balance_ok = len(invalid_stages) == 0
    if invalid_stages:
        overall_scope = "INVALID"
        overall_selectable = False
    elif not_selectable_stages:
        overall_scope = "NOT_SELECTABLE"
    else:
        overall_scope = "IN_SCOPE"
    for st in invalid_stages:
        warnings.append(
            f"Kademe {st.get('stage')}: Non-fiziksel enerji dengesi (delta_h<=0); "
            f"delta_h '{st.get('delta_h_source', 'bilinmiyor')}' ile sifirlandi, head/guc toplamina "
            f"KATILMADI. Sonuc gecersiz sayilmalidir."
        )
    if not_selectable_stages:
        for st in not_selectable_stages:
            sw = "; ".join(st.get("selection_warnings", []))
            warnings.append(f"Kademe {st.get('stage')}: Kompresör seçilemez - {sw} (T_in artışı veya farklı akışkan önerilir)")
        warnings.append("Ağır C6+ hidrokarbonlarda düşük sıcaklık + yüksek PR kombinasyonu faz zarfına yakın - proses şartları gözden geçirilmeli")
    total_knockout = sum(float(s.get("liquid_knockout_kg_h", 0.0) or 0.0) for s in staged_results)
    if total_knockout > 0.01:
        warnings.append(
            f"Ara soğutucularda toplam {total_knockout:.2f} kg/h sıvı ayrıştırıldı (Knockout Drum aktif)."
        )
    return {
        "t_out": final_t_out_k - 273.15,
        "head_kj_kg": total_poly_head_kj_kg,
        "compression_ratio": (p_out_pa / p_in_pa) if (p_in_pa and p_in_pa > 0) else 1.0,
        "design_poly_efficiency": poly_eff_tgt,
        "actual_poly_efficiency": actual_poly_eff_total,
        "liquid_knockout_total_kg_h": round(total_knockout, 2),
        "power_gas_per_unit_kw": total_stage_gas_power_kw,
        "power_shaft_per_unit_kw": total_shaft_kw,
        "power_motor_per_unit_kw": motor_kw,
        "power_unit_kw": unit_kw,
        "api_617_margin_percent": API_617_DRIVER_MARGIN_PCT,
        "mech_loss_per_unit_kw": mech_loss_kw,
        "fuel_unit_kgh": fuel_kgh,
        "mass_flow_per_unit_kgs": mass_flow_per_unit,
        "inlet_vol_flow_acmh_per_unit": inlet_acmh,
        "power_gas_total_kw": total_stage_gas_power_kw * num_units,
        "power_shaft_total_kw": total_shaft_kw * num_units,
        "power_motor_total_kw": motor_kw * num_units,
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
        "energy_balance_ok": energy_balance_ok,
        "not_selectable_stages": [s.get("stage") for s in not_selectable_stages],
        "fallback_used": False,
        "fallback_call_count": 0,
        "fallback_state_count": 0,
        "fallback_states": [],
        "fallback_stage_numbers": [],
        "engine_version": ENGINE_VERSION,
    }


def build_uncertainty_measurements(inputs):
    inp = inputs if isinstance(inputs, dict) else {}
    return {
        "p_in": _coerce_float(inp.get("p_in"), 101325.0),
        "p_out": _coerce_float(inp.get("p_out"), 300000.0),
        "t_in": _coerce_float(inp.get("t_in"), 300.0),
        "flow": _coerce_float(inp.get("flow"), 10.0),
    }


def build_uncertainty_payload(uncertainty_result, actual_poly_efficiency):
    compliant = bool(uncertainty_result.get("fully_compliant", False))
    reasons = []
    failures = uncertainty_result.get("sensitivity_failures") or []
    if failures:
        reasons.append(
            "Duyarlilik hesaplanamayan olcumler: " + ", ".join(str(p) for p in failures)
        )
    fs = uncertainty_result.get("full_scale_assumptions") or []
    if fs:
        reasons.append(
            "Tam olcek (FS) bilinmeden okuma bazli varsayilan basinc olcumleri: "
            + ", ".join(str(p) for p in fs)
        )
    if not uncertainty_result.get("model_uncertainty_included", False):
        reasons.append("Model belirsizligi bu analize dahil edilmemistir.")
    return {
        "polytropic_efficiency": {
            "value": actual_poly_efficiency,
            "combined_uncertainty": uncertainty_result["combined_uncertainty"],
            "expanded_uncertainty": uncertainty_result["expanded_uncertainty"],
            "confidence_level": "95%",
            "breakdown": uncertainty_result["breakdown_percent"],
        },
        "asme_ptc10_compliant": compliant,
        "compliance_reasons": reasons,
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
        warning_text = "Termodinamik kutuphane en az bir noktada fallback/ideal yaklasim ile sonuc uretti; gercek EOS kullanilmamis olabilir."
        if results["fallback_stage_numbers"]:
            stage_text = ", ".join(str(stage) for stage in results["fallback_stage_numbers"])
            warning_text += f" Etkilenen kademeler: {stage_text}."
        if results["fallback_state_count"]:
            warning_text += f" Benzersiz fallback durum sayisi: {results['fallback_state_count']}."
        results.setdefault("warnings", []).append(warning_text)

    nonconverged = fallback_tracking.get("solver_nonconverged") or {}
    if nonconverged:
        results["solver_nonconverged"] = dict(nonconverged)
        details = ", ".join(f"{k} (artık={v:.2f} J/kg·K)" for k, v in nonconverged.items())
        results.setdefault("warnings", []).append(
            f"İzentropik kök çözücü tolerans içinde yakınsamadı: {details}."
        )

    return results
