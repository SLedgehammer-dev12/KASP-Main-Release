"""Stage-by-stage orchestration for ThermoEngine design calculations."""

from __future__ import annotations

from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.constants import R_UNIVERSAL_J_MOL_K
from kasp.core.thermo_design_support import build_stage_result


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
    ):
        if method_key == "endpoint":
            return method_endpoint_fn
        if method_key == "incremental":
            return method_incremental_fn
        if method_key == "direct_hs":
            return method_direct_hs_fn
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
        method_average_fn,
        method_endpoint_fn,
        method_incremental_fn,
        method_direct_hs_fn,
    ):
        method_callback = self._resolve_method_callback(
            method_key,
            method_average_fn=method_average_fn,
            method_endpoint_fn=method_endpoint_fn,
            method_incremental_fn=method_incremental_fn,
            method_direct_hs_fn=method_direct_hs_fn,
        )

        curr_p_in = p_in_pa
        curr_t_in = t_in_k
        total_stage_gas_power_kw = 0.0
        total_poly_head_kj_kg = 0.0
        staged_results = []
        final_t_out_k = t_in_k

        for stage in range(1, num_stages + 1):
            curr_p_out = curr_p_in * stage_pr
            if stage == num_stages:
                curr_p_out = p_out_pa

            self.logger.info(
                f">> KADEME {stage}: {curr_p_in/1e5:.2f} bar → {curr_p_out/1e5:.2f} bar"
            )

            if method_key == "incremental":
                t_out_k, poly_head, z_avg, history = method_callback(
                    curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, step_count
                )
            elif method_key == "direct_hs":
                t_out_k, poly_head, z_avg, history = method_callback(
                    curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos
                )
            else:
                t_out_k, poly_head, z_avg, history = method_callback(
                    curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, max_iter, tolerance
                )

            state_in = self.thermo_solver.get_properties(curr_p_in, curr_t_in, gas_obj, eos)
            state_out = self.thermo_solver.get_properties(curr_p_out, t_out_k, gas_obj, eos)

            stage_gas_power_kw = mass_flow_per_unit * (poly_head / poly_eff_tgt)
            stage_delta_h_kj = (state_out.H - state_in.H) / 1000.0
            r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
            actual_poly_eff = CompressorAerodynamics.calculate_polytropic_efficiency(
                state_in,
                state_out,
                r_specific,
            )

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
                    z_avg=z_avg,
                    method_history=history,
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
