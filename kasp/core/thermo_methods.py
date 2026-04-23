"""Calculation method strategies used by ThermoEngine."""

from __future__ import annotations

import math

import numpy as np

from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.settings import EngineSettings
from kasp.core.constants import R_UNIVERSAL_J_MOL_K


class ThermoMethodSuite:
    def __init__(self, *, thermo_solver, logger):
        self.thermo_solver = thermo_solver
        self.logger = logger

    def method_average_properties(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
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
                poly_head = (
                    z_avg
                    * r_specific
                    * t_in
                    * (1.0 / n_minus_1_over_n)
                    * (math.pow(p_out / p_in, n_minus_1_over_n) - 1.0)
                ) / 1000.0

                self.logger.debug(f"✓ Metot 1 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
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
        poly_head = (
            (
                z_avg_final
                * r_specific
                * t_in
                * (1.0 / n_final)
                * (math.pow(p_out / p_in, n_final) - 1.0)
            )
            / 1000.0
            if abs(n_final) > 1e-10
            else 0.0
        )
        return t2_guess, poly_head, z_avg_final, history

    def method_endpoint(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
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
        }

        for iteration in range(max_iter):
            t2_old = t2_guess

            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_old, gas_obj, eos)
                k2, Z2 = state_out.k, state_out.Z
            except Exception as error:
                raise RuntimeError(f"Çıkış özellikleri hesaplanamadı (Metot 2, iter {iteration}): {error}")

            n_minus_1_over_n = (k2 - 1) / (k2 * poly_eff)
            if abs(n_minus_1_over_n) < 1e-10:
                break

            t2_new = t_in * (p_out / p_in) ** n_minus_1_over_n
            t2_guess = t2_old + 0.8 * (t2_new - t2_old)
            if t2_guess <= t_in:
                t2_guess = t_in * 1.01

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
                poly_head = (
                    z_avg
                    * r_specific
                    * t_in
                    * (1.0 / n_minus_1_over_n)
                    * (math.pow(p_out / p_in, n_minus_1_over_n) - 1.0)
                ) / 1000.0

                self.logger.debug(f"✓ Metot 2 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                return t2_guess, poly_head, z_avg, history

        self.logger.warning(f"⚠ Metot 2: Yakınsama sağlanamadı ({max_iter} iter).")
        z_avg_final = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)
        r_specific = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
        n_final = (k2 - 1) / (k2 * poly_eff)
        poly_head = (
            (
                z_avg_final
                * r_specific
                * t_in
                * (1.0 / n_final)
                * (math.pow(p_out / p_in, n_final) - 1.0)
            )
            / 1000.0
            if abs(n_final) > 1e-10
            else 0.0
        )
        return t2_guess, poly_head, z_avg_final, history

    def method_incremental_pressure(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=10):
        if step_count < 2:
            step_count = 10

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

            head_step = (
                z_step
                * r_specific
                * t_current
                * (1.0 / n_step)
                * (math.pow(p_end / p_start, n_step) - 1.0)
            ) / 1000.0
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

            max_iter = 30
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
                t2_guess = max(t_in * 1.001, min(t_in * 5.0, t2_guess))

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
                poly_head = (
                    z_avg
                    * r_specific
                    * t_in
                    * (1.0 / sigma)
                    * (math.pow(p_out / p_in, sigma) - 1.0)
                ) / 1000.0

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
        }

        self.logger.info(
            f"✓ Metot 4 (H-S) tamamlandı: T_out={t2_guess:.1f} K ({t2_guess-273.15:.1f}°C), "
            f"H_poly={poly_head:.2f} kJ/kg, η_isen={eta_isen:.4f}, "
            f"ΔH_isen={delta_h_isen/1000:.1f} kJ/kg, ΔH_actual={delta_h_actual/1000:.1f} kJ/kg"
        )

        return t2_guess, poly_head, z_avg, history

    def find_isentropic_temperature(self, p_in, t_in, p_out, s_target, gas_obj, eos, state_in):
        if eos == "coolprop":
            try:
                import CoolProp.CoolProp as CP

                t_isen = CP.PropsSI("T", "P", p_out, "Smass", s_target, gas_obj)
                if t_isen > 0 and t_isen < t_in * 10:
                    self.logger.debug(f"CoolProp izentropik flash: T_isen={t_isen:.1f} K")
                    return t_isen
            except Exception as error:
                self.logger.debug(f"CoolProp izentropik flash başarısız: {error}")

        k = state_in.k if state_in.k > 1.0 else 1.3
        n_isen = (k - 1) / k
        t_guess = t_in * math.pow(p_out / p_in, n_isen)

        for iteration in range(25):
            try:
                state_try = self.thermo_solver.get_properties(p_out, t_guess, gas_obj, eos)
                s_try = state_try.S
            except Exception:
                t_guess *= 1.01
                continue

            d_s = s_try - s_target
            if abs(d_s) < 5.0:
                self.logger.debug(f"İzentropik Newton yakınsadı: {iteration+1} iter, T={t_guess:.1f} K")
                return t_guess

            d_s_d_t = state_try.Cp / t_guess if state_try.Cp > 0 else 2.0
            if abs(d_s_d_t) < 1e-10:
                d_s_d_t = 2.0

            delta = -d_s / d_s_d_t
            delta = max(-30.0, min(30.0, delta))
            t_guess += 0.7 * delta
            t_guess = max(t_in * 0.9, min(t_in * 5.0, t_guess))

        self.logger.warning(f"⚠ İzentropik T tam yakınsayamadı, son T={t_guess:.1f} K")
        return t_guess
