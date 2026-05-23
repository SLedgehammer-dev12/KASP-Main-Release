"""
KASP V4.4 Data Models
Bu dosya projenin tip güvenliğini (Type Safety) sağlamak amacıyla oluşturulan
Dataclasses / Models tanımlarını barındırır. Standart dictionary yapıları yerine
belirli tiplere sahip nesneler döndürülerek kod güvenilirliği ve okunabilirliği arttırılacaktır.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class ThermodynamicState:
    """Temel termodinamik nokta özellikleri (P, T, H, vs.)"""
    P: float            # Basınç (Pa)
    T: float            # Sıcaklık (K)
    H: float            # Entalpi (J/kg)
    S: float            # Entropi (J/kg/K)
    Z: float            # Sıkıştırılabilirlik faktörü
    k: float            # İzentropik (Özgül ısı) oranı (Cp/Cv)
    MW: float           # Molar kütle (g/mol)
    Cp: float           # Sabit basınçta özgül ısı (kJ/kg/K)
    Cv: float           # Sabit hacimde özgül ısı (kJ/kg/K)
    density: float      # Yoğunluk (kg/m³)
    phase: str          # 'gas', 'liquid', 'supercritical', vs.
    raw_props: Dict[str, Any] = field(default_factory=dict) # Orijinal kütüphane property verisi

@dataclass
class ProcessConditions:
    """Kompresör veya santral çalışma koşulları ve gereksinimler"""
    p_in: float         # Giriş basıncı (Pa mutlak)
    t_in: float         # Giriş sıcaklığı (K)
    p_out: float        # Çıkış basıncı (Pa mutlak)
    flow_kgs: float     # Kütlesel debi (kg/s)
    t_out_measured: Optional[float] = None  # Ölçülen çıkış sıcaklığı (K) [Opsiyonel]
    gas_comp: Dict[str, float] = field(default_factory=dict)  # Normalize edilmiş gaz kompozisyonu (fraksiyon)
    eos_method: str = 'coolprop' # Kullanılacak termodinamik metot (coolprop, pr, srk vb.)

@dataclass
class EnginePerformanceResult:
    """CompressorAerodynamics (Head ve Verim) analiz sonuçları"""
    head_actual_kj_kg: float
    poly_efficiency: float      # Politropik verim (0-1.0)
    isen_efficiency: float      # İzentropik verim (0-1.0)
    therm_efficiency: float     # Sistemin genel termal verimi (0-1.0)
    power_gas_kw: float         # Gerekli gaz/sıkıştırma gücü (kW)
    power_shaft_kw: float       # Gerekli şaft gücü (Mekanik kayıplar dâhil) (kW)
    mechanical_loss_kw: float
    t_out_isen_k: float         # İzentropik sıkışma sonu teorik sıcaklık (K)
    t_out_actual_k: float       # Gerçek sıkışma sonu sıcaklık (Tahmini veya ölçüm temelli) (K)
    heat_rate_kj_kwh: float     # Özgül ısı tüketimi HR (kJ/kWh)
    uncertainty: float = 0.0

@dataclass
class TurbineRecommendation:
    """TurbineSelector modülünün API formatındaki ünite puanlama çıktısı"""
    turbine_name: str
    manufacturer: str
    model: str
    type_str: str               # Aero-Derivative, Industrial vb.
    iso_power_kw: float         # Standart kapasite
    available_power_kw: float   # Site koşullarına göre düzeltilmiş gerçek kullanım gücü
    site_heat_rate: float       # Düzeltilmiş site özgül ısı tüketimi
    power_margin_percent: float # Mevcut fazlalık/eksiklik gücü yüzdesi
    surge_margin_percent: float # Surge mesafesi
    stonewall_margin_percent: float # Stonewall mesafesi
    meets_api617_surge: bool    # >%10 mu?
    selection_score: float      # 0-100 ağırlıklı final skoru
    efficiency_rating: str      # 'Çok Yüksek', 'Yüksek' vb.
    recommendation_level: str   # 5 Yıldızlı metin

@dataclass
class SelectionResult:
    """Tüm seçilen ünitelerin toplam kapsül sınıfı"""
    units: list[TurbineRecommendation] = field(default_factory=list)
    site_conditions: Dict[str, float] = field(default_factory=dict) # Temp, Altitude, Pressure vb.
