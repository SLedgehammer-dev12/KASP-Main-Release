"""
KASP V4.4 Settings
Termodinamik hesaplamalarda, türbin seçim puanlamalarında ve emniyet
kriterlerinde kullanılan tüm eşik değerleri (threshold), oranlar ve katsayılar
bu dosyadan yönetilmektedir. (Magic Number temizliği)
"""

class EngineSettings:
    # ─── Termodinamik & Optimizasyon Eşikleri ───
    PR_INTEGRATION_THRESHOLD = 4.0      # Basınç oranına göre sayısal integrasyon sınırı
    MAX_CONSISTENCY_ITERATIONS = 20     # İzentropik / Polytropik döngülerde maks limit
    CONSISTENCY_TOLERANCE = 0.5         # Delta H ve T için hedef tolerans (J/kg veya K)
    DEFAULT_COOLPROP_COMPLEX_MAX_ITER = 10  # 8+ bileşenli CoolProp karışımlarında yakınsama sınırı
    PTC10_MECHANICAL_LOSS_LIMIT = 10.0  # Şaft limitinin %10'u (ASME PTC 10)
    DEFAULT_MECHANICAL_EFFICIENCY_PCT = 98.0  # Varsayılan mekanik verim (%)
    DEFAULT_THERMAL_EFFICIENCY_PCT = 35.0     # Varsayılan sürücü termal verimi (%)
    
    # ─── API 617 Emniyet Marjları ───
    API617_MIN_SURGE_MARGIN = 10.0      # %10'dan az surge mesafesi tehlikelidir
    API617_MIN_STONEWALL_MARGIN = 5.0   # %5'ten az Stonewall (Choke) mesafesi tehlikelidir
    
    # ─── Türbin Puanlama / Derecelendirme Ağırlıkları (Toplam 1.0) ───
    SCORE_WEIGHT_POWER = 0.40           # İstenen güce yakınlık (oversize/undersize)
    SCORE_WEIGHT_EFFICIENCY = 0.30      # Isıl verim oranı (Heat Rate bazlı)
    SCORE_WEIGHT_SURGE = 0.20           # Aerodinamik emniyet (API 617 limit aşımı)
    SCORE_WEIGHT_TYPE = 0.10            # Sistem türü (Aero, HD, Endüstriyel)
    
    # ─── Isıl Verim Optimizasyon Sınırları (kJ/kWh) ───
    HR_REF_BEST = 8500.0                # Çok İyi (100 puan sınırı, %40+ verim)
    HR_REF_WORST = 14000.0              # Çok Kötü (0 puan sınırı, <%25 verim)
    
    # ─── Türbin Tipi Sabit Puan Çarpanları ───
    TURBINE_TYPE_SCORES = {
        'Aero-Derivative': 100,
        'Industrial/Aero': 90,
        'Industrial':       80,
        'Heavy-Duty':       70,
        'Centrifugal':      60,
    }

    @classmethod
    def get_turbine_type_score(cls, turbine_type: str | None) -> float:
        """Kayıtlı türbin tiplerini büyük/küçük harf, boşluk ve tire duyarsız normalize ederek puanlar."""
        if not turbine_type:
            return 65.0
        normalized = str(turbine_type).lower().replace(" ", "-").replace("_", "-").strip()
        for k, v in cls.TURBINE_TYPE_SCORES.items():
            if k.lower() == normalized:
                return float(v)

        alias_map = {
            "industrial/aero": 90.0,
            "industrial-aero": 90.0,
            "aero-derivative": 100.0,
            "aero": 100.0,
            "industrial": 80.0,
            "heavy-duty": 70.0,
            "heavy": 70.0,
            "centrifugal": 60.0,
        }
        for k, v in alias_map.items():
            if k in normalized:
                return v
        return 65.0

    # ─── Güç Marjı (Oversizing) Penaltıları (%) ───
    MAX_ALLOWED_OVERSIZE_PCT = 50.0     # İhtiyaçtan %50 büyükse filtreye takılır
    OPTIMAL_OVERSIZE_MIN = 5.0          # İdeal oversizing alt sınırı (%5 marj)
    OPTIMAL_OVERSIZE_MAX = 20.0         # İdeal oversizing üst sınırı (%20 marj)
