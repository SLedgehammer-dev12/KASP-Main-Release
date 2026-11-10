"""Pure-Python Design Input Service for KASP.

Contains engineering presets, contextual guidance information,
and live process metric calculators (PR and delta-P).
"""

from __future__ import annotations

from typing import Dict, Any, List
from kasp.core.units import UnitSystem

ENGINEERING_PRESETS = [
    {
        "id": "natural_gas",
        "icon": "⚡",
        "title": "Doğal Gaz Boru Hattı",
        "subtitle": "50→75 bar, 2.0M Sm³/h",
        "inputs": {
            "p_in": 49.65,
            "p_in_unit": "bar(g)",
            "t_in": 19.0,
            "t_in_unit": "°C",
            "p_out": 75.0,
            "p_out_unit": "bar(a)",
            "flow": 1985000.0,
            "flow_unit": "Sm³/h",
            "num_units": 4,
            "num_stages": 2,
            "intercooler_t": 35.0,
            "intercooler_dp_pct": 1.5,
            "poly_eff": 80.0,
            "eos_model": "coolprop",
            "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
            "gas_comp": {
                "METHANE": 87.0,
                "ETHANE": 7.0,
                "PROPANE": 3.0,
                "NITROGEN": 1.5,
                "CARBONDIOXIDE": 1.5
            }
        }
    },
    {
        "id": "lng_boiloff",
        "icon": "❄️",
        "title": "LNG Boil-Off / Besleme",
        "subtitle": "30→80 bar, -20°C Kriyojenik",
        "inputs": {
            "p_in": 30.0,
            "p_in_unit": "bar(g)",
            "t_in": -20.0,
            "t_in_unit": "°C",
            "p_out": 80.0,
            "p_out_unit": "bar(a)",
            "flow": 1200000.0,
            "flow_unit": "Sm³/h",
            "num_units": 2,
            "num_stages": 3,
            "intercooler_t": 25.0,
            "intercooler_dp_pct": 2.0,
            "poly_eff": 78.0,
            "eos_model": "coolprop",
            "calc_method": "Metot 5: Huntington-RK45 Diferansiyel",
            "gas_comp": {
                "METHANE": 98.0,
                "ETHANE": 1.5,
                "NITROGEN": 0.5
            }
        }
    },
    {
        "id": "co2_injection",
        "icon": "🌿",
        "title": "CO₂ Yakalama & Enjeksiyon",
        "subtitle": "15→65 bar, Yüksek Yoğunluk",
        "inputs": {
            "p_in": 15.0,
            "p_in_unit": "bar(g)",
            "t_in": 30.0,
            "t_in_unit": "°C",
            "p_out": 65.0,
            "p_out_unit": "bar(a)",
            "flow": 500000.0,
            "flow_unit": "Sm³/h",
            "num_units": 2,
            "num_stages": 4,
            "intercooler_t": 35.0,
            "intercooler_dp_pct": 2.0,
            "poly_eff": 76.0,
            "eos_model": "coolprop",
            "calc_method": "Metot 5: Huntington-RK45 Diferansiyel",
            "gas_comp": {
                "CARBONDIOXIDE": 95.0,
                "METHANE": 3.0,
                "NITROGEN": 2.0
            }
        }
    },
    {
        "id": "hydrogen_blend",
        "icon": "⚡",
        "title": "Hidrojen Karışımı (H₂)",
        "subtitle": "20→50 bar, Düşük MW",
        "inputs": {
            "p_in": 20.0,
            "p_in_unit": "bar(g)",
            "t_in": 20.0,
            "t_in_unit": "°C",
            "p_out": 50.0,
            "p_out_unit": "bar(a)",
            "flow": 800000.0,
            "flow_unit": "Sm³/h",
            "num_units": 2,
            "num_stages": 3,
            "intercooler_t": 30.0,
            "intercooler_dp_pct": 1.5,
            "poly_eff": 77.0,
            "eos_model": "coolprop",
            "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
            "gas_comp": {
                "HYDROGEN": 20.0,
                "METHANE": 75.0,
                "NITROGEN": 5.0
            }
        }
    }
]

GUIDANCE_TEXTS = {
    "p_in": {
        "title": "Giriş Basıncı",
        "desc": "Kompresör emiş hattındaki mutlak veya efektif basınç. Emme basıncı, ilk kademe çark boyutunu ve hacimsel debisini doğrudan belirler."
    },
    "t_in": {
        "title": "Giriş Sıcaklığı",
        "desc": "Kompresör emiş sıcaklığı. Giriş sıcaklığı ne kadar düşük olursa gaz yoğunluğu artar ve sıkıştırma işi/güç tüketimi o kadar azalır."
    },
    "p_out": {
        "title": "Çıkış Basıncı",
        "desc": "Hedef basma hattı basıncı. Toplam basınç oranı (P_out/P_in) kademe sayısının belirlenmesinde birincil kriterdir."
    },
    "flow": {
        "title": "Gaz Debisi",
        "desc": "Standart veya gerçek şartlarda gaz debisi. Güç ihtiyacı kütlesel debi ile doğru orantılıdır."
    },
    "num_stages": {
        "title": "Kademe Sayısı (Multi-Stage)",
        "desc": "Basınç oranı PR > 3.5 olduğunda kademeler arası soğutma (Intercooler) uygulanması termodinamik verimi dramatik şekilde artırır."
    },
    "poly_eff": {
        "title": "Politropik Verim (η_p)",
        "desc": "Santrifüj kompresör çark politropik verimi. Endüstriyel santrifüj makinelerde tipik değer %76 - %86 aralığındadır."
    },
    "eos_model": {
        "title": "Hal Denklemi (Equation of State)",
        "desc": "<b>CoolProp (HEOS):</b> Saf akışkanlar ve kuru gazlar için referans model.<br><b>Peng-Robinson / SRK:</b> Hidrokarbon karışımları için endüstri standardı kübik EoS.<br><b>Equinor NeqSim (SRK-CPA):</b> Su, glikol ve asit gazı içeren polar karışımlarda en kararlı faz dengesi.<br><b>SINTEF thermopack:</b> Zengin hidrokarbonlarda yüksek performanslı kübik model."
    },
    "calc_method": {
        "title": "Sıkıştırma Yolu Yöntemi (Path Method)",
        "desc": "<b>Metot 6 (Schultz 3-Üslü):</b> ASME PTC-10 ve API 617 standartlarına tam uyumlu model.<br><b>Metot 5 (Huntington-RK45):</b> Sayısal Runge-Kutta 4. derece diferansiyel yol entegrasyonu.<br><b>Metot 4 (Doğrudan H-S):</b> Termodinamik durum noktalarından entalpi-entropi doğrudan farkı."
    },
    "consistency_iteration": {
        "title": "Tutarlılık İterasyonu (Consistency Mode)",
        "desc": "Kullanılan politropik verim ile kademe çıktılarından hesaplanan verim örtüşene kadar otomatik iterasyon yapar."
    }
}


def get_design_presets() -> List[Dict[str, Any]]:
    """Return all available engineering presets."""
    return ENGINEERING_PRESETS


def calculate_live_metrics(p_in: float, p_in_u: str, p_out: float, p_out_u: str) -> Dict[str, Any]:
    """Calculate pressure ratio and pressure differential in SI bar."""
    try:
        p_in_bar = UnitSystem.convert_pressure(float(p_in), p_in_u, "bar(a)")
        p_out_bar = UnitSystem.convert_pressure(float(p_out), p_out_u, "bar(a)")
        if p_in_bar <= 0 or p_out_bar <= 0:
            return {"pr": None, "delta_p_bar": None, "valid": False}
        pr = p_out_bar / p_in_bar
        dp = p_out_bar - p_in_bar
        return {
            "pr": round(pr, 3),
            "delta_p_bar": round(dp, 3),
            "valid": True,
            "warning": "Tek kademe için PR > 4.0 yüksek." if pr > 4.0 else None
        }
    except Exception:
        return {"pr": None, "delta_p_bar": None, "valid": False}
