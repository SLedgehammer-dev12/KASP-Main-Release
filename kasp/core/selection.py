"""
KASP V4.4 Turbine Selector
Gerekli proses kompresör gücüne en uygun türbini seçmek için API 617 tabanlı
Güç, Isıl Verim, Surge ve Tip kriterlerini ağırlıklandırarak (0-100) puanlayan 
karar destek motoru.
"""

import math
import logging
from typing import List, Dict, Any, Optional

# V4.4 Data Models & Settings
from kasp.core.models import TurbineRecommendation
from kasp.core.settings import EngineSettings

logger = logging.getLogger(__name__)

class TurbineSelector:
    """Türbinleri güç, verim ve aerodinamik analizlere göre derecelendiren sınıf."""
    
    @staticmethod
    def select_units(required_power_kw: float, site_conditions: Dict[str, float], 
                     all_turbines_data: List[Dict[str, Any]], limit: int = 5) -> List[TurbineRecommendation]:
        """
        Kayıtlı türbin listesini filtreler, saha düzeltmelerini yapar ve en uygun olanları sıralar.
        """
        selected_recommendations: List[TurbineRecommendation] = []
        
        ambient_temp = site_conditions.get('ambient_temp', 15.0)
        altitude = site_conditions.get('altitude', 0.0)
        ambient_pressure = site_conditions.get('ambient_pressure', 101.325)
        
        logger.info(
            f"Ünite seçimi (V4.4) başlatılıyor. Gerekli güç: {required_power_kw:.0f} kW | "
            f"Amb: {ambient_temp}°C / {altitude}m / {ambient_pressure} kPa"
        )
        
        for turbine in all_turbines_data:
            iso_power = turbine.get('iso_power_kw', 0)
            iso_heat_rate = turbine.get('iso_heat_rate_kj_kwh', 0)
            
            if iso_power <= 0 or iso_heat_rate <= 0:
                continue
                
            # 1. Saha koşullarına göre ISO -> Gerçek performans düzeltmesi
            corr_power, corr_hr, corr_source = TurbineSelector._correct_performance(
                iso_power, iso_heat_rate, ambient_temp, ambient_pressure, altitude, turbine
            )
            
            # 2. Ön Filtre (Sadece -%0 ile %150 aralığındaki türbinleri değerlendir)
            # Power Margin = (Available - Required) / Required * 100
            power_margin_pct = ((corr_power - required_power_kw) / required_power_kw) * 100
            
            # Negatif marjları (Yetersizleri) reddet (V4.3 mantığı) veya çok büyükleri reddet
            if power_margin_pct < 0.0 or power_margin_pct > EngineSettings.MAX_ALLOWED_OVERSIZE_PCT:
                continue
                
            # 3. Aerodinamik Güvenlik Marjları (Surge / Stonewall)
            aero_margins = TurbineSelector._calculate_aero_margins(turbine, site_conditions.get('flow'))
            sm_pct = aero_margins['surge_margin_pct']
            sw_pct = aero_margins['stonewall_margin_pct']
            
            # 4. Ağırlıklı Puanlama Algoritması
            score = TurbineSelector._calculate_turbine_score(
                turbine_type=turbine.get('type', 'Industrial'),
                corrected_heat_rate=corr_hr,
                power_margin_pct=power_margin_pct,
                surge_margin_pct=sm_pct,
                stonewall_margin_pct=sw_pct
            )
            
            # 5. Emniyet (API 617 Mins) — marj hesaplanamadiysa "bilinmiyor" (None) doner, sifir varsayilmaz
            if sm_pct is None or sw_pct is None:
                meets_api617 = None
            else:
                meets_api617 = (sm_pct >= EngineSettings.API617_MIN_SURGE_MARGIN and 
                                sw_pct >= EngineSettings.API617_MIN_STONEWALL_MARGIN)
                            
            # 6. Recommendation Objesi Oluştur
            rec = TurbineRecommendation(
                turbine_name=f"{turbine.get('manufacturer', 'Bilinmiyor')} {turbine.get('model', 'Bilinmiyor')}",
                manufacturer=turbine.get('manufacturer', 'Bilinmiyor'),
                model=turbine.get('model', 'Bilinmiyor'),
                type_str=turbine.get('type', 'Industrial'),
                iso_power_kw=iso_power,
                available_power_kw=corr_power,
                site_heat_rate=corr_hr,
                power_margin_percent=power_margin_pct,
                surge_margin_percent=sm_pct,
                stonewall_margin_percent=sw_pct,
                meets_api617_surge=meets_api617,
                selection_score=score,
                efficiency_rating=TurbineSelector._get_efficiency_rating(corr_hr),
                recommendation_level=TurbineSelector._get_recommendation_label(score),
                correction_source=corr_source,
            )
            selected_recommendations.append(rec)
            
        # Puan (Azalan) ve Güç Farkı (Artan) sıralaması
        selected_recommendations.sort(
            key=lambda x: (x.selection_score, -abs(x.power_margin_percent - 10.0)),
            reverse=True
        )
        
        return selected_recommendations[:limit]

    @staticmethod
    def _interpolate_curve(points, values, x):
        """Basit dogrusal interpolasyon; aralik disinda uc degerleri sabit tutulur."""
        if not points or not values or len(points) != len(values):
            return None
        try:
            x = float(x)
        except (TypeError, ValueError):
            return None
        if x <= points[0]:
            return values[0]
        if x >= points[-1]:
            return values[-1]
        for i in range(1, len(points)):
            if x <= points[i]:
                x0, x1 = points[i - 1], points[i]
                y0, y1 = values[i - 1], values[i]
                if x1 == x0:
                    return y1
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return values[-1]

    @staticmethod
    def _correct_performance(iso_power: float, iso_hr: float, t_amb: float, 
                             p_amb: float, alt: float, turbine_data: Dict[str, Any]):
        """Saha düzeltmelerini uygular. OEM egrileri varsa onlari, yoksa genel ISO formülünü kullanir.

        Returns:
            (corr_power, corr_hr, source) — source: 'oem_curve' veya 'generic_formula'
        """
        T_ref_k = 15.0 + 273.15
        T_amb_k = t_amb + 273.15
        corr_data = (turbine_data or {}).get("performance_correction_data") or {}
        temp_curve = corr_data.get("temperature_correction") or {}
        power_pf = TurbineSelector._interpolate_curve(
            temp_curve.get("points"), temp_curve.get("power_factor"), t_amb
        )
        hr_pf = TurbineSelector._interpolate_curve(
            temp_curve.get("points"), temp_curve.get("hr_factor"), t_amb
        )
        alt_curve = corr_data.get("altitude_correction") or {}
        alt_pf = TurbineSelector._interpolate_curve(
            alt_curve.get("points"), alt_curve.get("power_factor"), alt
        )
        alt_hrf = TurbineSelector._interpolate_curve(
            alt_curve.get("points"), alt_curve.get("hr_factor"), alt
        )

        if power_pf is not None and hr_pf is not None:
            # OEM egrileri mevcut: sicaklik + rakım egriden
            alt_factor = alt_pf if alt_pf is not None else 1.0
            hr_alt_factor = alt_hrf if alt_hrf is not None else 1.0
            power_factor = power_pf * alt_factor
            hr_factor = hr_pf * hr_alt_factor
            source = "oem_curve"
        else:
            # Egri yok: genel ISO tahmini. Ortam basinci acikca verilmisse rakım
            # etkisi zaten icindedir; ayrica carpmak cift sayma yapar (P1-7).
            if alt and abs(p_amb - 101.325) < 1e-6:
                pressure_ratio = (1.0 - 2.25577e-5 * max(0.0, min(float(alt), 11000.0))) ** 5.25588
            else:
                pressure_ratio = p_amb / 101.325
            power_factor = (T_ref_k / T_amb_k) * pressure_ratio
            hr_factor = T_amb_k / max(1e-9, T_ref_k)
            source = "generic_formula"

        corr_power = iso_power * power_factor
        corr_hr = iso_hr * hr_factor
        return corr_power, corr_hr, source

    @staticmethod
    def _is_placeholder_bounds(min_val, max_val) -> bool:
        try:
            mn = float(min_val or 0.0)
            mx = float(max_val or 0.0)
        except (TypeError, ValueError):
            return True
        if mx <= 0:
            return True
        return mn == 0.0 and mx in (500.0, 1000.0, 9999.0)

    @staticmethod
    def _calculate_aero_margins(turbine: Dict, op_flow: float) -> Dict[str, float]:
        """API 617 Surge ve Choke oranlarını hesaplar.

        Debi veya surge verisi yoksa (veya placeholder 0/1000/9999 ise) marj hesaplanamaz;
        sifir varsaymak yerine None dondurulur (P1-7).
        """
        surge_flow = turbine.get('surge_flow', 0)
        stonewall_flow = turbine.get('stonewall_flow', 0)
        min_flow = turbine.get('min_flow_kgs')
        max_flow = turbine.get('max_flow_kgs')

        if TurbineSelector._is_placeholder_bounds(surge_flow, stonewall_flow):
            surge_flow = 0
            stonewall_flow = 0
        if min_flow is not None and max_flow is not None:
            if TurbineSelector._is_placeholder_bounds(min_flow, max_flow):
                min_flow = 0
                max_flow = 0
                surge_flow = 0
                stonewall_flow = 0

        # Mikro-ölçek veya geçersiz debi kontrolü
        if surge_flow and surge_flow <= 0.05:
            surge_flow = 0
        if stonewall_flow and stonewall_flow <= 0.05:
            stonewall_flow = 0

        if not op_flow or op_flow <= 0 or not surge_flow or surge_flow <= 0:
            return {'surge_margin_pct': None, 'stonewall_margin_pct': None, 'available': False}

        # Eğer işletme debisi boğulma debisinin (stonewall) aşırı üzerindeyse veri uyumsuzdur
        if stonewall_flow and stonewall_flow > 0 and op_flow > 2.0 * stonewall_flow:
            return {'surge_margin_pct': None, 'stonewall_margin_pct': None, 'available': False}

        surge_margin = ((op_flow - surge_flow) / surge_flow) * 100.0
        # Standart dışı aşırı sapmalarda (örn. > 500%) marjı geçersiz kıl
        if surge_margin > 500.0:
            surge_margin = None

        stonewall_margin = (
            ((stonewall_flow - op_flow) / op_flow * 100.0)
            if (stonewall_flow and stonewall_flow > 0 and stonewall_flow not in (500, 1000, 9999))
            else None
        )

        return {
            'surge_margin_pct': surge_margin, 
            'stonewall_margin_pct': stonewall_margin,
            'available': (surge_margin is not None and stonewall_margin is not None),
        }

    @staticmethod
    def _calculate_turbine_score(turbine_type: str, corrected_heat_rate: float,
                                 power_margin_pct: float, surge_margin_pct: float, 
                                 stonewall_margin_pct: float) -> float:
        """
        EngineSettings sabitlerini kullanarak 0-100 arasında normalize bir skor üretir.
        """
        # 1. GÜÇ MARJI SKORU (0-100)
        pm = power_margin_pct
        if pm < 0:
             power_score = max(0.0, 50.0 + pm * 5.0)
        elif pm <= EngineSettings.OPTIMAL_OVERSIZE_MIN:
             power_score = 60.0 + pm * 4.0
        elif pm <= EngineSettings.OPTIMAL_OVERSIZE_MAX:
             power_score = 100.0 - (pm - EngineSettings.OPTIMAL_OVERSIZE_MIN) * 1.33
        elif pm <= 35:
             power_score = 80.0 - (pm - EngineSettings.OPTIMAL_OVERSIZE_MAX) * 2.0
        elif pm <= EngineSettings.MAX_ALLOWED_OVERSIZE_PCT:
             power_score = 50.0 - (pm - 35) * 1.5
        else:
             power_score = max(0.0, 25.0 - (pm - 50) * 0.5)

        # 2. ISI ORANI SKORU
        eff_score = max(0.0, (EngineSettings.HR_REF_WORST - corrected_heat_rate) / 
                        (EngineSettings.HR_REF_WORST - EngineSettings.HR_REF_BEST) * 100.0)
        # Referans araligin disinda 100'u asmasin (P1-8)
        eff_score = min(100.0, eff_score)
                        
        # 3. SURGE SKORU (marj hesaplanamadiysa notr skor)
        if surge_margin_pct is None:
            surge_score = 60.0
        else:
            sm = max(0.0, surge_margin_pct)
            if sm >= 20.0:
                surge_score = 100.0
            elif sm >= 10.0:
                surge_score = 80.0 + (sm - 10.0) * 2.0
            elif sm > 0:
                surge_score = sm * 8.0
            else:
                surge_score = 0.0
            
        sw = stonewall_margin_pct
        if sw is not None and sw < 5.0:
            stonewall_penalty = (5.0 - sw) * 4.0
            surge_score = max(0.0, surge_score - stonewall_penalty)

        # 4. TİP SKORU
        type_score = EngineSettings.TURBINE_TYPE_SCORES.get(turbine_type, 65)

        # TOTAL AĞIRLIKLANDIRMA
        total_score = (
            power_score * EngineSettings.SCORE_WEIGHT_POWER +
            eff_score   * EngineSettings.SCORE_WEIGHT_EFFICIENCY +
            surge_score * EngineSettings.SCORE_WEIGHT_SURGE +
            type_score  * EngineSettings.SCORE_WEIGHT_TYPE
        )
        # Sozlesme: skor 0-100 araliginda normalize (P1-8)
        return round(max(0.0, min(100.0, total_score)), 1)

    @staticmethod
    def _get_efficiency_rating(heat_rate: float) -> str:
        if heat_rate <= 8500: return 'Çok Yüksek'
        elif heat_rate <= 9500: return 'Yüksek'
        elif heat_rate <= 10500: return 'Orta'
        elif heat_rate <= 11500: return 'Düşük'
        else: return 'Çok Düşük'

    @staticmethod
    def _get_recommendation_label(score: float) -> str:
        if score >= 90: return 'Çok Önerilen'
        elif score >= 80: return 'Önerilen'
        elif score >= 70: return 'Kabul Edilebilir'
        elif score >= 60: return 'Sınırda'
        else: return 'Önerilmez'
