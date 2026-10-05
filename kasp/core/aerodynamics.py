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

# Run-bazli iptal sinyalleri: her hesaplama kosusu kendi iptal jetonunu tasir.
# Boylece bir isin iptali, ayni anda calisan diger isleri etkilemez (P4-13).
# Argumansiz cagrilar eski global davranisi korur (geriye uyumluluk).
_cancel_event = threading.Event()
_run_lock = threading.Lock()
_run_events: dict[str, threading.Event] = {}
_thread_run = threading.local()


def begin_calculation_run(run_id: str | None = None) -> str:
    """Yeni bir hesaplama kosusu baslatir ve run-ID dondurur.

    Cagiran thread'in run-ID'sine baglanir; `is_calculation_cancel_requested`
    bu thread'de artik yalnizca bu kosunun jetonunu kontrol eder.
    """
    import uuid

    rid = run_id or f"run-{uuid.uuid4().hex}"
    event = threading.Event()
    with _run_lock:
        _run_events[rid] = event
    _thread_run.run_id = rid
    _thread_run.event = event
    return rid


def end_calculation_run(run_id: str | None = None) -> None:
    """Hesaplama kosusunu kapatir ve jetonunu kayit defterinden siler."""
    rid = run_id or getattr(_thread_run, "run_id", None)
    if rid is None:
        return
    with _run_lock:
        _run_events.pop(rid, None)
    if getattr(_thread_run, "run_id", None) == rid:
        _thread_run.run_id = None
        _thread_run.event = None


def request_calculation_cancel(run_id: str | None = None) -> None:
    """Iptal ister. run_id verilirse yalnizca o kosu iptal edilir.

    run_id verilmezse (eski cagiricilar) global bayrak + tum aktif kosular
    isaretlenir; davranis onceki surumle aynidir.
    """
    if run_id is not None:
        with _run_lock:
            event = _run_events.get(run_id)
        if event is not None:
            event.set()
        return
    _cancel_event.set()
    with _run_lock:
        events = list(_run_events.values())
    for event in events:
        event.set()


def clear_calculation_cancel(run_id: str | None = None) -> None:
    """Iptal bayragini temizler. run_id verilirse yalnizca o kosu temizlenir."""
    if run_id is not None:
        with _run_lock:
            event = _run_events.get(run_id)
        if event is not None:
            event.clear()
        return
    _cancel_event.clear()
    event = getattr(_thread_run, "event", None)
    if event is not None:
        event.clear()


def is_calculation_cancel_requested() -> bool:
    """Cagiran thread'in kosusu (veya global bayrak) iptal istendi mi?"""
    event = getattr(_thread_run, "event", None)
    if event is not None and event.is_set():
        return True
    return _cancel_event.is_set()

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
                import CoolProp.CoolProp as CP
                from CoolProp import AbstractState
                AS = AbstractState("HEOS", gas_obj)
                AS.update(CP.PSmass_INPUTS, p_out, state_in.S)
                return AS.T()
        except Exception as e2:
            logger.debug(f"AbstractState isentropic flash failed ({e2}). Proceeding to Brent solver.")

        if thermo_solver is not None and gas_obj is not None:
            try:
                t_brent, _iters, residual = CompressorAerodynamics.calculate_isentropic_temp_brent(
                    state_in, p_out, thermo_solver, gas_obj, eos
                )
                if math.isfinite(t_brent) and residual < 10.0 and t_brent > 0:
                    return t_brent
            except Exception as e3:
                logger.debug(f"Brent isentropic solver failed ({e3}). Using k-based fallback.")

        k = state_in.k
        if k <= 1.0:
            k = 1.3

        n_isen = (k - 1) / k
        t_out_isen = state_in.T * math.pow((p_out / state_in.P), n_isen)

        return t_out_isen

    @staticmethod
    def calculate_schultz_factor(state_in: ThermodynamicState, state_out: ThermodynamicState,
                                 p_out: float, thermo_solver, gas_obj, eos: str, R_specific: float) -> float:
        """
        Calculates the Schultz polytropic head correction factor (f_t) per ASME PTC 10.
        """
        try:
            t_out_isen = CompressorAerodynamics.calculate_isentropic_temp_fallback(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
            state_isen = thermo_solver.get_properties(p_out, t_out_isen, gas_obj, eos)
            dh_isen = state_isen.H - state_in.H
            
            if dh_isen <= 0:
                return 1.0
                
            k1 = state_in.k
            if k1 <= 1.001:
                k1 = 1.3
                
            pressure_ratio = p_out / state_in.P
            if pressure_ratio <= 1.001:
                return 1.0
                
            # Ideal isentropic head
            k_exp = (k1 - 1.0) / k1
            h_isen_ideal = (1.0 / k_exp) * state_in.Z * R_specific * state_in.T * (math.pow(pressure_ratio, k_exp) - 1.0)
            
            # Isentropic head correction factor (f_s)
            f_s = dh_isen / h_isen_ideal if h_isen_ideal > 0 else 1.0
            
            # Polytropic temperature exponent sigma
            ln_TR = math.log(state_out.T / state_in.T)
            ln_PR = math.log(state_out.P / state_in.P)
            sigma = ln_TR / ln_PR if abs(ln_PR) > 1e-10 else k_exp
            
            # Schultz polytropic head correction factor (f_t)
            if abs(sigma) < 1e-5:
                # Isothermal limit: lim_{sigma->0} (PR^sigma - 1)/sigma = ln(PR)
                denom_iso = math.pow(pressure_ratio, k_exp) - 1.0
                f_t = f_s * (k_exp * ln_PR) / denom_iso if abs(denom_iso) > 1e-12 else f_s
            else:
                numerator = k_exp * (math.pow(pressure_ratio, sigma) - 1.0)
                denominator = sigma * (math.pow(pressure_ratio, k_exp) - 1.0)
                f_t = f_s * (numerator / denominator) if denominator > 0 else f_s
                
            # Clamp to physical range (typically between 0.85 and 1.15)
            return max(0.85, min(1.15, f_t))
        except Exception as e:
            logger.warning(f"Schultz correction factor calculation failed: {e}. Using 1.0.")
            return 1.0

    @staticmethod
    def calculate_polytropic_efficiency(state_in: ThermodynamicState,
                                        state_out: ThermodynamicState,
                                        R_specific: float,
                                        thermo_solver=None,
                                        gas_obj=None,
                                        eos: str = None) -> float:
        """
        Giriş ve Çıkış koşulları (Test/Gerçek) bilindiğinde Politropik Verimi hesaplar.
        ASME PTC 10 Schultz metodu ve API 617 logaritmik formülasyonunu kullanır.
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
             poly_head_ideal = Z_avg * R_specific * state_in.T * ln_PR
        else:
             poly_head_ideal = (1.0 / sigma) * Z_avg * R_specific * state_in.T * (math.pow(state_out.P / state_in.P, sigma) - 1.0)
             
        # Schultz düzeltme katsayısını uygula (ASME PTC 10)
        f_t = 1.0
        if thermo_solver is not None and gas_obj is not None and eos is not None:
             f_t = CompressorAerodynamics.calculate_schultz_factor(
                 state_in, state_out, state_out.P, thermo_solver, gas_obj, eos, R_specific
             )
             
        poly_head = f_t * poly_head_ideal
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
    def calculate_mechanical_loss(inlet_vol_flow_m3s: float, reference_power_kw: float = None) -> float:
        """
        Mekanik (Rulman/Conta) kayıp tahmini.
        Ampirik model (ExxonMobil merkezkaç kompresör formülasyonu): 0.65 * (ACMH)^0.45

        Args:
            inlet_vol_flow_m3s: Giriş hacimsel debisi (m³/s)
            reference_power_kw: Tavan için referans güç. Çağrılarda GAZ gücü verilir;
                tavan bu değerin %10'udur (KASP iç tasarım emniyet sınırı: EngineSettings.PTC10_MECHANICAL_LOSS_LIMIT).
                Not: ASME PTC 10 standardı genel bir ampirik kayıp formülü tanımlamaz;
                bu tavan sınırı endüstriyel uygulama ve KASP iç emniyeti amacıyla konulmuştur.

        Limitation: Kayıp, referans gücün %10'unu geçemez; küçük makinelerde taban 10 kW.
        """
        acmh_unit = max(1.0, inlet_vol_flow_m3s * 3600.0) # m3/h'a çevir

        loss_kw = 0.65 * math.pow(acmh_unit, 0.45)
        loss_kw = max(10.0, loss_kw) # Min kayıp limiti

        limit_pct = EngineSettings.PTC10_MECHANICAL_LOSS_LIMIT / 100.0 # 0.10

        if reference_power_kw is not None and reference_power_kw > 0.0:
            max_allowed_loss = reference_power_kw * limit_pct
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
            head_total_j_kg = float(results.get("head_kj_kg", 0)) * 1000.0
            num_stages = max(
                1,
                int(
                    results.get("num_stages")
                    or len(results.get("stages") or results.get("staged_results") or [])
                    or 1
                ),
            )
            head_stage_j_kg = head_total_j_kg / num_stages

            rho = float(inlet_props.get("rho", 1.2))
            a_sound = float(inlet_props.get("a", 340.0))
            mu = float(inlet_props.get("mu", 1.8e-5))

            Q_m3s = mass_flow_kgs / rho if rho > 0 else 0

            # Santrifüj çark ucu çevresel hızı (kademe başına kafa ve hedef ψ≈0.50 ile)
            psi_target = 0.50
            U_est = max(10.0, (head_stage_j_kg / psi_target) ** 0.5)

            # Dinamik çap tahmini: tipik φ (0.03-0.06) ve U (<=450 m/s) kısıtlarıyla
            if Q_m3s > 0 and U_est > 0:
                phi_target = 0.04  # orta aralık
                D_est = (Q_m3s / (U_est * phi_target)) ** 0.5
                # U kısıtı: tip speed <= 450 m/s (API 617 standart santrifüj çark sınırı)
                if U_est > 450.0:
                    U_est = 450.0
                    D_est = (Q_m3s / (U_est * phi_target)) ** 0.5
                # Çap sınırları: 0.15m - 1.8m (gerçekçi kompresör aralığı)
                D_ref = max(0.15, min(1.8, D_est))
            else:
                D_ref = 0.5  # fallback

            RPM_est = (U_est * 60.0) / (math.pi * D_ref)

            psi = head_stage_j_kg / (U_est ** 2) if U_est > 0 else 0.0
            phi = Q_m3s / (U_est * (D_ref ** 2)) if U_est > 0 and D_ref > 0 else 0.0
            Re = (rho * U_est * D_ref) / mu if mu > 0 else 0.0
            Ma = U_est / a_sound if a_sound > 0 else 0.0

            # Balje / Cordier boyutsuz parametreleri:
            # Ns (Özgül Hız): ω·√Q / H^(3/4)
            # Ds (Özgül Çap): D·H^(1/4) / √Q
            Ns = None
            Ds = None
            if head_stage_j_kg > 0 and Q_m3s > 0 and D_ref > 0:
                omega = (2.0 * U_est) / D_ref  # rad/s
                Ns = round((omega * math.sqrt(Q_m3s)) / (head_stage_j_kg ** 0.75), 3)
                Ds = round((D_ref * (head_stage_j_kg ** 0.25)) / math.sqrt(Q_m3s), 3)

            return {
                "psi": round(psi, 4),
                "phi": round(phi, 4),
                "Re": f"{Re:.2e}",
                "Ma": round(Ma, 3),
                "U_est_m_s": round(U_est, 1),
                "RPM_est": str(int(round(RPM_est))),
                "D_ref_m": round(D_ref, 3),
                "Ns": Ns if Ns is not None else "-",
                "Ds": Ds if Ds is not None else "-",
                "head_stage_kj_kg": round(head_stage_j_kg / 1000.0, 2),
                "num_stages": num_stages,
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
        try:
            poly_eff_val = float(poly_eff)
            if not math.isfinite(poly_eff_val):
                poly_eff_val = 0.75
        except (TypeError, ValueError):
            poly_eff_val = 0.75
        if 1.0 < poly_eff_val <= 100.0:
            poly_eff_val = poly_eff_val / 100.0
        poly_eff = max(0.10, min(0.999, poly_eff_val))

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
        """Brent's Hybrid Root-Finding Solver (using scipy.optimize.brentq with robust physical bracket expansion)"""
        from scipy.optimize import brentq

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

        # Başlangıç tahmini (T2 >= T1 için kompresörde a = t_in)
        k_est = state_in.k if (state_in.k and state_in.k > 1.0) else 1.3
        n_isen = (k_est - 1.0) / k_est
        pr = max(1.0001, p_out / max(1.0, state_in.P))
        t_est = t_in * (pr ** n_isen)
        a = t_in
        b = min(2500.0, max(t_in + 25.0, t_est * 1.25))
        fa = f(a)
        fb = f(b)

        # Sağlam fiziksel braket genişletme (İşaret değişimi sağlanana kadar)
        for _ in range(8):
            if fa * fb < 0 and abs(fa) < 1e5 and abs(fb) < 1e5:
                break
            if fa >= 0:
                a = max(80.0, a * 0.8)
                fa = f(a)
            if fb <= 0:
                b = min(3500.0, b + max(25.0, (b - t_in) * 0.6))
                fb = f(b)

        # Braket başarıyla bulunduysa C-seviyesi scipy brentq çalıştır
        if fa * fb < 0:
            try:
                root, res = brentq(f, a, b, xtol=1e-4, rtol=1e-4, maxiter=30, full_output=True)
                residual = abs(f(root))
                iter_count = max(1, getattr(res, "iterations", 5))
                return root, iter_count, residual
            except Exception as e:
                logger.warning(f"brentq çözücü hatası: {e}")

        # Braket bulunamadıysa veya brentq başarısız olduysa, AJ-NR kurtarması dene
        try:
            t_aj, iter_aj, res_aj = CompressorAerodynamics.calculate_isentropic_temp_aj_nr(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
            if res_aj is not None and res_aj < 50.0:
                return t_aj, iter_aj, res_aj
        except Exception:
            pass

        # Son çare: İdeal gaz tahmini ve gerçek residual ile dön (SolverChain yakalasın)
        t_fallback = max(t_in, t_est)
        try:
            st = thermo_solver.get_properties(p_out, t_fallback, gas_obj, eos)
            res_fallback = abs(st.S - S1)
        except Exception:
            res_fallback = 999.0
        return t_fallback, 1, res_fallback

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
        has_context = False
        solver_method = "auto"
        if hasattr(thermo_solver, "_run_tracking") and hasattr(thermo_solver._run_tracking, "context") and thermo_solver._run_tracking.context:
            solver_method = thermo_solver._run_tracking.context.get("solver_method", "auto")
            has_context = True

        if solver_method == "benchmark" or not has_context:
            return CompressorAerodynamics.run_isentropic_fallback_comparison(
                state_in, p_out, thermo_solver, gas_obj, eos
            )

        # Tum secimler SolverChain uzerinden gider; boylece artık dogrulanir (P0-3)
        from kasp.core.fallback import SolverChain
        tracker = getattr(thermo_solver, "_fallback_tracker", None)
        if tracker is not None:
            chain = SolverChain(tracker)
            return chain.find_isentropic_temp(
                state_in, p_out, thermo_solver, gas_obj, eos,
                solver_method=solver_method,
            )
        # FallbackTracker yoksa eski benchmark davranisi
        return CompressorAerodynamics.run_isentropic_fallback_comparison(
            state_in, p_out, thermo_solver, gas_obj, eos
        )

