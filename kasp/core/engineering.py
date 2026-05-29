"""Engineering modu için EOS ve Metot karşılaştırma (shootout) araçları."""

import time
import logging

logger = logging.getLogger(__name__)

ALL_EOS_METHODS = ["coolprop", "thermopack", "pr", "srk", "aga8", "ccp", "dwsim"]
ALL_EOS_LABELS = {
    "coolprop": "CoolProp (HEOS)",
    "thermopack": "SINTEF thermopack",
    "pr": "Peng-Robinson",
    "srk": "SRK",
    "aga8": "AGA8-DC92",
    "ccp": "Petrobras ccp",
    "dwsim": "DWSIM",
}
METHOD_NAMES = {
    "Metot 1: Ortalama Özellikler": "Ortalama Özellikler",
    "Metot 2: Uç Nokta": "Uç Nokta",
    "Metot 3: Artımlı Basınç": "Artımlı Entegrasyon",
    "Metot 4: Doğrudan H-S": "Direct H-S (Mollier)",
}
ALL_METHOD_LABELS = [
    "Metot 1: Ortalama Özellikler",
    "Metot 2: Uç Nokta",
    "Metot 3: Artımlı Basınç",
    "Metot 4: Doğrudan H-S",
]


def _extract_raw_properties(output: dict) -> dict:
    """Hesaplama sonuclarindan ham property degerlerini cikarir."""
    props = {}
    for point, key in [("inlet", "inlet_properties"), ("outlet", "outlet_properties")]:
        data = output.get(key, {}) or {}
        props[f"{point}_mw"] = data.get("M_kg_mol", 0) * 1000.0 if data.get("M_kg_mol") else None
        props[f"{point}_k"] = data.get("k")
        props[f"{point}_z"] = data.get("Z")
        props[f"{point}_cp"] = data.get("Cp")
        props[f"{point}_cv"] = data.get("Cv")
        props[f"{point}_density"] = data.get("rho")
        props[f"{point}_phase"] = data.get("phase")
    props["mass_flow_kgs"] = output.get("mass_flow_total_kgs")
    props["fallback_used"] = output.get("fallback_used", False)
    return props


def run_eos_shootout(engine, base_inputs: dict) -> list[dict]:
    """Tüm EOS motorlarını aynı girdilerle çalıştırır, sonuçları karşılaştırır."""
    results = []
    reference = None
    for eos in ALL_EOS_METHODS:
        inputs = dict(base_inputs)
        inputs["eos_method"] = eos
        t0 = time.perf_counter()
        try:
            output = engine.calculate_design_performance(inputs)
            elapsed = time.perf_counter() - t0
            raw = _extract_raw_properties(output)
            results.append({
                "eos": eos,
                "label": ALL_EOS_LABELS.get(eos, eos),
                "success": True,
                "t_out": output.get("t_out", None),
                "head_kj_kg": output.get("head_kj_kg", None),
                "poly_eff_actual": output.get("actual_poly_efficiency", None),
                "power_kw": output.get("power_gas_total_kw", None),
                "z_avg": output.get("z_avg", None),
                "elapsed_s": elapsed,
                "fallback_used": output.get("fallback_used", None),
                "raw_props": raw,
                "error": None,
            })
            if eos == "coolprop" and reference is None:
                reference = output
        except Exception as e:
            results.append({
                "eos": eos,
                "label": ALL_EOS_LABELS.get(eos, eos),
                "success": False,
                "error": str(e),
            })

    # Referansa göre sapma hesapla
    if reference:
        ref_head = reference.get("head_kj_kg", 0)
        ref_power = reference.get("power_gas_total_kw", 0)
        for r in results:
            if not r["success"] or r["head_kj_kg"] is None or ref_head == 0:
                continue
            r["head_diff_pct"] = (r["head_kj_kg"] - ref_head) / ref_head * 100
            r["power_diff_pct"] = (r["power_kw"] - ref_power) / ref_power * 100 if ref_power else 0

    return results


def run_method_shootout(engine, base_inputs: dict) -> list[dict]:
    """Tüm sıkıştırma metotlarını aynı girdilerle çalıştırır."""
    results = []
    for method in ALL_METHOD_LABELS:
        inputs = dict(base_inputs)
        inputs["method"] = method
        t0 = time.perf_counter()
        try:
            output = engine.calculate_design_performance(inputs)
            elapsed = time.perf_counter() - t0
            results.append({
                "method": method,
                "label": METHOD_NAMES.get(method, method),
                "success": True,
                "t_out": output.get("t_out", None),
                "head_kj_kg": output.get("head_kj_kg", None),
                "poly_eff_actual": output.get("actual_poly_efficiency", None),
                "power_kw": output.get("power_gas_total_kw", None),
                "convergence": output.get("method_converged", None),
                "elapsed_s": elapsed,
                "error": None,
            })
        except Exception as e:
            results.append({
                "method": method,
                "label": METHOD_NAMES.get(method, method),
                "success": False,
                "error": str(e),
            })
    return results
