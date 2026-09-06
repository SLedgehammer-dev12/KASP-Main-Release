"""Calculation method strategies used by ThermoEngine."""

from __future__ import annotations

import math

import numpy as np

from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.settings import EngineSettings
from kasp.core.constants import R_UNIVERSAL_J_MOL_K


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
        max_iter = self._coerce_iteration_limit(max_iter)
        tolerance = self._coerce_tolerance(tolerance)
        pr = p_out / p_in
        use_integral = pr > EngineSettings.PR_INTEGRATION_THRESHOLD

        if use_integral:
            self.logger.info(
                f"📊 API 617 Appendix C — İntegral metodu: PR={pr:.2f} > {EngineSettings.PR_INTEGRATION_THRESHOLD}"
            )

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            k1, Z1 = state_in.k, state_in.Z
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 1): {error}")

        n_init = (k1 - 1) / (k1 * poly_eff)
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
                k2, Z2 = state_out.k, state_out.Z
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
                    n_minus_1_over_n = (k_avg - 1) / (k_avg * poly_eff)
                    use_integral_local = False
                    history["method_used"] = "averaging_fallback"
            else:
                k_avg = (k1 + k2) / 2.0
                n_minus_1_over_n = (k_avg - 1) / (k_avg * poly_eff)

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
                    state_avg = self.thermo_solver.get_properties(
                        (p_in + p_out) / 2, (t_in + t2_guess) / 2, gas_obj, eos
                    )
                    z_avg = state_avg.Z
                    mw = state_avg.MW
                except Exception:
                    mw = state_in.MW

                r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
                poly_head = self._calculate_polytropic_head(
                    z_avg,
                    r_specific,
                    t_in,
                    p_out / p_in,
                    n_minus_1_over_n,
                )

                self.logger.debug(f"✓ Metot 1 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                history["converged"] = True
                history["termination_reason"] = "converged"
                return t2_guess, poly_head, z_avg, history

        self.logger.warning(f"⚠ Metot 1: Maks. iterasyon ({max_iter}) aşıldı, son tahmin kullanılıyor.")
        try:
            state_avg = self.thermo_solver.get_properties((p_in + p_out) / 2, (t_in + t2_guess) / 2, gas_obj, eos)
            z_avg_final = state_avg.Z
            k_final = state_avg.k
            mw = state_avg.MW
        except Exception:
            z_avg_final = Z1
            k_final = k1
            mw = state_in.MW

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
        n_final = (k_final - 1) / (k_final * poly_eff)
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
        max_iter = self._coerce_iteration_limit(max_iter)
        tolerance = self._coerce_tolerance(tolerance)
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            k1, Z1 = state_in.k, state_in.Z
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 2): {error}")

        n_init = (k1 - 1) / (k1 * poly_eff)
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

        for iteration in range(max_iter):
            t2_old = t2_guess

            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_old, gas_obj, eos)
                k2, Z2 = state_out.k, state_out.Z
            except Exception as error:
                raise RuntimeError(f"Çıkış özellikleri hesaplanamadı (Metot 2, iter {iteration}): {error}")

            # k ve poly_eff sınırla - eff 0 olmamalı
            k2_clamped = max(1.15, min(1.8, float(k2) if math.isfinite(k2) else 1.4))
            poly_eff_clamped = max(0.3, min(0.99, float(poly_eff) if math.isfinite(poly_eff) else 0.75))
            n_minus_1_over_n = (k2_clamped - 1) / (k2_clamped * poly_eff_clamped)
            if abs(n_minus_1_over_n) < 1e-10:
                history["termination_reason"] = "near_zero_exponent"
                break
            # n fiziksel aralık kontrolü (tipik 0.1-0.35)
            n_minus_1_over_n = max(0.05, min(0.45, n_minus_1_over_n))

            t2_new = t_in * (p_out / p_in) ** n_minus_1_over_n
            if not math.isfinite(t2_new) or t2_new <= 0:
                t2_new = t_in * 1.2
            t2_guess = t2_old + 0.8 * (t2_new - t2_old)
            if t2_guess <= t_in:
                t2_guess = t_in * 1.01
            # Fiziksel üst sınır (PR<=8 için T_out < T_in*2.8)
            t2_guess = min(t2_guess, t_in * 2.8)

            history["pressure"].append(p_out)
            history["temperature"].append(t2_guess)
            history["z_factor"].append(Z2)
            history["k_value"].append(k2)
            history["iteration"].append(iteration + 1)

            if abs(t2_guess - t2_old) < tolerance:
                state_out_final = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                z2_final = state_out_final.Z
                z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, z2_final)
                r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
                poly_head = self._calculate_polytropic_head(
                    z_avg,
                    r_specific,
                    t_in,
                    p_out / p_in,
                    n_minus_1_over_n,
                )

                self.logger.debug(f"✓ Metot 2 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                history["converged"] = True
                history["termination_reason"] = "converged"
                return t2_guess, poly_head, z_avg, history

        self.logger.warning(f"⚠ Metot 2: Yakınsama sağlanamadı ({max_iter} iter).")
        z_avg_final = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)
        r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
        n_final = (k2 - 1) / (k2 * poly_eff)
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
        step_count = self._coerce_step_count(step_count)

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            z0 = state_in.Z
            mw = state_in.MW
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 3): {error}")

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)

        history = {
            "pressure": [p_in],
            "temperature": [t_in],
            "z_factor": [z0],
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

        for index in range(step_count):
            p_start = pressures[index]
            p_end = pressures[index + 1]

            try:
                state_step = self.thermo_solver.get_properties(p_start, t_current, gas_obj, eos)
                k_step = state_step.k
                z_step = state_step.Z
            except Exception as error:
                raise RuntimeError(f"Artımlı hesaplama hatası — Adım {index}: {error}")

            n_step = (k_step - 1) / (k_step * poly_eff)
            if abs(n_step) < 1e-10:
                raise RuntimeError(f"n_step sıfıra çok yakın (adım {index}).")

            head_step = self._calculate_polytropic_head(
                z_step,
                r_specific,
                t_current,
                p_end / p_start,
                n_step,
            )
            total_head += head_step
            t_current = t_current * (p_end / p_start) ** n_step

            z_list.append(z_step)
            history["pressure"].append(p_end)
            history["temperature"].append(t_current)
            history["z_factor"].append(z_step)
            history["head_incremental"].append(total_head)
            history["step"].append(index + 1)

        z_avg = float(np.mean(z_list))
        self.logger.debug(f"✓ Metot 3 tamamlandı: {step_count} adım, T_out={t_current:.1f} K, Head={total_head:.2f} kJ/kg")
        return t_current, total_head, z_avg, history

    def method_direct_hs(self, p_in, t_in, p_out, poly_eff, gas_obj, eos):
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            h1, s1, k1, z1 = state_in.H, state_in.S, state_in.k, state_in.Z
            mw = state_in.MW
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 4): {error}")

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
        t_isen = self.find_isentropic_temperature(p_in, t_in, p_out, s1, gas_obj, eos, state_in)

        try:
            state_isen = self.thermo_solver.get_properties(p_out, t_isen, gas_obj, eos)
            h2_isen = state_isen.H
        except Exception as error:
            raise RuntimeError(f"İzentropik çıkış özellikleri hesaplanamadı (Metot 4): {error}")

        delta_h_isen = h2_isen - h1

        if delta_h_isen <= 0:
            self.logger.warning(
                f"⚠ Metot 4: ΔH_isen negatif ({delta_h_isen:.1f} J/kg). k-tabanlı izentropik fallback kullanılıyor."
            )
            pressure_ratio = p_out / p_in
            n_isen_fb = (k1 - 1) / k1
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
        t2_guess = t_isen * (1.0 + (1.0 - poly_eff) * 0.3)
        iterations_hs = []
        outer_iterations = 3
        hs_converged = False

        for outer in range(outer_iterations):
            exponent_isen = (k_avg - 1) / k_avg
            exponent_poly = (k_avg - 1) / (k_avg * poly_eff)

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
            tol_h = 100.0

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
                k2 = state_t2.k
                k_avg_new = (k1 + k2) / 2.0
                self.logger.debug(
                    f"  Dış döngü {outer}: k₁={k1:.4f}, k₂={k2:.4f}, k_avg: {k_avg:.4f} → {k_avg_new:.4f}"
                )
                if abs(k_avg_new - k_avg) < 0.001:
                    k_avg = k_avg_new
                    break
                k_avg = k_avg_new
            except Exception:
                break

        try:
            state_out = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
            z2 = state_out.Z
        except Exception:
            z2 = z1

        z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(z1, z2)

        ln_tr = math.log(t2_guess / t_in) if t2_guess > t_in else 1e-10
        ln_pr = math.log(p_out / p_in)

        if abs(ln_pr) < 1e-10:
            poly_head = 0.0
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
        }

        self.logger.info(
            f"✓ Metot 4 (H-S) tamamlandı: T_out={t2_guess:.1f} K ({t2_guess-273.15:.1f}°C), "
            f"H_poly={poly_head:.2f} kJ/kg, η_isen={eta_isen:.4f}, "
            f"ΔH_isen={delta_h_isen/1000:.1f} kJ/kg, ΔH_actual={delta_h_actual/1000:.1f} kJ/kg"
        )

        # Faz siniri kontrolu: k-tabanli referans ile karsilastir
        pr_total = p_out / p_in
        n_poly_ref = (k1 - 1.0) / (k1 * poly_eff) if poly_eff > 0 else 0.1
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
        step_count = self._coerce_step_count(step_count, default=20)
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
            else:
                # Adaptive RKF45 (Runge-Kutta-Fehlberg)
                h = total_dp / max(step_count, 10)
                h_min = abs(total_dp) * 1e-6
                h_max = abs(total_dp) * 0.25
                max_iterations = 500
                iter_count = 0

                while (p_current < p_out - 1e-6) and (iter_count < max_iterations):
                    iter_count += 1
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

            poly_head_kj_kg = poly_head_total / 1000.0
            z_avg = float(np.mean(z_list))
            
            history = {
                "method_used": "huntington_rk45",
                "pressure": p_list,
                "temperature": t_list,
                "z_factor": z_list,
                "step_count": len(p_list) - 1,
                "converged": True,
                "termination_reason": "converged",
            }
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
        Metot 6: Schultz 3-Üslü Gerçek Gaz Modeli (Schultz 1962, ASME Original).
        X = (T/Z)*(dZ/dT)_P
        Y = 1 - (P/Z)*(dZ/dP)_T
        n_v = k / [Y - X*(k-1)*(1/eta_p - 1)]
        m_T = (R*Z/Cp) * (1/eta_p + X)
        """
        max_iter = self._coerce_iteration_limit(max_iter)
        tolerance = self._coerce_tolerance(tolerance)
        
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            z1, k1 = state_in.Z, state_in.k
            cp1 = max(100.0, float(state_in.Cp))
            mw = state_in.MW
        except Exception as error:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 6): {error}")

        r_specific = R_UNIVERSAL_J_MOL_K / (mw / 1000.0)
        pr = p_out / p_in
        t2_guess = t_in * math.pow(pr, (k1 - 1.0) / (k1 * poly_eff))
        
        history = {
            "temperature": [t_in],
            "z_factor": [z1],
            "k_value": [k1],
            "iteration": [0],
            "converged": False,
            "method_used": "schultz_3exp",
            "termination_reason": None,
        }

        z2 = z1
        for iteration in range(max_iter):
            t2_old = t2_guess
            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                z2, k2 = state_out.Z, state_out.k
                cp2 = max(100.0, float(state_out.Cp))
            except Exception as error:
                self.logger.warning(f"Metot 6 iterasyon hatası: {error}")
                break

            t_avg = (t_in + t2_guess) / 2.0
            p_avg = (p_in + p_out) / 2.0
            
            # Calculate X and Y compressibility derivatives at average state
            dt = 0.5
            dp = 5000.0
            st_avg = self.thermo_solver.get_properties(p_avg, t_avg, gas_obj, eos)
            z_avg_pt = st_avg.Z
            cp_avg = max(100.0, float(st_avg.Cp))
            k_avg = st_avg.k
            
            st_t_plus = self.thermo_solver.get_properties(p_avg, t_avg + dt, gas_obj, eos)
            dz_dt = (st_t_plus.Z - z_avg_pt) / dt
            
            st_p_plus = self.thermo_solver.get_properties(p_avg + dp, t_avg, gas_obj, eos)
            dz_dp = (st_p_plus.Z - z_avg_pt) / dp
            
            X = (t_avg / max(1e-4, z_avg_pt)) * dz_dt
            Y = 1.0 - (p_avg / max(1e-4, z_avg_pt)) * dz_dp
            
            # Temperature exponent m_T
            m_T = (r_specific * z_avg_pt / max(100.0, cp_avg)) * (1.0 / poly_eff + X)
            t2_calc = t_in * math.pow(pr, m_T)
            t2_guess = t2_old + 0.5 * (t2_calc - t2_old)
            
            history["temperature"].append(t2_guess)
            history["z_factor"].append(z2)
            history["k_value"].append(k2)
            history["iteration"].append(iteration + 1)
            
            if abs(t2_guess - t2_old) < tolerance:
                # Polytropic volume exponent n_v
                denom = Y - X * (k_avg - 1.0) * (1.0 / poly_eff - 1.0)
                n_v = k_avg / denom if abs(denom) > 1e-4 else k_avg / Y
                exp_v = (n_v - 1.0) / n_v if abs(n_v) > 1e-4 else (k_avg - 1.0) / k_avg
                
                z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(z1, z2)
                poly_head = self._calculate_polytropic_head(
                    z_avg, r_specific, t_in, pr, exp_v
                )
                history["converged"] = True
                history["termination_reason"] = "converged"
                history["X"] = X
                history["Y"] = Y
                history["n_v"] = n_v
                history["m_T"] = m_T
                self.logger.info(
                    f"✓ Metot 6 (Schultz 3-Exp) tamamlandı: T_out={t2_guess:.1f} K ({t2_guess-273.15:.1f}°C), "
                    f"H_poly={poly_head:.2f} kJ/kg, X={X:.4f}, Y={Y:.4f}, n_v={n_v:.4f}"
                )
                return t2_guess, poly_head, z_avg, history

        # Fallback if loop finishes
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
