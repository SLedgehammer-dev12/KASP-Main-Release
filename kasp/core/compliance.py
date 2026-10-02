import numpy as np
import logging

logger = logging.getLogger(__name__)

class ASME_PTC10_Compliance:
    """ASME PTC-10 standartına uyum sınıfı"""
    
    @staticmethod
    def calculate_uncertainty(measured_values, instrument_accuracy):
        """Ölçüm belirsizliği hesaplama - ASME PTC 10 Appendix B (göreli-RSS, basitleştirilmiş).

        Not: Bu basitleştirilmiş yöntem duyarlılık katsayısı kullanmaz; canlı belirsizlik
        hesabı için kasp.core.uncertainty.UncertaintyAnalyzer kullanılmalıdır.
        """
        uncertainties = {}
        total_uncertainty = 0

        for param, value in measured_values.items():
            if value is None or value == 0:
                # Sıfır/bilinmeyen değerde göreli katkı tanımsız; güvenli tarafta 0 kabul et.
                uncertainties[param] = 0.0
                continue
            accuracy = instrument_accuracy.get(param, 0.01)  # Varsayılan %1
            uncertainty = value * accuracy
            uncertainties[param] = uncertainty
            total_uncertainty += (uncertainty / value) ** 2

        return np.sqrt(total_uncertainty)

    @staticmethod
    def calculate_reynolds_correction_factor(
        re_test: float,
        re_spec: float,
        b2_m: float = 0.02,
        ra_um: float = 1.6,
        x_fraction: float = 0.30,
        n_exp: float = 0.12,
    ) -> tuple[float, float, float]:
        """ASME PTC 10 Section 5.3 Reynolds Sayısı Düzeltme Katsayısı (RA, RB, RC Yöntemi).

        Formül:
            (1 - eta_spec) / (1 - eta_test) = (1 - X) + X * (RA_spec / RA_test) * (Re_test / Re_spec)^n

        Args:
            re_test: Test makine Reynolds sayısı.
            re_spec: Şartname/garanti makine Reynolds sayısı.
            b2_m: Çark kanadı çıkış genişliği (m).
            ra_um: Yüzey pürüzlülüğü Ra (mikrometre).
            x_fraction: Sürtünmeli kayıp oranı (ASME PTC 10 varsayılanı 0.30).
            n_exp: Reynolds üssü (tipik 0.10 - 0.20, varsayılan 0.12).

        Returns:
            (loss_ratio, ra_test, ra_spec)
        """
        re_t = max(1e3, float(re_test or 1e6))
        re_s = max(1e3, float(re_spec or 1e6))
        ra_m = max(0.01e-6, float(ra_um or 1.6) * 1e-6)
        b2 = max(0.001, float(b2_m or 0.02))

        # Yüzey pürüzlülüğü kriteri (PTC 10 Eq. 5.3-2)
        term_t = (4.8e6 * (b2 / ra_m)) / re_t
        term_s = (4.8e6 * (b2 / ra_m)) / re_s
        ra_test = min(1.0, max(0.1, 0.066 + 0.934 * (term_t ** n_exp))) if term_t > 0 else 1.0
        ra_spec = min(1.0, max(0.1, 0.066 + 0.934 * (term_s ** n_exp))) if term_s > 0 else 1.0

        roughness_ratio = (ra_spec / ra_test) if ra_test > 0 else 1.0
        re_ratio = (re_t / re_s) ** n_exp

        loss_ratio = (1.0 - x_fraction) + x_fraction * roughness_ratio * re_ratio
        return float(loss_ratio), float(ra_test), float(ra_spec)

    @staticmethod
    def check_test_validity(test_data: dict, spec_data: dict) -> dict:
        """ASME PTC 10 Tip 1 & Tip 2 kabul testi sınırları denetimi (Tablo 3.1 & 3.2)."""
        warnings = []
        is_valid = True

        vr_test = float(test_data.get("volume_ratio", 1.0) or 1.0)
        vr_spec = float(spec_data.get("volume_ratio", 1.0) or 1.0)
        vr_dev_pct = abs(vr_test - vr_spec) / vr_spec * 100.0 if vr_spec > 0 else 0.0

        test_type = test_data.get("test_type", "Type 2")
        vr_limit_pct = 4.0 if test_type == "Type 1" else 5.0
        if vr_dev_pct > vr_limit_pct:
            warnings.append(
                f"Hacim oranı sapması (%{vr_dev_pct:.2f}) izin verilen ASME PTC 10 sınırını (%{vr_limit_pct:.1f}) aşıyor."
            )
            is_valid = False

        mu_test = float(test_data.get("mach_number", 0.8) or 0.8)
        mu_spec = float(spec_data.get("mach_number", 0.8) or 0.8)
        mu_diff = abs(mu_test - mu_spec)
        mu_limit = 0.02 if test_type == "Type 1" else 0.05
        if mu_diff > mu_limit:
            warnings.append(
                f"Çark ucu Mach sayısı farkı ({mu_diff:.3f}) ASME PTC 10 sınırını ({mu_limit:.2f}) aşıyor."
            )
            is_valid = False

        re_test = float(test_data.get("reynolds_number", 1e6) or 1e6)
        if re_test < 1e5:
            warnings.append(
                f"Test makine Reynolds sayısı ({re_test:.2e}) ASME PTC 10 minimum limitinin (1.0e5) altında."
            )
            is_valid = False

        return {
            "test_type": test_type,
            "is_valid": is_valid,
            "volume_ratio_dev_pct": round(vr_dev_pct, 2),
            "mach_diff": round(mu_diff, 4),
            "warnings": warnings,
        }

    @staticmethod
    def performance_correction_to_standard_conditions(measured_performance, site_conditions):
        """Standart / garanti koşullarına düzeltme - ASME PTC 10 Section 5.3 (Reynolds & Mach).

        Test koşullarında ölçülen politropik kafa, verim ve güç değerlerini
        belirtilen saha koşullarına ASME PTC 10 benzeşim ve sürtünme modellerine göre dönüştürür.
        """
        corrected = measured_performance.copy()

        # Giriş verilerini normalize et (verim decimal 0.0 - 1.0)
        raw_eff = float(measured_performance.get("efficiency", 0.80) or 0.80)
        eff_test = raw_eff / 100.0 if raw_eff > 1.0 else raw_eff
        head_test = float(measured_performance.get("head", 0.0) or 0.0)

        speed_test = float(measured_performance.get("speed_rpm", site_conditions.get("speed_rpm", 3000.0)) or 3000.0)
        speed_spec = float(site_conditions.get("speed_rpm", speed_test) or speed_test)
        speed_ratio = speed_spec / speed_test if speed_test > 0 else 1.0

        re_test = float(measured_performance.get("reynolds_number", measured_performance.get("Re", 1e6)) or 1e6)
        re_spec = float(site_conditions.get("reynolds_number", site_conditions.get("Re", re_test)) or re_test)
        b2_m = float(site_conditions.get("b2_m", 0.02) or 0.02)
        ra_um = float(site_conditions.get("roughness_ra_um", 1.6) or 1.6)

        loss_ratio, ra_test, ra_spec = ASME_PTC10_Compliance.calculate_reynolds_correction_factor(
            re_test=re_test,
            re_spec=re_spec,
            b2_m=b2_m,
            ra_um=ra_um,
        )

        # ASME PTC 10 Eq. 5.3: eta_spec = 1 - (1 - eta_test) * loss_ratio
        eff_spec = max(0.1, min(0.99, 1.0 - (1.0 - eff_test) * loss_ratio))
        eff_ratio = eff_spec / eff_test if eff_test > 0 else 1.0

        # Head düzeltmesi: H_spec = H_test * (N_spec/N_test)^2 * (eta_spec/eta_test)
        head_spec = head_test * (speed_ratio ** 2) * eff_ratio

        # Güç düzeltmesi: P = (m_dot * H) / eta
        mass_flow = float(site_conditions.get("mass_flow_kgs", measured_performance.get("mass_flow_kgs", 10.0)) or 10.0)
        power_kw = (mass_flow * head_spec) / eff_spec if eff_spec > 0 else 0.0

        validity = ASME_PTC10_Compliance.check_test_validity(measured_performance, site_conditions)

        corrected["head"] = round(head_spec, 2)
        corrected["efficiency"] = round(eff_spec * 100.0 if raw_eff > 1.0 else eff_spec, 4)
        corrected["power_kw"] = round(power_kw, 2)
        corrected["reynolds_correction_factor"] = round(loss_ratio, 4)
        corrected["ra_test"] = round(ra_test, 4)
        corrected["ra_spec"] = round(ra_spec, 4)
        corrected["speed_ratio"] = round(speed_ratio, 4)
        corrected["ptc10_valid"] = validity["is_valid"]
        corrected["ptc10_warnings"] = validity["warnings"]
        corrected["analysis_scope"] = "COMPLIANT"

        return corrected

class API_617_Compliance:
    """API Standard 617 uyum sınıfı"""
    
    @staticmethod
    def lateral_critical_speed_analysis(rotor_data):
        """
        Yanal kritik hız analizi - API 617 Bölüm 2
        V4.3 Fix 10: Bu metot basitleştirilmiş Jeffcott Rotor modeli kullanıyor.
        'meets_api' sonucu her zaman True dönebilir; gerçek FEA analizi yapılmadıkça
        bu sonucu nihai kabul etmeyin.
        """
        logger.warning(
            "⚠️ API 617 Lateral Critical Speed: Basitleştirilmiş Jeffcott Rotor modeli kullanılıyor. "
            "Gerçek FEA/rotor dinamiği analizi yapılmamıştır; sonuçlar yalnızca gösterge niteliğindedir."
        )
        mass = rotor_data.get('mass', 100)
        stiffness = rotor_data.get('stiffness', 1e6)
        
        natural_frequency = (1 / (2 * np.pi)) * np.sqrt(stiffness / mass)
        critical_speed_rpm = natural_frequency * 60
        
        return {
            'first_critical_speed_rpm': critical_speed_rpm,
            'separation_margin': None,  # Hesaplanmamıştır (gerçek FEA gerekir)
            'meets_api': None,          # Bilinmiyor — gerçek analiz yapılmamıştır (True DEGIL)
            'not_implemented': True,  # V4.3: Gerçek FEA analizi henüz implement edilmedi
            'analysis_scope': 'NOT_IMPLEMENTED',
            'warning': 'Basitleştirilmiş Jeffcott Rotor modeli — gerçek API 617 analizinin yerini tutmaz; FEA analizi yapılmamıştır.'
        }

    @staticmethod
    def torsional_analysis(shaft_data):
        """
        Burulma vibrasyonu analizi - API 617 Bölüm 3
        V4.3 Fix 10: Stub metot — gerçek analiz implement edilmedi.
        """
        logger.warning(
            "⚠️ API 617 Torsional Analysis: Henüz implement edilmedi (NOT_IMPLEMENTED)."
        )
        return {
            'status': 'NOT_IMPLEMENTED',  # Gerçek analiz yapılmadıkça 'Pass' döndürülmez
            'stress_level': None,
            'not_implemented': True,
            'analysis_scope': 'NOT_IMPLEMENTED',
            'warning': 'Gerçek burulma analizi yapılmamıştır; bu sonuç gösterge niteliğindedir.'
        }
