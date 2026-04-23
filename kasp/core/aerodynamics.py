"""
KASP V4.4 Compressor Aerodynamics
Kompresör politropik head, efficiency (verim) ve izentropik deşarj sıcaklıklarını
hesaplayan, ayrıca aerodinamik ve mekanik kayıpları içeren modül.
"""

import math
import logging
import numpy as np

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
            # 1. CoolProp (Eğer mümkünse Direct Entropy-Pressure Flash)
            if eos == 'coolprop':
                import CoolProp.CoolProp as CP
                return CP.PropsSI('T', 'P', p_out, 'Smass', state_in.S, gas_obj)
        except Exception as e:
            logger.debug(f"Direct Isentropic Flash failed ({e}). Proceeding to fallback.")
            
        # 2. PR/SRK veya Fallback İzentropik Üs (k-1)/k 
        k = state_in.k
        if k <= 1.0:
            k = 1.3  # Güvenli fallback exponent
            
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
        ExxonMobil merkezkaç kompresör ampirik formülü: 0.65 * (ACMH)^0.45
        Limitation: Kayıp şaft gücünün %10'unu geçemez.
        """
        acmh_unit = max(1.0, inlet_vol_flow_m3s * 3600.0) # m3/h'a çevir
        
        loss_kw = 0.65 * math.pow(acmh_unit, 0.45)
        loss_kw = max(10.0, loss_kw) # Min kayıp limiti
        
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
    def calculate_isentropic_temp_fallback(
        state_in: ThermodynamicState, p_out: float,
        thermo_solver, gas_obj, eos: str
    ) -> float:
        """
        CoolProp entropi-basınç flash başarısız olduğunda Newton-Raphson
        iterasyonu ile isentropik çıkış sıcaklığını bulur.

        Args:
            state_in      : Giriş termodinamik durumu (ThermodynamicState)
            p_out         : Çıkış basıncı (Pa)
            thermo_solver : ThermodynamicSolver örneği
            gas_obj       : CoolProp string veya Thermo dict
            eos           : EOS metodu

        Returns:
            float: İsentropik çıkış sıcaklığı (K)
        """
        S1    = state_in.S
        k_avg = state_in.k
        p_in  = state_in.P
        t_in  = state_in.T

        # İlk tahmin: politropik ilişki
        n_isen    = (k_avg - 1) / k_avg if k_avg > 1.0 else 0.2308
        t2_guess  = t_in * (p_out / p_in) ** n_isen

        max_iter          = 20
        tolerance_entropy = 10.0   # J/kg/K
        tolerance_temp    = 0.5    # K
        t2_prev           = t2_guess

        for i in range(max_iter):
            try:
                state2 = thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                S2     = state2.S
            except Exception as e:
                logger.warning(f"İsentropik fallback adım {i}: özellik hesabı başarısız ({e})")
                break

            dS = S2 - S1

            if abs(dS) < tolerance_entropy:
                if i > 0 and abs(t2_guess - t2_prev) < tolerance_temp:
                    logger.debug(f"✓ İsentropik fallback yakınsadı: {i+1} iter, T2={t2_guess:.1f} K")
                    return t2_guess
                elif i == 0:
                    return t2_guess

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

        logger.warning(f"⚠ İsentropik fallback tam yakınsayamadı, son T2={t2_guess:.1f} K kullanılıyor")
        return t2_guess

