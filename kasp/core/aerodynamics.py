"""
KASP V4.4 Compressor Aerodynamics
Kompresör politropik head, efficiency (verim) ve izentropik deşarj sıcaklıklarını
hesaplayan, ayrıca aerodinamik ve mekanik kayıpları içeren modül.
"""

import math
import logging
import numpy as np
import threading
import time

_local_storage = threading.local()

def reset_fallback_comparisons():
    _local_storage.comparisons = []
    _local_storage.current_stage = "Performans"

def add_fallback_comparison(comparison):
    if not hasattr(_local_storage, "comparisons"):
        _local_storage.comparisons = []
    _local_storage.comparisons.append(comparison)

def get_fallback_comparisons():
    return getattr(_local_storage, "comparisons", [])

def set_current_stage(stage):
    _local_storage.current_stage = stage

def get_current_stage():
    return getattr(_local_storage, "current_stage", "Performans")

# V4.4 Data Models
from kasp.core.models import ThermodynamicState, EnginePerformanceResult
from kasp.core.settings import EngineSettings

logger = logging.getLogger(__name__)

class CompressorAerodynamics:
    """Kompresör sıkıştırma işlemi, verimler ve head hesaplayıcı sınıf"""

    @staticmethod
    def calculate_isentropic_outlet_temp(state_in: ThermodynamicState, p_out: float,
                                         thermo_solver, gas_obj, eos: str) -> float:
        """
        Belirtilen çıkış basıncı (p_out) için Teorik İzentropik Sıcaklığı (T_out_isen) hesaplar.
        """
        try:
            if eos == 'coolprop':
                import CoolProp.CoolProp as CP
                return CP.PropsSI('T', 'P', p_out, 'Smass', state_in.S, gas_obj)
        except Exception as e:
            logger.debug(f"Direct CoolProp flash failed ({e}). Proceeding to fallback.")

        try:
            if eos == 'coolprop':
                from CoolProp import AbstractState
                AS = AbstractState("HEOS", gas_obj)
                AS.update(CP.PSmass_INPUTS, p_out, state_in.S)
                return AS.T()
        except Exception as e2:
            logger.debug(f"AbstractState isentropic flash failed ({e2}). Using k-based fallback.")

        k = state_in.k
        if k <= 1.0:
            k = 1.3

        n_isen = (k - 1) / k
        t_out_isen = state_in.T * math.pow((p_out / state_in.P), n_isen)

        return t_out_isen

    @staticmethod
    def calculate_polytropic_efficiency(state_in: ThermodynamicState,
                                        state_out: ThermodynamicState,
                                        R_specific: float) -> float:
        """
        Giriş ve Çıkış koşulları (Test/Gerçek) bilindiğinde Politropik Verimi hesaplar.
        API 617 Standardına göre logaritmik formulasyon kullanır.
        """
        if state_in.P <= 0 or state_out.P <= 0 or state_in.T <= 0 or state_out.T <= 0:
            return 0.0
            
        if abs(state_out.P - state_in.P) < 1e-5:
            return 0.0  # İş yok
            
        delta_H = state_out.H - state_in.H
        if delta_H <= 0:
            return 0.0  # Kompresör işi pozitiftir
            
        ln_TR = math.log(state_out.T / state_in.T)
        ln_PR = math.log(state_out.P / state_in.P)
        
        if abs(ln_PR) < 1e-10:
            return 0.0
            
        sigma = ln_TR / ln_PR # (n-1)/n
        
        # Z average (Logarithmic per ASME PTC 10)
        Z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(state_in.Z, state_out.Z)
        
        if abs(sigma) < 1e-5:
             # Isothermal limit
             poly_head = Z_avg * R_specific * state_in.T * ln_PR
        else:
             poly_head = (1.0 / sigma) * Z_avg * R_specific * state_in.T * (math.pow(state_out.P / state_in.P, sigma) - 1.0)
             
        poly_efficiency = poly_head / delta_H
        return max(0.0, min(1.0, poly_efficiency))

    @staticmethod
    def _calculate_z_average_logarithmic(z_in: float, z_out: float) -> float:
        """ASME PTC 10 Logaritmik Sıkıştırılabilirlik Ortalaması"""
        if abs(z_out - z_in) < 1e-6:
             return (z_in + z_out) / 2.0
        try:
             return (z_out - z_in) / math.log(z_out / z_in)
        except (ValueError, ZeroDivisionError):
             return (z_in + z_out) / 2.0

    @staticmethod
    def calculate_mechanical_loss(inlet_vol_flow_m3s: float, shaft_power_kw: float = None) -> float:
        """
        ASME PTC 10 uyumlu Mekanik (Rulman/Conta) kayıp tahmini.
        ExxonMobil merkezkaç kompresör ampirik formülü.
        Limitation: Kayıp şaft gücünün %10'unu geçemez.
        """
        acmh_unit = max(1.0, inlet_vol_flow_m3s * 3600.0)
        
        loss_kw = EngineSettings.MECHANICAL_LOSS_COEFF * math.pow(
            acmh_unit, EngineSettings.MECHANICAL_LOSS_EXPONENT
        )
        loss_kw = max(EngineSettings.MECHANICAL_LOSS_MIN_KW, loss_kw)
        
        limit_pct = EngineSettings.PTC10_MECHANICAL_LOSS_LIMIT / 100.0 # 0.10
        
        if shaft_power_kw is not None and shaft_power_kw > 0.0:
            max_allowed_loss = shaft_power_kw * limit_pct
            if loss_kw > max_allowed_loss:
                logger.debug(f"Mekanik kayıp sınırlandırıldı: {loss_kw:.1f}x -> {max_allowed_loss:.1f}")
                loss_kw = max_allowed_loss
                
        return loss_kw

    @staticmethod
    def calculate_thermal_efficiency(heat_rate_kj_kwh: float) -> float:
        """Isıl değerin güce dönüşümü (Temel Termodinami 2.Yasa Verimi)"""
        # 1 kWh = 3600 kJ
        # Verim = 3600 / HeatRate
        if heat_rate_kj_kwh <= 0: return 0.0
        therm_eff = 3600.0 / heat_rate_kj_kwh
        return max(0.0, min(1.0, therm_eff))

    @staticmethod
    def calculate_dimensionless_coeffs(results, inlet_props, mass_flow_kgs):
        try:
            head_j_kg = float(results.get("head_kj_kg", 0)) * 1000.0
            rho = float(inlet_props.get("rho", 1.2))
            a_sound = float(inlet_props.get("a", 340.0))
            mu = float(inlet_props.get("mu", 1.8e-5))

            D_ref = 0.5
            U_est = max(10.0, (head_j_kg / 0.55) ** 0.5)
            RPM_est = (U_est * 60.0) / (3.1416 * D_ref)

            psi = head_j_kg / (U_est ** 2) if U_est > 0 else 0
            Q_m3s = mass_flow_kgs / rho if rho > 0 else 0
            phi = Q_m3s / (U_est * (D_ref ** 2)) if U_est > 0 else 0
            Re = (rho * U_est * D_ref) / mu if mu > 0 else 0
            Ma = U_est / a_sound if a_sound > 0 else 0

            return {
                "psi": round(psi, 4),
                "phi": round(phi, 4),
                "Re": f"{Re:.2e}",
                "Ma": round(Ma, 3),
                "U_est_m_s": round(U_est, 1),
                "RPM_est": str(int(round(RPM_est))),
            }
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # API 617 APPENDIX C — Sayısal İntegrasyon & İsentropik Fallback
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_polytropic_exponent_integral(
        p_in: float, t_in: float, p_out: float,
        poly_eff: float, thermo_solver, gas_obj, eos: str,
        steps: int = 20
    ):
        """
        API 617 Appendix C: Politropik üs sayısal integrasyon ile hesabı.

        PR > EngineSettings.PR_INTEGRATION_THRESHOLD (4.0) olduğunda daha
        doğru sonuç verir; k ve Z değerlerini yol boyunca hesaplar.

        Args:
            p_in, t_in, p_out : Giriş ve çıkış koşulları (Pa, K)
            poly_eff          : Politropik verim (0–1)
            thermo_solver     : ThermodynamicSolver örneği
            gas_obj           : CoolProp string veya Thermo dict
            eos               : 'coolprop', 'pr', 'srk'
            steps             : İntegrasyon adım sayısı (10–50, varsayılan 20)

        Returns:
            tuple: (n_minus_1_over_n, k_integral, analysis_data)
                - n_minus_1_over_n : Entegre politropik üs katsayısı
                - k_integral       : Basınç ağırlıklı ortalama özgül ısı oranı
                - analysis_data    : Tanı verisi (dict)
        """
        steps = max(10, min(50, steps))

        # Geometrik basınç adımları (üstel sıkıştırma için daha uygun)
        pressures = np.geomspace(p_in, p_out, steps + 1)

        k_values = []
        temperatures = []
        z_factors = []
        t_current = t_in

        for i in range(steps):
            p_start = pressures[i]
            p_end   = pressures[i + 1]
            p_mid   = np.sqrt(p_start * p_end)  # Geometrik orta nokta

            try:
                state_mid = thermo_solver.get_properties(p_mid, t_current, gas_obj, eos)
                k_mid = state_mid.k
                z_mid = state_mid.Z
            except Exception:
                k_mid = k_values[-1] if k_values else 1.4
                z_mid = 1.0
                logger.warning(f"İntegral adım {i}: özellik hesabı başarısız, fallback k={k_mid:.4f}")

            k_values.append(k_mid)
            z_factors.append(z_mid)
            temperatures.append(t_current)

            # Sonraki adım için sıcaklığı güncelle
            n_step = (k_mid - 1) / (k_mid * poly_eff)
            t_current = t_current * (p_end / p_start) ** n_step

        # Basınç farkına göre ağırlıklı ortalama k (ASME PTC 10 uyumlu)
        pressure_diffs = np.diff(pressures)
        weights = pressure_diffs / np.sum(pressure_diffs)
        k_integral = float(np.average(k_values, weights=weights))

        n_minus_1_over_n = (k_integral - 1) / (k_integral * poly_eff)

        analysis_data = {
            'pressures':      pressures.tolist(),
            'k_values':       k_values,
            'temperatures':   temperatures,
            'z_factors':      z_factors,
            'k_min':          min(k_values),
            'k_max':          max(k_values),
            'k_range_percent': ((max(k_values) - min(k_values)) / np.mean(k_values)) * 100,
            'steps_used':     steps,
        }

        logger.debug(
            f"API 617 İntegral: k_integral={k_integral:.4f}, "
            f"k_range={analysis_data['k_range_percent']:.2f}%, steps={steps}"
        )
        return n_minus_1_over_n, k_integral, analysis_data

    @staticmethod
    def calculate_isentropic_temp_fd_nr(
        state_in: ThermodynamicState, p_out: float,
        thermo_solver, gas_obj, eos: str
    ) -> tuple:
        """Finite Difference Newton-Raphson Solver"""
        S1    = state_in.S
        k_avg = state_in.k
        p_in  = state_in.P
        t_in  = state_in.T

        # İlk tahmin: politropik ilişki
        n_isen    = (k_avg - 1) / k_avg if k_avg > 1.0 else 0.2308
        t2_guess  = t_in * (p_out / p_in) ** n_isen

        max_iter          = 20
        tolerance_entropy = 5.0   # J/kg/K
        tolerance_temp    = 0.5    # K
        t2_prev           = t2_guess
        
        iter_count = 0
        residual = 999.0

        for i in range(max_iter):
            iter_count += 1
            try:
                state2 = thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                S2     = state2.S
            except Exception:
                break

            dS = S2 - S1
            residual = abs(dS)

            if residual < tolerance_entropy:
                if i > 0 and abs(t2_guess - t2_prev) < tolerance_temp:
                    break
                elif i == 0:
                    break

            t2_prev = t2_guess

            # Sayısal türev (dS/dT)
            dT = 1.0
            try:
                state2p = thermo_solver.get_properties(p_out, t2_guess + dT, gas_obj, eos)
                dS_dT   = (state2p.S - S2) / dT
            except Exception:
                dS_dT = 1.0  # Güvenli fallback

            if abs(dS_dT) < 1e-10:
                break

            # Newton adımı ve fiziksel sınırlar
            t2_guess = t2_guess - dS / dS_dT
            t2_guess = max(100.0, min(2000.0, t2_guess))

        return t2_guess, iter_count, residual

    @staticmethod
    def calculate_isentropic_temp_aj_nr(
        state_in: ThermodynamicState, p_out: float,
        thermo_solver, gas_obj, eos: str
    ) -> tuple:
        """Analytical Jacobian Newton-Raphson Solver using (dS/dT)_P = Cp/T"""
        S1    = state_in.S
        k_avg = state_in.k
        p_in  = state_in.P
        t_in  = state_in.T

        # İlk tahmin: politropik ilişki
        n_isen    = (k_avg - 1) / k_avg if k_avg > 1.0 else 0.2308
        t2_guess  = t_in * (p_out / p_in) ** n_isen

        max_iter          = 20
        tolerance_entropy = 5.0   # J/kg/K
        tolerance_temp    = 0.5    # K
        t2_prev           = t2_guess
        
        iter_count = 0
        residual = 999.0

        for i in range(max_iter):
            iter_count += 1
            try:
                state2 = thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                S2     = state2.S
            except Exception:
                break

            dS = S2 - S1
            residual = abs(dS)

            if residual < tolerance_entropy:
                if i > 0 and abs(t2_guess - t2_prev) < tolerance_temp:
                    break
                elif i == 0:
                    break

            t2_prev = t2_guess

            # Analitik türev: dS_dT = Cp / T (burada Cp J/kg-K cinsindedir)
            dS_dT = state2.Cp / t2_guess if state2.Cp > 0 else 2.0
            if abs(dS_dT) < 1e-10:
                dS_dT = 2.0

            # Newton adımı (stabilite için 0.9 damping faktörü eklendi)
            t2_guess = t2_guess - 0.9 * (dS / dS_dT)
            t2_guess = max(100.0, min(2000.0, t2_guess))

        return t2_guess, iter_count, residual

    @staticmethod
    def calculate_isentropic_temp_brent(
        state_in: ThermodynamicState, p_out: float,
        thermo_solver, gas_obj, eos: str
    ) -> tuple:
        """Brent's Hybrid Root-Finding Solver (Pure Python)"""
        S1 = state_in.S
        t_in = state_in.T

        def f(t):
            try:
                state = thermo_solver.get_properties(p_out, t, gas_obj, eos)
                return state.S - S1
            except Exception:
                if t < t_in:
                    return -1e6
                else:
                    return 1e6

        # Başlangıç braketi bulma (T2 >= T1 için kompresörde a = t_in)
        a = t_in
        b = min(2500.0, t_in * 2.0)
        fa = f(a)
        fb = f(b)

        for _ in range(5):
            if fa * fb < 0:
                break
            if fa > 0:
                a = max(100.0, a * 0.5)
                fa = f(a)
            if fb < 0:
                b = min(3000.0, b * 1.5)
                fb = f(b)

        if fa * fb >= 0:
            # Braket başarısız — bisection stratejisi ile en iyi tahmini bul
            left, right = min(a, b), max(a, b)
            best_t, best_res = (a, abs(fa)) if abs(fa) < abs(fb) else (b, abs(fb))
            for _ in range(8):
                mid = (left + right) / 2.0
                fmid = abs(f(mid))
                if fmid < best_res:
                    best_t, best_res = mid, fmid
                if f(mid) > 0:
                    right = mid
                else:
                    left = mid
            return best_t, 1, best_res

        # Brent Algoritması
        max_iter = 20
        tol = 5.0 # Entropi toleransı
        c = a
        fc = fa
        d = b - a
        e = d
        iter_count = 0
        residual = 999.0

        for iteration in range(max_iter):
            iter_count += 1
            if abs(fc) < abs(fb):
                a, b, c = b, c, b
                fa, fb, fc = fb, fc, fb

            residual = abs(fb)
            if residual < tol:
                break

            m = 0.5 * (c - b)
            if abs(m) < 0.1:
                break

            if abs(e) >= 0.1 and abs(fa) > abs(fb):
                s = fb / fa
                if a == c:
                    p = 2.0 * m * s
                    q = 1.0 - s
                else:
                    q = fa / fc
                    r = fb / fc
                    p = s * (2.0 * m * q * (q - r) - (b - a) * (r - 1.0))
                    q = (q - 1.0) * (r - 1.0) * (s - 1.0)

                if p > 0:
                    q = -q
                else:
                    p = -p

                if 2.0 * p < min(3.0 * m * q - abs(0.1 * q), abs(e * q)):
                    e = d
                    d = p / q
                else:
                    d = m
                    e = d
            else:
                d = m
                e = d

            a = b
            fa = fb

            if abs(d) > 0.1:
                b += d
            else:
                b += 0.1 if m > 0 else -0.1

            fb = f(b)

            if (fb > 0 and fc > 0) or (fb < 0 and fc < 0):
                c = a
                fc = fa
                d = b - a
                e = d

        return b, iter_count, residual

    @staticmethod
    def run_isentropic_fallback_comparison(
        state_in: ThermodynamicState, p_out: float,
        thermo_solver, gas_obj, eos: str
    ) -> float:
        """Her üç metodu da koşturarak karşılaştırır ve aralarındaki farkı raporlar."""
        stage = get_current_stage()

        # 1. FD-NR
        t0 = time.perf_counter()
        t_fd, iter_fd, res_fd = CompressorAerodynamics.calculate_isentropic_temp_fd_nr(
            state_in, p_out, thermo_solver, gas_obj, eos
        )
        dt_fd = (time.perf_counter() - t0) * 1000.0

        # 2. AJ-NR
        t0 = time.perf_counter()
        t_aj, iter_aj, res_aj = CompressorAerodynamics.calculate_isentropic_temp_aj_nr(
            state_in, p_out, thermo_solver, gas_obj, eos
        )
        dt_aj = (time.perf_counter() - t0) * 1000.0

        # 3. Brent
        t0 = time.perf_counter()
        t_brent, iter_brent, res_brent = CompressorAerodynamics.calculate_isentropic_temp_brent(
            state_in, p_out, thermo_solver, gas_obj, eos
        )
        dt_brent = (time.perf_counter() - t0) * 1000.0

        # Karşılaştırma verisini kaydet
        comparison = {
            "stage": stage,
            "methods": [
                {
                    "name": "Sonlu Farklar NR (FD-NR)",
                    "temp_k": t_fd,
                    "iterations": iter_fd,
                    "residual": res_fd,
                    "time_ms": dt_fd
                },
                {
                    "name": "Analitik Jacobian NR (AJ-NR)",
                    "temp_k": t_aj,
                    "iterations": iter_aj,
                    "residual": res_aj,
                    "time_ms": dt_aj
                },
                {
                    "name": "Brent Metodu (Brent)",
                    "temp_k": t_brent,
                    "iterations": iter_brent,
                    "residual": res_brent,
                    "time_ms": dt_brent
                }
            ]
        }
        add_fallback_comparison(comparison)

        logger.info(
            f"Fallback Benchmark [{stage}] - "
            f"FD-NR: {t_fd:.2f}K ({iter_fd} iter, {dt_fd:.2f}ms), "
            f"AJ-NR: {t_aj:.2f}K ({iter_aj} iter, {dt_aj:.2f}ms), "
            f"Brent: {t_brent:.2f}K ({iter_brent} iter, {dt_brent:.2f}ms)"
        )

        # En güvenilir ve hızlı olan AJ-NR sonucunu birincil değer olarak dön
        return t_aj

    @staticmethod
    def calculate_isentropic_temp_fallback(
        state_in: ThermodynamicState, p_out: float,
        thermo_solver, gas_obj, eos: str
    ) -> float:
        # Retrieve selected root-finding solver from thread-local context
        solver_method = "auto"
        if hasattr(thermo_solver, "_run_tracking") and hasattr(thermo_solver._run_tracking, "context") and thermo_solver._run_tracking.context:
            solver_method = thermo_solver._run_tracking.context.get("solver_method", "auto")

        if solver_method == "aj_nr":
            t_aj, _, _ = CompressorAerodynamics.calculate_isentropic_temp_aj_nr(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
            return t_aj
        elif solver_method == "fd_nr":
            t_fd, _, _ = CompressorAerodynamics.calculate_isentropic_temp_fd_nr(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
            return t_fd
        elif solver_method == "brent":
            t_brent, _, _ = CompressorAerodynamics.calculate_isentropic_temp_brent(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
            return t_brent
        elif solver_method == "benchmark":
            return CompressorAerodynamics.run_isentropic_fallback_comparison(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
        else:
            # "auto" mod: Akilli sequential fallback + benchmark verisi topla
            from kasp.core.fallback import SolverChain
            tracker = getattr(thermo_solver, "_fallback_tracker", None)
            if tracker is not None:
                chain = SolverChain(tracker)
                result = chain.find_isentropic_temp(
                    state_in, p_out, thermo_solver, gas_obj, eos,
                    solver_method="auto",
                )
                # Benchmark verisini de arka planda topla (diagnostik icin)
                try:
                    CompressorAerodynamics.run_isentropic_fallback_comparison(
                        state_in, p_out, thermo_solver, gas_obj, eos
                    )
                except Exception:
                    pass
                return result
            # FallbackTracker yoksa eski benchmark davranisi
            return CompressorAerodynamics.run_isentropic_fallback_comparison(
                state_in, p_out, thermo_solver, gas_obj, eos
            )

