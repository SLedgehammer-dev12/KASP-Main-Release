"""Calculation method strategies used by ThermoEngine."""

from __future__ import annotations

import math

import numpy as np

from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.settings import EngineSettings
from kasp.core.constants import R_UNIVERSAL_J_MOL_K
from kasp.core.thermo_support import isentropic_exponent


class ThermoMethodSuite:
    MAX_METHOD_ITERATIONS = 200
    MAX_INCREMENTAL_STEPS = 500

    def __init__(self, *, thermo_solver, logger):
        self.thermo_solver = thermo_solver
        self.logger = logger

    def _coerce_iteration_limit(self, value, *, default=100):
        try:
            limit = int(value)
        except (TypeError, ValueError):
            limit = default
        return max(1, min(self.MAX_METHOD_ITERATIONS, limit))

    @staticmethod
    def _coerce_tolerance(value, *, default=0.01):
        try:
            tolerance = float(value)
        except (TypeError, ValueError):
            tolerance = default
        return max(1e-6, tolerance)

    def _coerce_step_count(self, value, *, default=10):
        try:
            step_count = int(value)
        except (TypeError, ValueError):
            step_count = default
        return max(2, min(self.MAX_INCREMENTAL_STEPS, step_count))

    @staticmethod
    def _coerce_pressures(p_in, p_out) -> tuple[float, float]:
        try:
            pi = float(p_in)
            po = float(p_out)
        except (TypeError, ValueError):
            raise ValueError(f"Geçersiz basınç girdisi (p_in={p_in}, p_out={p_out}).")
        if not math.isfinite(pi) or pi <= 0.0 or not math.isfinite(po) or po <= 0.0:
            raise ValueError(f"Giriş ve çıkış basınçları pozitif olmalıdır (p_in={p_in}, p_out={p_out}).")
        return pi, po

    @staticmethod
    def _coerce_poly_eff(value, *, default=0.75, min_eff=0.10, max_eff=0.999) -> float:
        """
        Politropik verimi standart fraksiyon (0.0 < eff < 1.0) aralığına normalize eder.
        Eğer değer 1.0'dan büyük ve <= 100.0 ise (yüzde formatı), 100'e bölünür.
        Sıfır, negatif veya geçersiz (NaN/None/inf) değerler güvenli fiziksel aralığa kelepçelenir.
        """
        try:
            val = float(value)
            if not math.isfinite(val):
                return default
        except (TypeError, ValueError):
            return default

        if 1.0 < val <= 100.0:
            val = val / 100.0

        return max(min_eff, min(max_eff, val))

    @staticmethod
    def _calculate_polytropic_head(z_factor, r_specific, t_in, pressure_ratio, exponent):
        if abs(exponent) < 1e-10:
            return 0.0
        return (
            z_factor
            * r_specific
            * t_in
            * (1.0 / exponent)
            * (math.pow(pressure_ratio, exponent) - 1.0)
        ) / 1000.0

    def method_average_properties(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        p_in, p_out = self._coerce_pressures(p_in, p_out)
        max_iter = self._coerce_iteration_limit(max_iter)
        tolerance = self._coerce_tolerance(tolerance)
        poly_eff = self._coerce_poly_eff(poly_eff)

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            m1, _, k1 = CompressorAerodynamics.real_gas_temperature_exponents(state_in, poly_eff)
            Z1 = state_in.Z
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 1): {error}")

        if abs(p_out - p_in) < 1.0:
            return t_in, 0.0, Z1, {
                "pressure": [p_in],
                "temperature": [t_in],
                "z_factor": [Z1],
                "k_value": [k1],
                "iteration": [0],
                "method_used": "averaging",
                "iteration_limit": max_iter,
                "tolerance": tolerance,
                "converged": True,
                "termination_reason": "zero_dp",
            }

        pr = p_out / p_in
        use_integral = pr > EngineSettings.PR_INTEGRATION_THRESHOLD

        if use_integral:
            self.logger.info(
                f"📊 API 617 Appendix C — İntegral metodu: PR={pr:.2f} > {EngineSettings.PR_INTEGRATION_THRESHOLD}"
            )

        n_init = m1
        t2_guess = t_in * (p_out / p_in) ** n_init
        if t2_guess <= 0 or t2_guess > t_in * 10:
            t2_guess = t_in * 1.5

        history = {
            "pressure": [p_in],
            "temperature": [t_in],
            "z_factor": [Z1],
            "k_value": [k1],
            "iteration": [0],
            "method_used": "integral" if use_integral else "averaging",
            "iteration_limit": max_iter,
            "tolerance": tolerance,
            "converged": False,
            "termination_reason": None,
        }
        integral_analysis = None
        use_integral_local = use_integral

        for iteration in range(max_iter):
            t2_old = t2_guess

            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_old, gas_obj, eos)
                m2, _, k2 = CompressorAerodynamics.real_gas_temperature_exponents(state_out, poly_eff)
                Z2 = state_out.Z
            except Exception as error:
                raise RuntimeError(f"Çıkış özellikleri hesaplanamadı (Metot 1, iter {iteration}): {error}")

            if use_integral_local:
                try:
                    n_minus_1_over_n, k_integral, integral_analysis = (
                        CompressorAerodynamics.calculate_polytropic_exponent_integral(
                            p_in, t_in, p_out, poly_eff, self.thermo_solver, gas_obj, eos, steps=20
                        )
                    )
                    k_avg = k_integral
                    history["k_integral"] = k_integral
                    history["integral_analysis"] = integral_analysis
                except Exception as error:
                    self.logger.warning(f"⚠ İntegral metot başarısız, ortalamaya dönülüyor: {error}")
                    k_avg = (k1 + k2) / 2.0
                    n_minus_1_over_n = (m1 + m2) / 2.0
                    use_integral_local = False
                    history["method_used"] = "averaging_fallback"
            else:
                k_avg = (k1 + k2) / 2.0
                n_minus_1_over_n = (m1 + m2) / 2.0

            z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)

            if abs(n_minus_1_over_n) < 1e-10:
                self.logger.warning("Metot 1: n_minus_1_over_n sıfıra çok yakın, döngü sonlandırıldı.")
                break

            t2_new = t_in * (p_out / p_in) ** n_minus_1_over_n
            t2_guess = t2_old + 0.5 * (t2_new - t2_old)

            history["pressure"].append(p_out)
            history["temperature"].append(t2_guess)
            history["z_factor"].append(z_avg)
            history["k_value"].append(k_avg)
            history["iteration"].append(iteration + 1)

            if abs(t2_guess - t2_old) < tolerance:
                try:
                    state_out_conv = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                except Exception:
                    state_out_conv = state_out
                try:
                    state_avg = self.thermo_solver.get_properties(
                        (p_in + p_out) / 2, (t_in + t2_guess) / 2, gas_obj, eos
                    )
                    z_avg = state_avg.Z
                    mw = state_avg.MW
                except Exception:
                    mw = state_in.MW

                r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
                v1 = CompressorAerodynamics._specific_volume_m3_kg(state_in, r_specific)
                v2 = CompressorAerodynamics._specific_volume_m3_kg(state_out_conv, r_specific)
                w_uncorr = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1, p_out, v2)
                if w_uncorr > 0.0 and math.isfinite(w_uncorr):
                    poly_head = w_uncorr / 1000.0
                else:
                    poly_head = self._calculate_polytropic_head(
                        z_avg, r_specific, t_in, p_out / p_in, n_minus_1_over_n
                    )

                self.logger.debug(f"✓ Metot 1 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                history["converged"] = True
                history["termination_reason"] = "converged"
                return t2_guess, poly_head, z_avg, history

        self.logger.warning(f"⚠ Metot 1: Maks. iterasyon ({max_iter}) aşıldı, son tahmin kullanılıyor.")
        try:
            state_avg = self.thermo_solver.get_properties((p_in + p_out) / 2, (t_in + t2_guess) / 2, gas_obj, eos)
            z_avg_final = state_avg.Z
            n_final, _, _ = CompressorAerodynamics.real_gas_temperature_exponents(state_avg, poly_eff)
            mw = state_avg.MW
        except Exception:
            z_avg_final = Z1
            n_final = m1
            mw = state_in.MW

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
        try:
            state_out_fb = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
            v1 = CompressorAerodynamics._specific_volume_m3_kg(state_in, r_specific)
            v2 = CompressorAerodynamics._specific_volume_m3_kg(state_out_fb, r_specific)
            poly_head = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1, p_out, v2) / 1000.0
        except Exception:
            poly_head = self._calculate_polytropic_head(
                z_avg_final,
                r_specific,
                t_in,
                p_out / p_in,
                n_final,
            )
        history["termination_reason"] = history["termination_reason"] or "max_iterations"
        return t2_guess, poly_head, z_avg_final, history

    def method_endpoint(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        p_in, p_out = self._coerce_pressures(p_in, p_out)
        max_iter = self._coerce_iteration_limit(max_iter)
        tolerance = self._coerce_tolerance(tolerance)
        poly_eff = self._coerce_poly_eff(poly_eff)
        poly_eff_clamped = max(0.3, min(0.99, float(poly_eff) if math.isfinite(poly_eff) else 0.75))
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            m1, _, k1 = CompressorAerodynamics.real_gas_temperature_exponents(state_in, poly_eff_clamped)
            Z1 = state_in.Z
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 2): {error}")

        if abs(p_out - p_in) < 1.0:
            return t_in, 0.0, Z1, {
                "pressure": [p_in],
                "temperature": [t_in],
                "z_factor": [Z1],
                "k_value": [k1],
                "iteration": [0],
                "method_used": "endpoint",
                "iteration_limit": max_iter,
                "tolerance": tolerance,
                "converged": True,
                "termination_reason": "zero_dp",
            }

        n_init = max(0.02, min(0.45, m1))
        t2_guess = t_in * (p_out / p_in) ** n_init
        if t2_guess <= 0:
            t2_guess = t_in * 1.1

        history = {
            "pressure": [p_in],
            "temperature": [t_in],
            "z_factor": [Z1],
            "k_value": [k1],
            "iteration": [0],
            "method_used": "endpoint",
            "iteration_limit": max_iter,
            "tolerance": tolerance,
            "converged": False,
            "termination_reason": None,
        }

        m2 = m1
        k2 = k1
        Z2 = Z1
        for iteration in range(max_iter):
            t2_old = t2_guess

            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_old, gas_obj, eos)
                m2, _, k2 = CompressorAerodynamics.real_gas_temperature_exponents(state_out, poly_eff_clamped)
                Z2 = state_out.Z
            except Exception as error:
                raise RuntimeError(f"Çıkış özellikleri hesaplanamadı (Metot 2, iter {iteration}): {error}")

            m2_val = float(m2) if math.isfinite(m2) else m1
            n_minus_1_over_n = 0.5 * (m1 + m2_val)
            if abs(n_minus_1_over_n) < 1e-10:
                history["termination_reason"] = "near_zero_exponent"
                break
            # n fiziksel aralık kontrolü (tipik 0.02-0.45)
            n_minus_1_over_n = max(0.02, min(0.45, n_minus_1_over_n))

            t2_new = t_in * (p_out / p_in) ** n_minus_1_over_n
            if not math.isfinite(t2_new) or t2_new <= 0:
                t2_new = t_in * 1.2
            t2_unclamped = t2_old + 0.8 * (t2_new - t2_old)
            if t2_unclamped <= t_in:
                t2_unclamped = t_in * 1.01
            # Fiziksel üst sınır (PR<=8 için T_out < T_in*2.8)
            upper_bound = t_in * 2.8
            hit_upper_clamp = t2_unclamped >= upper_bound
            t2_guess = min(t2_unclamped, upper_bound)

            history["pressure"].append(p_out)
            history["temperature"].append(t2_guess)
            history["z_factor"].append(Z2)
            history["k_value"].append(k2)
            history["iteration"].append(iteration + 1)

            if abs(t2_guess - t2_old) < tolerance:
                if hit_upper_clamp:
                    history["converged"] = False
                    history["termination_reason"] = "upper_clamp_hit"
                    break
                state_out_final = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                z2_final = state_out_final.Z
                m2_final, _, _ = CompressorAerodynamics.real_gas_temperature_exponents(
                    state_out_final, poly_eff_clamped
                )
                n_final_conv = max(0.02, min(0.45, 0.5 * (m1 + m2_final)))
                z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, z2_final)
                r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
                v1 = CompressorAerodynamics._specific_volume_m3_kg(state_in, r_specific)
                v2_final = CompressorAerodynamics._specific_volume_m3_kg(state_out_final, r_specific)
                w_uncorr = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1, p_out, v2_final)
                if w_uncorr > 0.0 and math.isfinite(w_uncorr):
                    poly_head = w_uncorr / 1000.0
                else:
                    poly_head = self._calculate_polytropic_head(
                        z_avg, r_specific, t_in, p_out / p_in, n_final_conv
                    )

                self.logger.debug(f"✓ Metot 2 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                history["converged"] = True
                history["termination_reason"] = "converged"
                return t2_guess, poly_head, z_avg, history

        self.logger.warning(f"⚠ Metot 2: Yakınsama sağlanamadı ({max_iter} iter).")
        z_avg_final = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)
        r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
        n_final = max(0.02, min(0.45, float(m2) if math.isfinite(m2) else 0.25))
        try:
            state_out_fb = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
            v1 = CompressorAerodynamics._specific_volume_m3_kg(state_in, r_specific)
            v2_fb = CompressorAerodynamics._specific_volume_m3_kg(state_out_fb, r_specific)
            poly_head = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1, p_out, v2_fb) / 1000.0
        except Exception:
            poly_head = self._calculate_polytropic_head(
                z_avg_final,
                r_specific,
                t_in,
                p_out / p_in,
                n_final,
            )
        history["termination_reason"] = history["termination_reason"] or "max_iterations"
        return t2_guess, poly_head, z_avg_final, history

    def method_incremental_pressure(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=10):
        p_in, p_out = self._coerce_pressures(p_in, p_out)
        step_count = self._coerce_step_count(step_count)
        poly_eff = self._coerce_poly_eff(poly_eff)

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            z0 = state_in.Z
            mw = state_in.MW
            _, _, k0 = CompressorAerodynamics.real_gas_temperature_exponents(state_in, poly_eff)
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 3): {error}")

        if abs(p_out - p_in) < 1.0:
            return t_in, 0.0, z0, {
                "pressure": [p_in],
                "temperature": [t_in],
                "z_factor": [z0],
                "k_value": [k0],
                "head_incremental": [0.0],
                "step": [0],
                "method_used": "incremental_pressure",
                "step_count": 0,
                "converged": True,
                "termination_reason": "zero_dp",
            }

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)

        history = {
            "pressure": [p_in],
            "temperature": [t_in],
            "z_factor": [z0],
            "k_value": [k0],
            "head_incremental": [0.0],
            "step": [0],
            "method_used": "incremental_pressure",
            "step_count": step_count,
            "converged": True,
        }

        pressures = np.geomspace(p_in, p_out, step_count + 1)
        t_current = t_in
        total_head = 0.0
        z_list = [z0]
        state_step = state_in

        for index in range(step_count):
            p_start = float(pressures[index])
            p_end = float(pressures[index + 1])

            try:
                if index > 0:
                    state_step = self.thermo_solver.get_properties(p_start, t_current, gas_obj, eos)
                n_step, _, k_step = CompressorAerodynamics.real_gas_temperature_exponents(
                    state_step, poly_eff
                )
            except Exception as error:
                raise RuntimeError(f"Artımlı hesaplama hatası — Adım {index}: {error}")

            if abs(n_step) < 1e-10:
                raise RuntimeError(f"n_step sıfıra çok yakın (adım {index}).")

            t_next = t_current * (p_end / p_start) ** n_step
            try:
                state_next = self.thermo_solver.get_properties(p_end, t_next, gas_obj, eos)
                v_start = CompressorAerodynamics._specific_volume_m3_kg(state_step, r_specific)
                v_end = CompressorAerodynamics._specific_volume_m3_kg(state_next, r_specific)
                head_step = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(
                    p_start, v_start, p_end, v_end
                ) / 1000.0
                z_end = state_next.Z
                _, _, k_end = CompressorAerodynamics.real_gas_temperature_exponents(state_next, poly_eff)
                state_step = state_next
            except Exception as error:
                raise RuntimeError(f"Artımlı hesaplama hatası — Adım {index}: {error}")

            total_head += head_step
            t_current = t_next

            z_list.append(z_end)
            history["pressure"].append(p_end)
            history["temperature"].append(t_current)
            history["z_factor"].append(z_end)
            history["k_value"].append(k_end)
            history["head_incremental"].append(total_head)
            history["step"].append(index + 1)

        z_avg = float(np.mean(z_list))
        self.logger.debug(f"✓ Metot 3 tamamlandı: {step_count} adım, T_out={t_current:.1f} K, Head={total_head:.2f} kJ/kg")
        return t_current, total_head, z_avg, history

    def method_direct_hs(self, p_in, t_in, p_out, poly_eff, gas_obj, eos):
        p_in, p_out = self._coerce_pressures(p_in, p_out)
        poly_eff = self._coerce_poly_eff(poly_eff)
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            h1, s1, z1 = state_in.H, state_in.S, state_in.Z
            m_poly_1, m_isen_1, k1 = CompressorAerodynamics.real_gas_temperature_exponents(
                state_in, poly_eff
            )
            mw = state_in.MW
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 4): {error}")

        if abs(p_out - p_in) < 1.0:
            return t_in, 0.0, z1, {
                "converged": True,
                "method_used": "direct_hs",
                "termination_reason": "zero_dp",
                "iterations_hs": [],
                "delta_h_actual": 0.0,
                "eta_isen_final": poly_eff,
                "t_isen_final": t_in,
                "fallback_used": False,
            }

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
        t_isen = self.find_isentropic_temperature(p_in, t_in, p_out, s1, gas_obj, eos, state_in)

        try:
            state_isen = self.thermo_solver.get_properties(p_out, t_isen, gas_obj, eos)
            h2_isen = state_isen.H
        except Exception as error:
            raise RuntimeError(f"İzentropik çıkış özellikleri hesaplanamadı (Metot 4): {error}")

        delta_h_isen = h2_isen - h1
        fallback_used = False

        if delta_h_isen <= 0:
            fallback_used = True
            self.logger.warning(
                f"⚠ Metot 4: ΔH_isen negatif ({delta_h_isen:.1f} J/kg). k-tabanlı izentropik fallback kullanılıyor."
            )
            pressure_ratio = p_out / p_in
            n_isen_fb = m_isen_1
            z_avg_fb = z1
            delta_h_isen = (
                z_avg_fb
                * r_specific
                * t_in
                * (1.0 / n_isen_fb)
                * (math.pow(pressure_ratio, n_isen_fb) - 1.0)
            )
            t_isen = t_in * math.pow(pressure_ratio, n_isen_fb)
            self.logger.info(
                f"  Fallback: ΔH_isen={delta_h_isen/1000:.1f} kJ/kg, T_isen={t_isen:.1f} K"
            )

        pressure_ratio = p_out / p_in
        k_avg = k1
        exponent_isen = m_isen_1
        exponent_poly = m_poly_1
        t2_guess = t_isen * (1.0 + (1.0 - poly_eff) * 0.3)
        iterations_hs = []
        outer_iterations = 4
        hs_converged = False
        v1_hs = CompressorAerodynamics._specific_volume_m3_kg(state_in, r_specific)
        v2s_hs = CompressorAerodynamics._specific_volume_m3_kg(state_isen, r_specific) if not fallback_used else v1_hs
        w_isen_hs = (
            CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1_hs, p_out, v2s_hs)
            if not fallback_used
            else delta_h_isen
        )
        eta_isen_override = None

        for outer in range(outer_iterations):
            if eta_isen_override is not None and math.isfinite(eta_isen_override) and eta_isen_override > 0:
                eta_isen = eta_isen_override
            else:
                pr_isen_term = math.pow(pressure_ratio, exponent_isen) - 1.0
                pr_poly_term = math.pow(pressure_ratio, exponent_poly) - 1.0
                if abs(pr_poly_term) < 1e-10:
                    eta_isen = poly_eff
                else:
                    eta_isen = pr_isen_term / pr_poly_term

            eta_isen = max(0.01, min(1.0, eta_isen))
            delta_h_actual = delta_h_isen / eta_isen
            h_target = h1 + delta_h_actual

            max_iter = self._coerce_iteration_limit(30)
            tol_h = 25.0

            for iteration in range(max_iter):
                try:
                    state_guess = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                    h_guess = state_guess.H
                except Exception as error:
                    self.logger.warning(
                        f"Metot 4 iter {outer}.{iteration}: özellik hatası @ T={t2_guess:.1f} K: {error}"
                    )
                    t2_guess = t2_guess * 0.99
                    continue

                d_h = h_guess - h_target
                iterations_hs.append(
                    {
                        "iter": f"{outer}.{iteration}",
                        "T": t2_guess,
                        "H": h_guess,
                        "H_target": h_target,
                        "dH": d_h,
                        "k_avg": k_avg,
                        "eta_isen": eta_isen,
                    }
                )

                if abs(d_h) < tol_h:
                    hs_converged = True
                    self.logger.debug(
                        f"✓ Metot 4 iç döngü yakınsadı: outer={outer}, iter={iteration + 1}, "
                        f"T_out={t2_guess:.1f} K, ΔH_err={d_h:.1f} J/kg, k_avg={k_avg:.4f}"
                    )
                    break

                dt = 0.5
                try:
                    state_plus = self.thermo_solver.get_properties(p_out, t2_guess + dt, gas_obj, eos)
                    d_h_d_t = (state_plus.H - h_guess) / dt
                except Exception:
                    d_h_d_t = state_in.Cp if state_in.Cp > 0 else 2000.0

                if abs(d_h_d_t) < 1e-5:
                    d_h_d_t = 2000.0

                delta_t = -d_h / d_h_d_t
                delta_t = max(-50.0, min(50.0, delta_t))
                t2_guess = t2_guess + 0.8 * delta_t
                # Fiziksel sınır: T_out en fazla T_in * 2.8 (PR<=8 için bile yeterli), en az T_in*1.005
                t2_guess = max(t_in * 1.005, min(t_in * 2.8, t2_guess))
                # Ek güvenlik: Cp nan veya k anormal ise clamp daha dar
                if not math.isfinite(t2_guess):
                    t2_guess = t_in * (1.0 + (1.0 - poly_eff) * 0.3)
                    t2_guess = max(t_in * 1.005, min(t_in * 2.8, t2_guess))

            else:
                self.logger.warning(
                    f"⚠ Metot 4: inner loop maks. iterasyon ({max_iter}) aşıldı. Son T={t2_guess:.1f} K"
                )

            try:
                state_t2 = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                m_poly_2, m_isen_2, k2 = CompressorAerodynamics.real_gas_temperature_exponents(
                    state_t2, poly_eff
                )
                k_avg_new = (k1 + k2) / 2.0
                exponent_isen = (m_isen_1 + m_isen_2) / 2.0
                exponent_poly = (m_poly_1 + m_poly_2) / 2.0
                if not fallback_used and w_isen_hs > 0.0:
                    v2_t2 = CompressorAerodynamics._specific_volume_m3_kg(state_t2, r_specific)
                    w_poly_t2 = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(
                        p_in, v1_hs, p_out, v2_t2
                    )
                    if w_poly_t2 > 0.0:
                        eta_isen_new = poly_eff * (w_isen_hs / w_poly_t2)
                        if eta_isen_override is not None and abs(eta_isen_new - eta_isen_override) < 1e-4:
                            k_avg = k_avg_new
                            eta_isen = max(0.01, min(1.0, eta_isen_new))
                            break
                        eta_isen_override = eta_isen_new
                        k_avg = k_avg_new
                        continue
                self.logger.debug(
                    f"  Dış döngü {outer}: k₁={k1:.4f}, k₂={k2:.4f}, k_avg: {k_avg:.4f} → {k_avg_new:.4f}"
                )
                if abs(k_avg_new - k_avg) < 0.001:
                    k_avg = k_avg_new
                    break
                k_avg = k_avg_new
            except Exception:
                break

        state_out = None
        try:
            state_out = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
            z2 = state_out.Z
        except Exception:
            z2 = z1

        z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(z1, z2)

        if t2_guess <= t_in:
            self.logger.warning(
                "⚠ Metot 4: Çıkış sıcaklığı giriş sıcaklığından küçük/eşit (T_out=%.1f K <= T_in=%.1f K).",
                t2_guess,
                t_in,
            )
            hs_converged = False
            ln_tr = 1e-10
        else:
            ln_tr = math.log(t2_guess / t_in)
        ln_pr = math.log(p_out / p_in)

        if abs(ln_pr) < 1e-10:
            poly_head = 0.0
        elif state_out is not None and not fallback_used:
            v1 = CompressorAerodynamics._specific_volume_m3_kg(state_in, r_specific)
            v2 = CompressorAerodynamics._specific_volume_m3_kg(state_out, r_specific)
            v2s = CompressorAerodynamics._specific_volume_m3_kg(state_isen, r_specific)
            w_poly = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1, p_out, v2)
            w_isen = CompressorAerodynamics._uncorrected_polytropic_work_j_kg(p_in, v1, p_out, v2s)
            f_s = max(0.85, min(1.15, delta_h_isen / w_isen)) if w_isen > 0 else 1.0
            poly_head = (f_s * w_poly) / 1000.0
        else:
            sigma = ln_tr / ln_pr
            if abs(sigma) < 1e-10:
                poly_head = (z_avg * r_specific * t_in * ln_pr) / 1000.0
            else:
                poly_head = self._calculate_polytropic_head(
                    z_avg,
                    r_specific,
                    t_in,
                    p_out / p_in,
                    sigma,
                )

        history = {
            "method_used": "direct_hs",
            "pressure": [p_in, p_out],
            "temperature": [t_in, t2_guess],
            "z_factor": [z1, z2],
            "k_value": [k1, k_avg],
            "iteration": list(range(len(iterations_hs) + 1)),
            "t_isentropic": t_isen,
            "delta_h_isentropic_kj": delta_h_isen / 1000.0,
            "delta_h_actual_kj": delta_h_actual / 1000.0,
            "eta_isentropic_derived": eta_isen,
            "sigma_backcomputed": ln_tr / ln_pr if abs(ln_pr) > 1e-10 else 0,
            "iterations_detail": iterations_hs,
            "inner_iteration_limit": max_iter,
            "outer_iteration_limit": outer_iterations,
            "converged": hs_converged,
            "fallback_used": fallback_used,
        }

        self.logger.info(
            f"✓ Metot 4 (H-S) tamamlandı: T_out={t2_guess:.1f} K ({t2_guess-273.15:.1f}°C), "
            f"H_poly={poly_head:.2f} kJ/kg, η_isen={eta_isen:.4f}, "
            f"ΔH_isen={delta_h_isen/1000:.1f} kJ/kg, ΔH_actual={delta_h_actual/1000:.1f} kJ/kg"
        )

        # Faz siniri kontrolu: gerçek gaz sıcaklık üssü referansı ile karşılaştır
        pr_total = p_out / p_in
        n_poly_ref = exponent_poly if exponent_poly > 0 else m_poly_1
        t_out_kbased = t_in * (pr_total ** n_poly_ref)
        deviation_pct = abs(t2_guess - t_out_kbased) / t_out_kbased * 100.0 if t_out_kbased > 0 else 0
        if deviation_pct > 3.0:
            self.logger.warning(
                "⚠️ Metot 4 sonucu k-tabanlı referanstan %.1f%% sapıyor "
                "(T_out_H-S=%.1f K vs T_out_k-ref=%.1f K, Z_out=%.4f). "
                "Faz zarfına yakın bölge olabilir — sonuçları diğer metotlarla karşılaştırın.",
                deviation_pct, t2_guess, t_out_kbased, z2,
            )
            history["phase_boundary_warning"] = True
            history["t_out_kbased_ref"] = t_out_kbased
            history["deviation_pct"] = deviation_pct
            if deviation_pct > 50.0:
                self.logger.warning("⚠️ Metot 4 sapması %50'yi aştı, yakınsama güvenilmez kabul ediliyor - M1 fallback tetiklenecek.")
                history["converged"] = False
                history["termination_reason"] = f"excessive_deviation_{deviation_pct:.1f}pct"
                hs_converged = False

        # Son güvenlik: eff >1 veya t_out fizik dışı ise converge false
        if eta_isen > 0.99 or t2_guess > t_in * 2.8 or not math.isfinite(t2_guess):
            self.logger.warning(f"⚠️ Metot 4 fizik dışı sonuç (η={eta_isen:.3f}, T={t2_guess:.1f}K) - M1 fallback")
            history["converged"] = False
            history["termination_reason"] = "unphysical_result"
            hs_converged = False
        else:
            history["converged"] = hs_converged

        return t2_guess, poly_head, z_avg, history

    def method_huntington_rk45(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=20, adaptive=True, tol=1e-4):
        """
        Metot 5: Huntington-RK45 Sürekli Diferansiyel Yol Entegratörü (ASME 85-GT-13).
        Adaptif Adım Boyutlu Runge-Kutta-Fehlberg (RKF45) algoritması içerir.
        dT/dP = [v * (1/eta_p - 1) + T * (dv/dT)_P] / Cp(P, T)
        H_p = integral_{P_in}^{P_out} v(P, T(P)) dP
        """
        p_in, p_out = self._coerce_pressures(p_in, p_out)
        step_count = self._coerce_step_count(step_count, default=20)
        poly_eff = self._coerce_poly_eff(poly_eff)
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            z0 = state_in.Z
            mw = state_in.MW
            h1 = state_in.H
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 5): {error}")

        def get_derivatives(p_pa, t_k):
            st = self.thermo_solver.get_properties(p_pa, t_k, gas_obj, eos)
            v = 1.0 / max(1e-6, st.density)  # m3/kg
            cp = max(100.0, float(st.Cp))  # J/(kg.K)
            
            # (dv/dT)_P via central/forward difference
            dt = 0.5
            st_plus = self.thermo_solver.get_properties(p_pa, t_k + dt, gas_obj, eos)
            v_plus = 1.0 / max(1e-6, st_plus.density)
            dv_dt = (v_plus - v) / dt
            
            # 1st Law ODE: dT/dP
            dt_dp = (v * (1.0 / poly_eff - 1.0) + t_k * dv_dt) / cp
            return dt_dp, v, st.Z

        total_dp = p_out - p_in
        if abs(total_dp) < 1.0:
            return t_in, 0.0, z0, {
                "method_used": "huntington_rk45",
                "pressure": [p_in],
                "temperature": [t_in],
                "z_factor": [z0],
                "step_count": 0,
                "converged": True,
                "termination_reason": "zero_dp",
            }

        t_current = t_in
        p_current = p_in
        poly_head_total = 0.0
        z_list = [z0]
        t_list = [t_in]
        p_list = [p_in]

        # Yakinsama dogrulama isaretleri (P0-2)
        reached_outlet = False
        tolerance_forced = False
        termination_reason = "converged"

        try:
            if not adaptive:
                # Fixed-step RK4 fallback
                pressures = np.linspace(p_in, p_out, step_count + 1)
                dp = pressures[1] - pressures[0]
                for i in range(step_count):
                    p_curr = pressures[i]
                    k1_dt_dp, v1, z_curr = get_derivatives(p_curr, t_current)
                    
                    p_mid = p_curr + 0.5 * dp
                    t_k2 = t_current + 0.5 * dp * k1_dt_dp
                    k2_dt_dp, v2, _ = get_derivatives(p_mid, t_k2)
                    
                    t_k3 = t_current + 0.5 * dp * k2_dt_dp
                    k3_dt_dp, v3, _ = get_derivatives(p_mid, t_k3)
                    
                    p_next = p_curr + dp
                    t_k4 = t_current + dp * k3_dt_dp
                    k4_dt_dp, v4, z_next = get_derivatives(p_next, t_k4)
                    
                    t_current += (dp / 6.0) * (k1_dt_dp + 2.0 * k2_dt_dp + 2.0 * k3_dt_dp + k4_dt_dp)
                    poly_head_total += (dp / 6.0) * (v1 + 4.0 * ((v2 + v3) / 2.0) + v4)
                    
                    z_list.append(z_next)
                    t_list.append(t_current)
                    p_list.append(p_next)
                reached_outlet = True
                termination_reason = "fixed_step"
            else:
                # Adaptive RKF45 (Runge-Kutta-Fehlberg)
                h = total_dp / max(step_count, 10)
                h_min = abs(total_dp) * 1e-6
                h_max = abs(total_dp) * 0.25
                max_iterations = 500
                iter_count = 0

                while (p_current < p_out - 1e-6) and (iter_count < max_iterations):
                    iter_count += 1
                    from kasp.core.aerodynamics import is_calculation_cancel_requested
                    from kasp.core.exceptions import CalculationCancelled
                    if is_calculation_cancel_requested():
                        raise CalculationCancelled("Kullanıcı hesaplamayı iptal etti.")
                    if p_current + h > p_out:
                        h = p_out - p_current

                    # RKF45 stages
                    k1, v1, z1 = get_derivatives(p_current, t_current)
                    k2, v2, _ = get_derivatives(p_current + (1.0 / 4.0) * h, t_current + (1.0 / 4.0) * h * k1)
                    k3, v3, _ = get_derivatives(
                        p_current + (3.0 / 8.0) * h,
                        t_current + (3.0 / 32.0) * h * k1 + (9.0 / 32.0) * h * k2,
                    )
                    k4, v4, _ = get_derivatives(
                        p_current + (12.0 / 13.0) * h,
                        t_current + (1932.0 / 2197.0) * h * k1 - (7200.0 / 2197.0) * h * k2 + (7296.0 / 2197.0) * h * k3,
                    )
                    k5, v5, _ = get_derivatives(
                        p_current + h,
                        t_current + (439.0 / 216.0) * h * k1 - 8.0 * h * k2 + (3680.0 / 513.0) * h * k3 - (845.0 / 4104.0) * h * k4,
                    )
                    k6, v6, _ = get_derivatives(
                        p_current + 0.5 * h,
                        t_current - (8.0 / 27.0) * h * k1 + 2.0 * h * k2 - (3544.0 / 2565.0) * h * k3 + (1859.0 / 4104.0) * h * k4 - (11.0 / 40.0) * h * k5,
                    )

                    # 4th and 5th order solutions
                    t4 = t_current + h * (
                        (25.0 / 216.0) * k1 + (1408.0 / 2565.0) * k3 + (2197.0 / 4104.0) * k4 - (1.0 / 5.0) * k5
                    )
                    t5 = t_current + h * (
                        (16.0 / 135.0) * k1 + (6656.0 / 12825.0) * k3 + (28561.0 / 56430.0) * k4 - (9.0 / 50.0) * k5 + (2.0 / 55.0) * k6
                    )
                    
                    # Local truncation error
                    err = abs(t5 - t4)
                    tol_effective = max(tol, 1e-6) * (1.0 + abs(t_current) * 1e-4)

                    if err <= tol_effective or h <= h_min:
                        if err > tol_effective:
                            # h_min'a dayandi; hata toleransin uzerinde kabul edildi
                            tolerance_forced = True
                        # Accept step
                        dh = h * (
                            (16.0 / 135.0) * v1 + (6656.0 / 12825.0) * v3 + (28561.0 / 56430.0) * v4 - (9.0 / 50.0) * v5 + (2.0 / 55.0) * v6
                        )
                        poly_head_total += dh
                        p_current += h
                        t_current = t5
                        
                        st_end = self.thermo_solver.get_properties(p_current, t_current, gas_obj, eos)
                        z_list.append(st_end.Z)
                        t_list.append(t_current)
                        p_list.append(p_current)

                        # Step size adjustment for accepted step
                        scale = 0.84 * ((tol_effective / max(err, 1e-12)) ** 0.2)
                        scale = max(0.2, min(2.5, scale))
                        h = max(h_min, min(h_max, h * scale))
                    else:
                        # Reject step, reduce step size
                        scale = 0.84 * ((tol_effective / max(err, 1e-12)) ** 0.2)
                        scale = max(0.1, min(0.5, scale))
                        h = max(h_min, h * scale)

                # Iterasyon sinirina takildiysa p_out'a ulasilmadi
                reached_outlet = p_current >= p_out - 1e-6

            # Yakinsama dogrulamasi: p_out'a ulasma ve tolerans zorlamasi kontrol edilir
            if not reached_outlet:
                converged = False
                termination_reason = "max_iterations"
            elif tolerance_forced:
                converged = False
                termination_reason = "h_min_tolerance_exceeded"
            else:
                converged = True

            poly_head_kj_kg = poly_head_total / 1000.0
            z_avg = float(np.mean(z_list))
            
            history = {
                "method_used": "huntington_rk45",
                "pressure": p_list,
                "temperature": t_list,
                "z_factor": z_list,
                "step_count": len(p_list) - 1,
                "converged": converged,
                "termination_reason": termination_reason,
            }
            if not converged:
                self.logger.warning(
                    f"⚠️ Metot 5 (Huntington-RK45) yakinsamadi: neden={termination_reason}, "
                    f"p={p_current/1e5:.2f}/{p_out/1e5:.2f} bar, adim={len(p_list)-1}"
                )
            else:
                self.logger.info(
                    f"✓ Metot 5 (Huntington-RK45) tamamlandı: T_out={t_current:.1f} K ({t_current-273.15:.1f}°C), "
                    f"H_poly={poly_head_kj_kg:.2f} kJ/kg, Z_avg={z_avg:.4f}, Adım={len(p_list)-1}"
                )
            return t_current, poly_head_kj_kg, z_avg, history
        except Exception as exc:
            self.logger.warning(f"Metot 5 RK45 hatası: {exc}")
            raise

    def method_schultz_3exp(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        """
        Metot 6: Schultz 3-Üslü Gerçek Gaz Modeli (Schultz 1962, ASME PTC-10).
        X = (T/Z)*(dZ/dT)_P
        Y = 1 - (P/Z)*(dZ/dP)_T
        m_T = (R*Z/Cp) * (1/eta_p + X)
        1/n_v = Y - m_T * (1 + X), H_p = f_s * [n_v / (n_v - 1)] * (P_2*v_2 - P_1*v_1)
        """
        p_in, p_out = self._coerce_pressures(p_in, p_out)
        max_iter = self._coerce_iteration_limit(max_iter)
        tolerance = self._coerce_tolerance(tolerance)
        poly_eff = self._coerce_poly_eff(poly_eff)

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            z1, k1 = state_in.Z, isentropic_exponent(state_in)
            mw = state_in.MW
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 6): {error}")

        if abs(p_out - p_in) < 1.0:
            return t_in, 0.0, z1, {
                "pressure": [p_in],
                "temperature": [t_in],
                "z_factor": [z1],
                "k_value": [k1],
                "iteration": [0],
                "converged": True,
                "method_used": "schultz_3exp",
                "termination_reason": "zero_dp",
            }

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
        pr = p_out / p_in

        def _eval_schultz_point(p_pa: float, t_k: float, base_state=None):
            st = base_state or self.thermo_solver.get_properties(p_pa, t_k, gas_obj, eos)
            z_pt = max(1e-4, float(st.Z))
            cp_pt = max(100.0, float(st.Cp))
            k_pt = isentropic_exponent(st)

            dt = max(0.25, min(1.0, 0.002 * t_k))
            t_hi = t_k + dt
            t_lo = max(1.0, t_k - dt)
            st_t_hi = self.thermo_solver.get_properties(p_pa, t_hi, gas_obj, eos)
            st_t_lo = self.thermo_solver.get_properties(p_pa, t_lo, gas_obj, eos)
            dz_dt = (st_t_hi.Z - st_t_lo.Z) / max(1e-6, t_hi - t_lo)

            dp = max(500.0, 0.005 * p_pa)
            p_hi = p_pa + dp
            p_lo = max(100.0, p_pa - dp)
            st_p_hi = self.thermo_solver.get_properties(p_hi, t_k, gas_obj, eos)
            st_p_lo = self.thermo_solver.get_properties(p_lo, t_k, gas_obj, eos)
            dz_dp = (st_p_hi.Z - st_p_lo.Z) / max(1.0, p_hi - p_lo)

            x_val = (t_k / z_pt) * dz_dt
            y_val = 1.0 - (p_pa / z_pt) * dz_dp
            m_t_val = (r_specific * z_pt / cp_pt) * (1.0 / poly_eff + x_val)
            return st, x_val, y_val, m_t_val, k_pt

        def _compute_schultz_head(t_out_final: float, x_eff: float, y_eff: float, m_t_eff: float, k_ref: float):
            st_out_final = self.thermo_solver.get_properties(p_out, t_out_final, gas_obj, eos)
            z2_final = st_out_final.Z
            v1 = (1.0 / state_in.density) if state_in.density and state_in.density > 0 else (z1 * r_specific * t_in / p_in)
            v2 = (1.0 / st_out_final.density) if st_out_final.density and st_out_final.density > 0 else (z2_final * r_specific * t_out_final / p_out)

            inv_nv_local = y_eff - m_t_eff * (1.0 + x_eff)
            nv_local = (1.0 / inv_nv_local) if abs(inv_nv_local) > 1e-6 else (k_ref / max(1e-4, y_eff))

            if v1 > 0 and v2 > 0 and abs(math.log(v1 / v2)) > 1e-8:
                n_v_val = math.log(pr) / math.log(v1 / v2)
            else:
                n_v_val = nv_local

            if abs(n_v_val - 1.0) > 1e-6:
                head_uncorr = ((n_v_val / (n_v_val - 1.0)) * (p_out * v2 - p_in * v1)) / 1000.0
            else:
                head_uncorr = (p_in * v1 * math.log(pr)) / 1000.0

            # Schultz (1962) Eq. 27 gerçek hacim-üslü head düzeltme faktörü:
            # f_s = (h_2s - h_1) / [ (n_s / (n_s - 1)) * (P_2*v_2s - P_1*v_1) ]
            schultz_f = 1.0
            try:
                t2_isen = CompressorAerodynamics.calculate_isentropic_temp_fallback(
                    state_in, p_out, self.thermo_solver, gas_obj, eos
                )
                st_isen = self.thermo_solver.get_properties(p_out, t2_isen, gas_obj, eos)
                dh_isen_j = st_isen.H - state_in.H
                v2s = (
                    (1.0 / st_isen.density)
                    if st_isen.density and st_isen.density > 0
                    else (st_isen.Z * r_specific * t2_isen / p_out)
                )
                if dh_isen_j > 0 and v1 > 0 and v2s > 0 and abs(math.log(v1 / v2s)) > 1e-8:
                    n_s = math.log(pr) / math.log(v1 / v2s)
                    if abs(n_s - 1.0) > 1e-6:
                        w_isen_poly = (n_s / (n_s - 1.0)) * (p_out * v2s - p_in * v1)
                    else:
                        w_isen_poly = p_in * v1 * math.log(pr)
                    if w_isen_poly > 0:
                        schultz_f = max(0.90, min(1.10, dh_isen_j / w_isen_poly))
            except Exception as exc:
                self.logger.debug("Schultz Eq.27 factor fallback to 1.0: %s", exc)
            z_avg_val = CompressorAerodynamics._calculate_z_average_logarithmic(z1, z2_final)
            return head_uncorr * schultz_f, z_avg_val, n_v_val, schultz_f

        _, x1, y1, m_t1, _ = _eval_schultz_point(p_in, t_in, base_state=state_in)
        t2_guess = t_in * math.pow(pr, max(0.01, m_t1))
        p_mid = math.sqrt(p_in * p_out)

        history = {
            "pressure": [p_in],
            "temperature": [t_in],
            "z_factor": [z1],
            "k_value": [k1],
            "iteration": [0],
            "converged": False,
            "method_used": "schultz_3exp",
            "termination_reason": None,
        }

        z2 = z1
        X_eff, Y_eff, m_T_eff, k_avg = x1, y1, m_t1, k1
        for iteration in range(max_iter):
            t2_old = t2_guess
            try:
                state_out, x2, y2, m_t2, k2 = _eval_schultz_point(p_out, t2_guess)
                z2 = state_out.Z
                t_mid = math.sqrt(max(1.0, t_in * t2_guess))
                _, x_mid, y_mid, m_t_mid, k_mid = _eval_schultz_point(p_mid, t_mid)
            except Exception as error:
                self.logger.warning(f"Metot 6 iterasyon hatası: {error}")
                break

            X_eff = (x1 + 4.0 * x_mid + x2) / 6.0
            Y_eff = (y1 + 4.0 * y_mid + y2) / 6.0
            m_T_eff = (m_t1 + 4.0 * m_t_mid + m_t2) / 6.0
            k_avg = (k1 + 4.0 * k_mid + k2) / 6.0

            t2_calc = t_in * math.pow(pr, m_T_eff)
            t2_guess = t2_old + 0.6 * (t2_calc - t2_old)

            history["pressure"].append(p_out)
            history["temperature"].append(t2_guess)
            history["z_factor"].append(z2)
            history["k_value"].append(k2)
            history["iteration"].append(iteration + 1)

            if abs(t2_guess - t2_old) < tolerance:
                poly_head, z_avg, n_v, schultz_f = _compute_schultz_head(
                    t2_guess, X_eff, Y_eff, m_T_eff, k_avg
                )
                history["converged"] = True
                history["termination_reason"] = "converged"
                history["X"] = X_eff
                history["Y"] = Y_eff
                history["n_v"] = n_v
                history["m_T"] = m_T_eff
                history["schultz_f"] = schultz_f
                self.logger.info(
                    f"✓ Metot 6 (Schultz 3-Exp) tamamlandı: T_out={t2_guess:.1f} K ({t2_guess-273.15:.1f}°C), "
                    f"H_poly={poly_head:.2f} kJ/kg, X={X_eff:.4f}, Y={Y_eff:.4f}, n_v={n_v:.4f}, f={schultz_f:.4f}"
                )
                return t2_guess, poly_head, z_avg, history

        # Fallback if loop finishes without hitting tolerance
        try:
            poly_head, z_avg_final, n_v_fb, schultz_f_fb = _compute_schultz_head(
                t2_guess, X_eff, Y_eff, m_T_eff, k_avg
            )
            history["X"] = X_eff
            history["Y"] = Y_eff
            history["n_v"] = n_v_fb
            history["m_T"] = m_T_eff
            history["schultz_f"] = schultz_f_fb
        except Exception:
            z_avg_final = CompressorAerodynamics._calculate_z_average_logarithmic(z1, z2)
            n_final = (k1 - 1.0) / (k1 * poly_eff)
            poly_head = self._calculate_polytropic_head(z_avg_final, r_specific, t_in, pr, n_final)
        history["termination_reason"] = "max_iterations"
        return t2_guess, poly_head, z_avg_final, history

    def find_isentropic_temperature(self, p_in, t_in, p_out, s_target, gas_obj, eos, state_in):
        # CoolProp direkt flash kaldirildi — sayisal cozucu (SolverChain) daha guvenilir
        from kasp.core.aerodynamics import CompressorAerodynamics
        return CompressorAerodynamics.calculate_isentropic_temp_fallback(
            state_in, p_out, self.thermo_solver, gas_obj, eos
        )
