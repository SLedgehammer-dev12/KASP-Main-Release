"""Stage-by-stage orchestration for ThermoEngine design calculations."""

from __future__ import annotations

import math

from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.constants import R_UNIVERSAL_J_MOL_K
from kasp.core.thermo_design_support import build_stage_result
from kasp.core.fallback import EosChainBrokenError


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
        total_stage_gas_power_kw = 0.0
        total_poly_head_kj_kg = 0.0
        staged_results = []
        final_t_out_k = t_in_k

        for stage in range(1, num_stages + 1):
            # Stage basinda EOS lock-in'i sifirla (yeni stage, yeni EOS sansi)
            if eos_chain is not None:
                eos_chain.reset_lock()

            curr_p_out = curr_p_in * stage_pr
            if stage == num_stages:
                curr_p_out = p_out_pa

            from kasp.core.aerodynamics import set_current_stage
            set_current_stage(f"Kademe {stage}")

            self.logger.info(
                f">> KADEME {stage}: {curr_p_in/1e5:.2f} bar → {curr_p_out/1e5:.2f} bar"
            )

            # Method hesaplamasi — EosChainBrokenError veya Metot 4 hatasinda yeniden dene
            retries = 0
            while True:
                try:
                    if method_key in ("incremental", "huntington_rk45"):
                        t_out_k, poly_head, z_avg, history = method_callback(
                            curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, step_count
                        )
                    elif method_key == "direct_hs":
                        try:
                            t_out_k, poly_head, z_avg, history = method_callback(
                                curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos
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
                                gas_obj, eos, max_iter, tolerance
                            )
                            history["fallback_from_method"] = "direct_hs"
                            history["fallback_to_method"] = "average"
                            history["fallback_reason"] = str(exc)
                            break
                    else:
                        try:
                            t_out_k, poly_head, z_avg, history = method_callback(
                                curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, max_iter, tolerance
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

            state_in = self.thermo_solver.get_properties(curr_p_in, curr_t_in, gas_obj, eos)
            state_out = self.thermo_solver.get_properties(curr_p_out, t_out_k, gas_obj, eos)
            fallback_sources = []
            if state_in.raw_props.get("fallback", False):
                fallback_sources.append("stage_inlet")
            if state_out.raw_props.get("fallback", False):
                fallback_sources.append("stage_outlet")

            stage_delta_h_kj = (state_out.H - state_in.H) / 1000.0
            # Fiziksel kontrol: Δh pozitif olmalı (sıkıştırma ısıtır). Negatif/0 ise referans uyumsuzluğu -> polytropic head ile düzelt
            if stage_delta_h_kj <= 0 or not math.isfinite(stage_delta_h_kj):
                self.logger.warning(f"⚠️ Kademe {stage}: Δh={stage_delta_h_kj:.1f} kJ/kg non-fiziksel, head/η ile düzeltildi.")
                stage_delta_h_kj = poly_head / max(0.3, poly_eff_tgt) if poly_head > 0 else abs(stage_delta_h_kj)
            r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)

            # Schultz Düzeltme Katsayısı (ASME PTC 10) - direct_hs ve huntington_rk45 zaten gerçek Z/Δh integrali kullandığı için f_t=1.0
            if method_key in ("direct_hs", "huntington_rk45"):
                f_t = 1.0
            else:
                f_t = CompressorAerodynamics.calculate_schultz_factor(
                    state_in,
                    state_out,
                    curr_p_out,
                    self.thermo_solver,
                    gas_obj,
                    eos,
                    r_specific,
                )
            poly_head = f_t * poly_head

            # Gaz gücü: Termodinamik 1. Yasaya göre ṁ·Δh_actual
            stage_gas_power_kw = mass_flow_per_unit * stage_delta_h_kj
            # Tutarlılık metriği: polytropik head/η ile gerçek entalpi farkı arasındaki fark
            # eff düşük (<0.25) ise pcons beklenen büyük sapma - uyarı değil
            raw_pcons = mass_flow_per_unit * (poly_head / poly_eff_tgt - stage_delta_h_kj)
            # Eğer eff çok düşükse pcons'u 0'a baskıla (tasarım dışı çalışma)
            # Gerçek eff hesaplandıktan sonra düzeltilecek
            power_consistency_check_kw = raw_pcons
            actual_poly_eff = CompressorAerodynamics.calculate_polytropic_efficiency(
                state_in,
                state_out,
                r_specific,
                thermo_solver=self.thermo_solver,
                gas_obj=gas_obj,
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
                # pcons bu durumda anlamlı değil
                power_consistency_check_kw = 0.0
            if z_avg is not None and z_avg < 0.5:
                selection_warnings.append(f"Düşük Z {z_avg:.3f} (<0.5) - yoğuşma/ sıvı riski")
                analysis_scope = "NOT_SELECTABLE"
                compressor_selectable = False
            if z_avg is not None and z_avg > 1.8:
                selection_warnings.append(f"Yüksek Z {z_avg:.3f} (>1.8) - ideal gazdan çok sapma")
            # history'de phase_boundary_warning varsa selectable false yap
            if history.get("phase_boundary_warning") and history.get("deviation_pct", 0) > 30:
                selection_warnings.append(f"Faz zarfı sapması {history.get('deviation_pct'):.1f}% (>30%)")
                if history.get("deviation_pct", 0) > 50:
                    analysis_scope = "NOT_SELECTABLE"
                    compressor_selectable = False
            if selection_warnings:
                self.logger.warning(f"⚠️ Kademe {stage} seçim uyarısı: {'; '.join(selection_warnings)}")
                history["selection_warnings"] = selection_warnings
                history["analysis_scope"] = analysis_scope

            total_stage_gas_power_kw += stage_gas_power_kw
            total_poly_head_kj_kg += poly_head
            staged_results.append(
                build_stage_result(
                    stage=stage,
                    p_in=curr_p_in,
                    t_in=curr_t_in,
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
                )
            )

            final_t_out_k = t_out_k

            if stage < num_stages:
                curr_p_in = curr_p_out * (1.0 - intercooler_dp)
                curr_t_in = ic_t_k

        return {
            "final_t_out_k": final_t_out_k,
            "total_stage_gas_power_kw": total_stage_gas_power_kw,
            "total_poly_head_kj_kg": total_poly_head_kj_kg,
            "staged_results": staged_results,
        }
