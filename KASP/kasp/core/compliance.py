import numpy as np
import logging

logger = logging.getLogger(__name__)

class ASME_PTC10_Compliance:
    """ASME PTC-10 standartına uyum sınıfı"""
    
    @staticmethod
    def calculate_uncertainty(measured_values, instrument_accuracy):
        """Ölçüm belirsizliği hesaplama - ASME PTC 10 Appendix B"""
        uncertainties = {}
        total_uncertainty = 0
        
        for param, value in measured_values.items():
            accuracy = instrument_accuracy.get(param, 0.01) # Varsayılan %1
            uncertainty = value * accuracy
            uncertainties[param] = uncertainty
            total_uncertainty += (uncertainty / value) ** 2
            
        return np.sqrt(total_uncertainty)

    @staticmethod
    def performance_correction_to_standard_conditions(measured_performance, site_conditions):
        """Standart koşullara düzeltme - ASME PTC 10 Section 5.3"""
        logger.warning(
            "⚠️ ASME PTC 10 Reynolds/Mach düzeltmeleri henüz implement edilmedi. "
            "Düzeltme faktörleri 1.0 olarak kullanılıyor."
        )
        
        # Basitleştirilmiş düzeltme faktörleri (Placeholder)
        reynolds_correction = 1.0
        mach_correction = 1.0
        
        corrected_performance = measured_performance.copy()
        corrected_performance['head'] *= reynolds_correction
        corrected_performance['efficiency'] *= mach_correction
        
        return corrected_performance

def check_ptc10_similarity(ref_dim, test_dim):
    """ASME PTC 10 benzerlik limitleri (ccp/similarity.py uyarlamasi).

    Parameters
    ----------
    ref_dim : dict
        Referans nokta boyutsuz katsayilari (psi, phi, Ma, Re, volume_ratio).
    test_dim : dict
        Test noktasi boyutsuz katsayilari.

    Returns
    -------
    dict
        check_results: her parametre icin gecme durumu ve mesaj.
    """
    results = {}
    all_ok = True

    if ref_dim.get("phi", 0) > 0 and test_dim.get("phi", 0) > 0:
        phi_ratio = test_dim["phi"] / ref_dim["phi"]
        phi_ok = 0.96 <= phi_ratio <= 1.04
        results["phi"] = {
            "value": phi_ratio,
            "ok": phi_ok,
            "range": "(0.96 - 1.04)",
        }
        if not phi_ok:
            all_ok = False
    else:
        results["phi"] = {"value": None, "ok": False, "range": "(0.96 - 1.04)"}

    vr_test = test_dim.get("volume_ratio", test_dim.get("phi", 0))
    vr_ref = ref_dim.get("volume_ratio", ref_dim.get("phi", 0))
    if vr_ref > 0 and vr_test > 0:
        vr_ratio = vr_test / vr_ref
        vr_ok = 0.95 <= vr_ratio <= 1.05
        results["volume_ratio"] = {"value": vr_ratio, "ok": vr_ok, "range": "(0.95 - 1.05)"}
        if not vr_ok:
            all_ok = False

    if ref_dim.get("Ma", -999) is not None and test_dim.get("Ma", -999) is not None:
        ma_diff = test_dim["Ma"] - ref_dim["Ma"]
        if ref_dim["Ma"] > 0.86:
            ma_ok = -0.042 <= ma_diff <= 0.07
            ma_range = "(-0.042 - 0.07)"
        elif ref_dim["Ma"] > 0.215:
            ma_ok = (0.266 * ref_dim["Ma"] - 0.271) <= ma_diff <= (-0.25 * ref_dim["Ma"] + 0.286)
            ma_range = "hesaplanmis aralik"
        else:
            ma_ok = -ref_dim["Ma"] <= ma_diff <= (-0.25 * ref_dim["Ma"] + 0.286)
            ma_range = "hesaplanmis aralik"
        results["mach"] = {"value": ma_diff, "ok": ma_ok, "range": ma_range}
        if not ma_ok:
            all_ok = False

    if ref_dim.get("Re", 0) > 9e4 and test_dim.get("Re", 0) > 9e4:
        re_ratio = test_dim["Re"] / ref_dim["Re"]
        x = (ref_dim["Re"] / 1e7) ** 0.3
        upper = min(100 ** x, 100) if ref_dim["Re"] < 1e7 else 100
        lower = max(0.01 ** x, 0.1) if ref_dim["Re"] < 1e6 else 0.1
        re_ok = lower <= re_ratio <= upper
        results["reynolds"] = {"value": re_ratio, "ok": re_ok, "range": f"({lower:.2f} - {upper:.0f})"}
        if not re_ok:
            all_ok = False

    results["all_ok"] = all_ok
    return results


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
            'separation_margin': 20,  # % API gerekliliği (hesaplanmış değil, varsayılan)
            'meets_api': True,        # UYARI: Gerçek analiz yapılmamıştır
            'not_implemented': True,  # V4.3: Gerçek FEA analizi henüz implement edilmedi
            'warning': 'Basitleştirilmiş model — gerçek API 617 analizinin yerini tutmaz.'
        }

    @staticmethod
    def torsional_analysis(shaft_data):
        """
        Burulma vibrasyonu analizi - API 617 Bölüm 3
        V4.3 Fix 10: Stub metot — gerçek analiz implement edilmedi.
        """
        logger.warning(
            "⚠️ API 617 Torsional Analysis: Henüz implement edilmedi. "
            "Sonuç her zaman 'Pass' dönecektir."
        )
        return {
            'status': 'Pass',
            'stress_level': 'Low',
            'not_implemented': True,
            'warning': 'Gerçek burulma analizi yapılmamıştır.'
        }
