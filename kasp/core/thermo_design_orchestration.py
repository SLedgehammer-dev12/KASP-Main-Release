"""Stage-by-stage orchestration for ThermoEngine design calculations."""

from __future__ import annotations

import math
import re

from kasp.core.aerodynamics import CompressorAerodynamics, is_calculation_cancel_requested
from kasp.core.constants import R_UNIVERSAL_J_MOL_K
from kasp.core.thermo_design_support import build_stage_result
from kasp.core.fallback import EosChainBrokenError
from kasp.core.exceptions import CalculationCancelled
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.vle import perform_vle_flash


def _extract_gas_composition(gas_comp, gas_obj):
    """Girdi veya gas_obj içinden bileşen yüzdeleri sözlüğünü çıkarır."""
    if gas_comp:
        return dict(gas_comp)
    if isinstance(gas_obj, dict):
        if "kept_components" in gas_obj and "mol_fractions" in gas_obj:
            return {
                c: float(f) * 100.0
                for c, f in zip(gas_obj["kept_components"], gas_obj["mol_fractions"])
            }
        tot = sum(float(v) for v in gas_obj.values() if float(v or 0.0) > 0) if gas_obj else 1.0
        mult = 100.0 if tot <= 1.5 else 1.0
        return {k: float(v) * mult for k, v in gas_obj.items()}
    if isinstance(gas_obj, str):
        parts = gas_obj.split("&")
        comp = {}
        for p in parts:
            m = re.match(r"^([^\[]+)(?:\[([0-9.]+)\])?$", p.strip())
            if m:
                name, frac = m.group(1), m.group(2)
                comp[name] = float(frac) * 100.0 if frac else 100.0
        if comp:
            return comp
    return {}


class ThermoDesignOrchestrator:
    def __init__(self, *, thermo_solver, logger):
        self.thermo_solver = thermo_solver
        self.logger = logger

    @staticmethod
    def _resolve_method_callback(
        method_key,
        *,
        method_average_fn,
        method_endpoint_fn,
        method_incremental_fn,
        method_direct_hs_fn,
        method_huntington_fn=None,
        method_schultz_3exp_fn=None,
    ):
        if method_key == "endpoint":
            return method_endpoint_fn
        if method_key == "incremental":
            return method_incremental_fn
        if method_key == "direct_hs":
            return method_direct_hs_fn
        if method_key == "huntington_rk45" and method_huntington_fn is not None:
            return method_huntington_fn
        if method_key == "schultz_3exp" and method_schultz_3exp_fn is not None:
            return method_schultz_3exp_fn
        return method_average_fn

    def run_stage_loop(
        self,
        *,
        p_in_pa,
        t_in_k,
        p_out_pa,
        stage_pr,
        num_stages,
        intercooler_dp,
        ic_t_k,
        method_key,
        poly_eff_tgt,
        gas_obj,
        eos,
        max_iter,
        tolerance,
        step_count,
        mass_flow_per_unit,
        eos_chain=None,
        method_average_fn,
        method_endpoint_fn,
        method_incremental_fn,
        method_direct_hs_fn,
        method_huntington_fn=None,
        method_schultz_3exp_fn=None,
        stage_ratios=None,
        gas_comp=None,
    ):
        # EosChain'i solver'a bagla — get_properties otomatik kullanir
        if eos_chain is not None:
            self.thermo_solver._active_eos_chain = eos_chain
        try:
            return self._run_stage_loop_inner(
                p_in_pa=p_in_pa,
                t_in_k=t_in_k,
                p_out_pa=p_out_pa,
                stage_pr=stage_pr,
                num_stages=num_stages,
                intercooler_dp=intercooler_dp,
                ic_t_k=ic_t_k,
                method_key=method_key,
                poly_eff_tgt=poly_eff_tgt,
                gas_obj=gas_obj,
                eos=eos,
                max_iter=max_iter,
                tolerance=tolerance,
                step_count=step_count,
                mass_flow_per_unit=mass_flow_per_unit,
                eos_chain=eos_chain,
                method_average_fn=method_average_fn,
                method_endpoint_fn=method_endpoint_fn,
                method_incremental_fn=method_incremental_fn,
                method_direct_hs_fn=method_direct_hs_fn,
                method_huntington_fn=method_huntington_fn,
                method_schultz_3exp_fn=method_schultz_3exp_fn,
                stage_ratios=stage_ratios,
                gas_comp=gas_comp,
            )
        finally:
            if eos_chain is not None:
                self.thermo_solver._active_eos_chain = None

    def _run_stage_loop_inner(
        self,
        *,
        p_in_pa,
        t_in_k,
        p_out_pa,
        stage_pr,
        num_stages,
        intercooler_dp,
        ic_t_k,
        method_key,
        poly_eff_tgt,
        gas_obj,
        eos,
        max_iter,
        tolerance,
        step_count,
        mass_flow_per_unit,
        eos_chain=None,
        method_average_fn,
        method_endpoint_fn,
        method_incremental_fn,
        method_direct_hs_fn,
        method_huntington_fn=None,
        method_schultz_3exp_fn=None,
        stage_ratios=None,
        gas_comp=None,
    ):
        method_callback = self._resolve_method_callback(
            method_key,
            method_average_fn=method_average_fn,
            method_endpoint_fn=method_endpoint_fn,
            method_incremental_fn=method_incremental_fn,
            method_direct_hs_fn=method_direct_hs_fn,
            method_huntington_fn=method_huntington_fn,
            method_schultz_3exp_fn=method_schultz_3exp_fn,
        )

        curr_p_in = p_in_pa
        curr_t_in = t_in_k
        curr_mass_flow = mass_flow_per_unit
        curr_gas_obj = gas_obj
        curr_gas_comp = _extract_gas_composition(gas_comp, gas_obj)
        total_stage_gas_power_kw = 0.0
        total_poly_head_kj_kg = 0.0
        total_liquid_knockout_kg_h = 0.0
        staged_results = []
        final_t_out_k = t_in_k
        any_invalid_stage = False

        for stage in range(1, num_stages + 1):
            if is_calculation_cancel_requested():
                raise CalculationCancelled("Kullanıcı hesaplamayı iptal etti.")
            # Stage basinda EOS lock-in'i sifirla (yeni stage, yeni EOS sansi)
            if eos_chain is not None:
                eos_chain.reset_lock()

            curr_pr = stage_ratios[stage - 1] if (stage_ratios and len(stage_ratios) >= stage) else stage_pr
            curr_p_out = curr_p_in * curr_pr
            if stage == num_stages:
                curr_p_out = p_out_pa

            from kasp.core.aerodynamics import set_current_stage
            set_current_stage(f"Kademe {stage}")

            self.logger.info(
                f">> KADEME {stage}: {curr_p_in/1e5:.2f} bar → {curr_p_out/1e5:.2f} bar"
            )

            stage_p_in = curr_p_in
            stage_t_in = curr_t_in
            stage_mass_flow = curr_mass_flow

            # Method hesaplamasi — EosChainBrokenError veya Metot 4 hatasinda yeniden dene
            retries = 0
            while True:
                if is_calculation_cancel_requested():
                    raise CalculationCancelled("Kullanıcı hesaplamayı iptal etti.")
                try:
                    if method_key in ("incremental", "huntington_rk45"):
                        t_out_k, poly_head, z_avg, history = method_callback(
                            curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, curr_gas_obj, eos, step_count
                        )
                    elif method_key == "direct_hs":
                        try:
                            t_out_k, poly_head, z_avg, history = method_callback(
                                curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, curr_gas_obj, eos
                            )
                            if not history.get("converged", True):
                                raise RuntimeError(
                                    f"Metot 4 yakınsamadı: {history.get('termination_reason', 'bilinmeyen')}"
                                )
                        except (RuntimeError, EosChainBrokenError) as exc:
                            if isinstance(exc, EosChainBrokenError) and retries < 2:
                                retries += 1
                                self.logger.warning(
                                    f"⚠ EosChain lock-in kirildi (stage {stage}): {exc}. Yeniden baslatiliyor... (deneme {retries})"
                                )
                                eos_chain.reset_lock()
                                continue
                            self.logger.warning(
                                f"⚠ Metot 4 basarisiz, Metot 1'e donuluyor: {exc}"
                            )
                            t_out_k, poly_head, z_avg, history = method_average_fn(
                                curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt,
                                curr_gas_obj, eos, max_iter, tolerance
                            )
                            history["fallback_from_method"] = "direct_hs"
                            history["fallback_to_method"] = "average"
                            history["fallback_reason"] = str(exc)
                            break
                    else:
                        try:
                            t_out_k, poly_head, z_avg, history = method_callback(
                                curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, curr_gas_obj, eos, max_iter, tolerance
                            )
                        except EosChainBrokenError:
                            raise
                        except RuntimeError as exc:
                            # CoolProp No density / stationary point hatası EosChain ile maskelenmiş olabilir
                            msg = str(exc)
                            if eos_chain is not None and retries < 2 and ("No density" in msg or "stationary" in msg.lower() or "Çıkış özellikleri" in msg):
                                raise EosChainBrokenError(msg) from exc
                            raise
                    break
                except EosChainBrokenError as exc:
                    retries += 1
                    if retries >= 2:
                        raise
                    self.logger.warning(
                        f"⚠ EosChain lock-in kirildi (stage {stage}): {exc}. Yeniden baslatiliyor... (deneme {retries})"
                    )
                    if eos_chain is not None:
                        eos_chain.reset_lock()
                    # Fallback EOS denensin diye bekle - bir sonraki iterasyonda zincir alternatif dener

            state_in = self.thermo_solver.get_properties(curr_p_in, curr_t_in, curr_gas_obj, eos)
            state_out = self.thermo_solver.get_properties(curr_p_out, t_out_k, curr_gas_obj, eos)
            fallback_sources = []
            if state_in.raw_props.get("fallback", False):
                fallback_sources.append("stage_inlet")
            if state_out.raw_props.get("fallback", False):
                fallback_sources.append("stage_outlet")

            r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)

            # Schultz Düzeltme Katsayısı (ASME PTC 10)
            # direct_hs, huntington_rk45, schultz_3exp ve incremental_pressure zaten gerçek gaz
            # integrali / türevleri (X, Y, n_v) kullandığı için f_t=1.0 uygulanır (çift düzeltme önlenir).
            if method_key in ("direct_hs", "huntington_rk45", "schultz_3exp", "incremental_pressure"):
                f_t = 1.0
            else:
                f_t = CompressorAerodynamics.calculate_schultz_factor(
                    state_in,
                    state_out,
                    curr_p_out,
                    self.thermo_solver,
                    curr_gas_obj,
                    eos,
                    r_specific,
                )
            poly_head = f_t * poly_head

            stage_delta_h_kj = (state_out.H - state_in.H) / 1000.0
            # Fiziksel kontrol: Δh pozitif olmalı (sıkıştırma ısıtır). Negatif/0 ise referans uyumsuzluğu.
            # Deger gizlice duzeltilmez; isaretlenir ve sonuc INVALID kabul edilir (mark-and-continue).
            energy_balance_ok = True
            invalid_stage_power = False
            delta_h_source = "enthalpy"
            if stage_delta_h_kj <= 0 or not math.isfinite(stage_delta_h_kj):
                energy_balance_ok = False
                invalid_stage_power = True
                delta_h_source = "invalid_zeroed"
                self.logger.warning(
                    f"⚠️ Kademe {stage}: Δh={stage_delta_h_kj:.1f} kJ/kg non-fiziksel, "
                    f"0.0 olarak sınırlandırıldı (sonuc INVALID isaretlendi)."
                )
                stage_delta_h_kj = 0.0

            # Gaz gücü: Termodinamik 1. Yasaya göre ṁ·Δh_actual (mevcut kademe debisi ile)
            stage_gas_power_kw = stage_mass_flow * stage_delta_h_kj if energy_balance_ok else 0.0
            # Tutarlılık metriği: polytropik head/η ile gerçek entalpi farkı arasındaki fark
            raw_pcons = (
                stage_mass_flow * (poly_head / poly_eff_tgt - stage_delta_h_kj)
                if energy_balance_ok
                else 0.0
            )
            power_consistency_check_kw = raw_pcons
            actual_poly_eff = CompressorAerodynamics.calculate_polytropic_efficiency(
                state_in,
                state_out,
                r_specific,
                thermo_solver=self.thermo_solver,
                gas_obj=curr_gas_obj,
                eos=eos,
            )
            # Ağır C6+ / düşük verim / düşük Z için seçilebilirlik kontrolü
            selection_warnings = []
            analysis_scope = "IN_SCOPE"
            compressor_selectable = True
            if actual_poly_eff < 0.25:
                selection_warnings.append(f"Düşük politropik verim {actual_poly_eff:.2f} (<0.25) - faz zarfına yakın, T_in artışı önerilir")
                analysis_scope = "NOT_SELECTABLE"
                compressor_selectable = False
                power_consistency_check_kw = 0.0
            if z_avg is not None and z_avg < 0.5:
                selection_warnings.append(f"Düşük Z {z_avg:.3f} (<0.5) - yoğuşma/ sıvı riski")
                analysis_scope = "NOT_SELECTABLE"
                compressor_selectable = False
            if z_avg is not None and z_avg > 1.8:
                selection_warnings.append(f"Yüksek Z {z_avg:.3f} (>1.8) - ideal gazdan çok sapma")
            if history.get("phase_boundary_warning") and history.get("deviation_pct", 0) > 30:
                selection_warnings.append(f"Faz zarfı sapması {history.get('deviation_pct'):.1f}% (>30%)")
                if history.get("deviation_pct", 0) > 50:
                    analysis_scope = "NOT_SELECTABLE"
                    compressor_selectable = False
            if not energy_balance_ok:
                selection_warnings.append(
                    f"Non-fiziksel enerji dengesi (Δh<=0); Δh '{delta_h_source}' ile sıfırlandı"
                )
                analysis_scope = "INVALID"
                compressor_selectable = False
            if selection_warnings:
                self.logger.warning(f"⚠️ Kademe {stage} seçim uyarısı: {'; '.join(selection_warnings)}")
                history["selection_warnings"] = selection_warnings
                history["analysis_scope"] = analysis_scope

            total_stage_gas_power_kw += stage_gas_power_kw
            if energy_balance_ok:
                total_poly_head_kj_kg += poly_head
            else:
                any_invalid_stage = True

            # INVALID kademede çıkış sıcaklığı fiziksel-dışı olabilir; ilerletme.
            if energy_balance_ok:
                final_t_out_k = t_out_k

            stage_liquid_knockout = 0.0
            if stage < num_stages:
                curr_p_in = curr_p_out * (1.0 - intercooler_dp)
                # Ara-soğutucu gerçekten soğutmalı: ic_t < deşarj sıcaklığı olmalı.
                # Aksi halde gizlice ısıtıcı gibi davranır — uyar.
                if ic_t_k >= t_out_k:
                    self.logger.warning(
                        f"⚠️ Kademe {stage}: Ara-soğutucu sıcaklığı ({ic_t_k-273.15:.1f}°C) "
                        f"deşarj sıcaklığından ({t_out_k-273.15:.1f}°C) yüksek — ısıtıcı gibi davranıyor."
                    )
                curr_t_in = ic_t_k

                # VLE Flash & Liquid Knockout Drum
                if curr_gas_comp:
                    try:
                        vle_res = perform_vle_flash(curr_p_in, curr_t_in, curr_gas_comp, curr_mass_flow)
                        if vle_res.get("is_two_phase") and vle_res.get("liquid_knockout_kg_h", 0.0) > 0.001:
                            stage_liquid_knockout = vle_res["liquid_knockout_kg_h"]
                            total_liquid_knockout_kg_h += stage_liquid_knockout
                            curr_mass_flow = vle_res["vapor_mass_flow_kgs"]
                            curr_gas_comp = vle_res["vapor_composition"]
                            # Sonraki kademeler icin curr_gas_obj'yi yeni gaz kompozisyonu ile guncelle
                            if eos == "coolprop":
                                curr_gas_obj = GasMixtureBuilder.build_coolprop_string(curr_gas_comp)
                            elif eos == "neqsim":
                                curr_gas_obj = GasMixtureBuilder.build_neqsim_input(curr_gas_comp)
                            else:
                                curr_gas_obj = GasMixtureBuilder.build_thermo_data(curr_gas_comp)

                            if eos_chain is not None:
                                eos_chain._raw_composition = curr_gas_comp
                                eos_chain._gas_obj_cache.clear()

                            self.logger.info(
                                f"💧 Kademe {stage} sonrasi ara-sogutucuda {stage_liquid_knockout:.2f} kg/h sivi ayristirildi "
                                f"(Knockout Drum). Sonraki kademe kutle debisi: {curr_mass_flow:.4f} kg/s."
                            )
                    except Exception as exc:
                        self.logger.warning(f"Ara-soğutucu VLE flash hesaplama hatası: {exc}")

            staged_results.append(
                build_stage_result(
                    stage=stage,
                    p_in=stage_p_in,
                    t_in=stage_t_in,
                    p_out=curr_p_out,
                    t_out=t_out_k,
                    head_kj_kg=poly_head,
                    poly_eff_design=poly_eff_tgt,
                    poly_eff_diagnostic=actual_poly_eff,
                    power_gas_kw=stage_gas_power_kw,
                    delta_h_kj_kg=stage_delta_h_kj,
                    power_consistency_check_kw=power_consistency_check_kw,
                    z_avg=z_avg,
                    method_history=history,
                    fallback_used=bool(fallback_sources),
                    fallback_sources=fallback_sources,
                    compressor_selectable=compressor_selectable,
                    selection_warnings=selection_warnings,
                    analysis_scope=analysis_scope,
                    energy_balance_ok=energy_balance_ok,
                    delta_h_source=delta_h_source,
                    invalid_stage_power=invalid_stage_power,
                    liquid_knockout_kg_h=stage_liquid_knockout,
                    mass_flow_kgs=stage_mass_flow,
                )
            )

        return {
            "final_t_out_k": final_t_out_k,
            "total_stage_gas_power_kw": total_stage_gas_power_kw,
            "total_poly_head_kj_kg": total_poly_head_kj_kg,
            "total_liquid_knockout_kg_h": total_liquid_knockout_kg_h,
            "any_invalid_stage": any_invalid_stage,
            "staged_results": staged_results,
        }
