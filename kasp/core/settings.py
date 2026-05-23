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
    PTC10_MECHANICAL_LOSS_LIMIT = 10.0  # Şaft limitinin %10'u (ASME PTC 10)
    
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

    # ─── Güç Marjı (Oversizing) Penaltıları (%) ───
    MAX_ALLOWED_OVERSIZE_PCT = 50.0     # İhtiyaçtan %50 büyükse filtreye takılır
    OPTIMAL_OVERSIZE_MIN = 5.0          # İdeal oversizing alt sınırı (%5 marj)
    OPTIMAL_OVERSIZE_MAX = 20.0         # İdeal oversizing üst sınırı (%20 marj)
