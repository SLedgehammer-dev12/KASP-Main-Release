# Natural Gas Prop vs KASP Termodinamik Çekirdeği — Karşılaştırma Raporu

Tarih: 2026-11-09  
Kıyaslanan sürümler: `Natural Gas Prop v1.6.1` (kaynak kod), KASP `v4.x` (`kasp/core/thermo.py`, `kasp/core/properties.py`).

---

## 1. Yönetici Özeti

**Natural Gas Prop (NGP) KASP'ın yerine geçmez; ancak KASP'a ciddi katkı sağlayacak üç alanı vardır:**

1. **Gerçek GERG-2008 desteği** — KASP yalnızca AGA8-DC92 (ISO 12213-2) kullanıyordu; UI'da "GERG-2008" seçeneği vardı ama çekirdek bu EOS'u tanımıyordu.
2. **Gerçek izentropik üs (κ)** — KASP `Cp/Cv` kullanıyor; NGP'nin AGA8/GERG çıktısı gerçek izentropik üssü veriyor. Bu, izentropik sıcaklık ve basitleştirilmiş yöntemlerde fark yaratır.
3. **Z-faktörü fallback + hidrat + faz zarfı + çoklu standart koşulu** — KASP'ta olmayan operasyonel doğrulama katmanları.

**Sayısal sonuç:** Lean doğal gazda NGP GERG-2008 ile KASP AGA8-DC92 arasında Z/yoğunluk/Cp/ses hızı sapması **%0.1'in altında**. Isıtma değerleri (ISO 6976) neredeyse birebir aynı. Zengin gaz ve CO₂'li gazda GERG/AGA8, PR/SRK'ya göre belirgin şekilde daha doğru.

**Yapılan düzeltme:** KASP'a gerçek `gerg2008` backend'i eklendi (`pyaga8.Gerg2008`), `pyaga8` bağımlılığı `requirements`'a yazıldı ve gerçek izentropik üs `raw_props["isentropic_exponent"]` olarak saklanmaya başlandı. Ayrıca testler eklendi.

---

## 2. Backend ve Yetenek Karşılaştırması

| Yetenek | Natural Gas Prop | KASP | Değerlendirme |
|---|---|---|---|
| CoolProp HEOS | ✅ | ✅ | Eşdeğer |
| CoolProp SRK / PR | ✅ | ✅ | Eşdeğer |
| CoolProp GERG-2008 | ✅ (HEOS/GERG) | ✅ (CoolProp HEOS) | Eşdeğer |
| **AGA8-DC92 / ISO 12213-2** | ✅ (`pyaga8.Detail`) | ✅ | Eşdeğer |
| **GERG-2008 (Kunz-Wagner)** | ✅ (`pyaga8.Gerg2008`) | ✅ (yeni eklendi) | **KASP kazanımı** |
| NeqSim / SRK-CPA | ✅ (Java gerekir) | ✅ (Java gerekir) | Eşdeğer; bu makinede Java yok |
| thermopack | ❌ | ✅ | KASP üstün |
| ccp / DWSIM | ❌ | ✅ | KASP üstün |
| Z-faktörü korelasyonları (Standing-Katz, ANN10, ANN5, DAK, Sutton, Wichert-Aziz) | ✅ | ❌ (PR/SRK/ideal fallback) | **NGP üstün** |
| Hidrat tahmini (Hammerschmidt, Motiee, Towler-Mokhatab, NeqSim CPA) | ✅ | ❌ | **NGP üstün** |
| Faz zarfı (dew/bubble, cricondenbar/therm) | ✅ | Kısmi (CoolProp faz) | **NGP üstün** |
| Transport (viskozite, ısıl iletkenlik, Joule-Thomson, yüzey gerilimi) | ✅ (NeqSim) | Viskozite CoolProp; diğerleri kısmi | NGP (Java varsa) |
| ISO 6976 LHV/HHV/Wobbe | ✅ | ✅ | Eşdeğer |
| Çoklu standart koşulu (ISO 13443, GPA 2172, API MPMS, EPDK, GOST) | ✅ | Kısmi | **NGP üstün** |
| Hacim dönüşümü (ACM/Sm³/Nm³) | ✅ | Kısmi | **NGP üstün** |
| Otomatik backend fallback | ✅ (GERG→AGA8→HEOS→SRK→PR→Z-only) | ✅ (EosChain) | Eşdeğer / NGP daha geniş |
| UI bağımsız saf çekirdek | ✅ (`models/`) | ✅ (`core/`) | Eşdeğer |

---

## 3. Sayısal Karşılaştırma — Lean Doğal Gaz

Karışım: **CH₄ 88 / C₂H₆ 7 / C₃H₈ 3 / N₂ 1 / CO₂ 1 (mol%)**

### 3.1 20 bar(a), 25 °C

| Backend | Z | ρ (kg/m³) | Cp (kJ/kg·K) | Cv (kJ/kg·K) | a (m/s) |
|---|---:|---:|---:|---:|---:|
| **GERG-2008 (NGP)** | 0.9555 | 15.4234 | 2.2193 | 1.6494 | 408.32 |
| AGA8-Detail (NGP) | 0.9553 | 15.4258 | 2.2207 | 1.6506 | 408.25 |
| HEOS (NGP) | 0.9554 | 15.4242 | 2.2182 | 1.6484 | 408.33 |
| SRK (NGP) | 0.9559 | 15.4165 | 2.2207 | 1.6426 | 409.62 |
| PR (NGP) | 0.9454 | 15.5884 | 2.2190 | 1.6385 | 405.57 |
| KASP CoolProp | 0.9554 | 15.4242 | 2.2182 | 1.6484 | 408.33 |
| KASP AGA8 | 0.9553 | 15.4258 | 2.2207 | 1.6506 | 408.25 |
| KASP GERG-2008 | 0.9555 | 15.4234 | 2.2193 | 1.6494 | 408.32 |

**GERG'e göre sapma:**

| Backend | Z | ρ | Cp | a |
|---|---:|---:|---:|---:|
| AGA8-Detail | -0.01% | +0.02% | +0.06% | -0.02% |
| HEOS | 0.00% | +0.01% | -0.05% | 0.00% |
| SRK | +0.05% | -0.04% | +0.07% | +0.32% |
| PR | **-1.06%** | **+1.07%** | -0.01% | -0.67% |

### 3.2 60 bar(a), 84.4 °C

| Backend | Z | ρ | Cp | a |
|---|---:|---:|---:|---:|
| GERG-2008 | 0.9397 | 39.2296 | 2.5225 | 445.78 |
| AGA8-Detail | 0.9395 | 39.2394 | 2.5243 | 445.56 |
| HEOS | 0.9397 | 39.2324 | 2.5214 | 445.79 |
| SRK | 0.9462 | 38.9609 | 2.5393 | 450.63 |
| PR | 0.9236 | 39.9132 | 2.5366 | 441.66 |

**Sapma:** PR Z **-1.71%**, yoğunluk **+1.74%**; SRK Z **+0.69%**, yoğunluk **-0.68%**; AGA8/HEOS **<%0.02**.

---

## 4. Sayısal Karşılaştırma — Zengin Gaz ve CO₂

### 4.1 Zengin gaz: CH₄ 70 / C₂H₆ 12 / C₃H₈ 8 / n-C₄ 4 / n-C₅ 3 / N₂ 2 / CO₂ 1, 40 bar, 40 °C

| Backend | Z | ρ (kg/m³) | Cp | a | Z sapması |
|---|---:|---:|---:|---:|---:|
| **GERG-2008** | 0.8592 | 42.6538 | 2.3843 | 336.10 | referans |
| AGA8-Detail | 0.8579 | 42.7198 | 2.4103 | 336.36 | -0.15% |
| KASP AGA8 | 0.8579 | 42.7198 | 2.4103 | 336.36 | -0.15% |
| KASP CoolProp | 0.8403 | 43.6151 | 2.3502 | 331.96 | **-2.20%** |
| KASP PR | 0.8403 | 43.6151 | 2.3502 | 331.96 | **-2.20%** |
| KASP SRK | 0.8624 | 42.4982 | 2.3559 | 339.51 | +0.37% |

> Not: KASP CoolProp, zengin karışımda iki faz/başarısızlık nedeniyle PR'a düşmüş görünüyor; bu yüzden PR ile aynı değerleri veriyor. GERG-2008 bu durumda açık ara daha güvenilir.

### 4.2 CO₂'li gaz: CH₄ 65 / CO₂ 30 / N₂ 5, 60 bar, 30 °C

| Backend | Z | ρ | a | Z sapması |
|---|---:|---:|---:|---:|
| **GERG-2008** | 0.8722 | 68.3177 | 345.53 | referans |
| AGA8-Detail | 0.8724 | 68.3031 | 345.73 | +0.02% |
| KASP AGA8 | 0.8724 | 68.3031 | 345.73 | +0.02% |
| KASP PR | 0.8537 | 69.8001 | 343.62 | **-2.12%** |
| KASP SRK | 0.8785 | 67.8287 | 351.72 | +0.72% |

### 4.3 Hidrojen karışımı: CH₄ 75 / H₂ 20 / N₂ 5, 50 bar, 20 °C

| Backend | Z | ρ | a | Z sapması |
|---|---:|---:|---:|---:|
| **GERG-2008** | 0.9565 | 29.6725 | 482.67 | referans |
| AGA8-Detail | 0.9565 | 29.6733 | 482.54 | 0.00% |
| KASP AGA8 | 0.9565 | 29.6733 | 482.54 | 0.00% |
| KASP PR | 0.9370 | 30.2903 | 476.54 | **-2.04%** |
| KASP SRK | 0.9578 | 29.6325 | 485.27 | +0.13% |

---

## 5. Isıtma Değerleri ve Standart Koşullar

Karışım: lean doğal gaz; 15 °C, 101.325 kPa.

| Parametre | NGP (GERG-2008 + ISO 6976) | KASP (ISO 6976) | Fark |
|---|---:|---:|---:|
| Standart yoğunluk (kg/Sm³) | 0.774452 | 0.774483 | +0.004% |
| Özgül ağırlık (-) | 0.631927 | 0.632 | ~0.01% |
| LHV (kJ/kg) | 47,512.75 | 47,503.34 | -0.02% |
| HHV (kJ/kg) | 52,588.89 | 52,587.68 | -0.002% |
| LHV (MJ/Sm³) | 36.796 | 36.791 | -0.01% |
| HHV (MJ/Sm³) | 40.728 | 40.729 | +0.002% |
| Wobbe (MJ/Sm³) | 51.234 | 51.231 | -0.005% |

**Sonuç:** Isıtma değeri ve Wobbe tarafında iki program pratikte aynı. NGP'nin farkı, çoklu standart koşulu (GPA 2172, API MPMS, EPDK, GOST) ve hacim dönüşümü sunması.

---

## 6. Kritik Bulgu: İzentropik Üs (κ) vs Cp/Cv

- KASP `state.k` alanını **Cp/Cv** olarak hesaplıyor.
- NGP'nin AGA8/GERG çıktısı **gerçek izentropik üssü** (`kappa`) veriyor.
- Termodinamik özdeşlik: `κ_s = a²·ρ / P`.

Örnek (20 bar, 25 °C):

| Büyüklük | Değer |
|---|---:|
| Cp/Cv | 1.3457 |
| Gerçek κ_s = a²ρ/P | **1.2857** |
| Fark | ~%4.7 |

Bu fark, izentropik sıcaklık bağıntısında `T₂/T₁ = (P₂/P₁)^((κ-1)/κ)` ciddi sapma yaratır. Örneğin PR=3 için:
- κ=1.2857 → sıcaklık oranı ≈ 1.275
- κ=1.3457 → sıcaklık oranı ≈ 1.326

298 K girişte bu, yaklaşık **15 °C** çıkış sıcaklığı farkı demektir. KASP'ın Metot 4/6 gibi entalpi-entropi tabanlı yöntemleri bundan daha az etkilenir; ancak Metot 1/2 ve izentropik referans hesapları etkilenir.

**Yapılan iyileştirme:** KASP artık her iki değeri ayrı saklıyor:
- `raw_props["cp_cv_ratio"]` → Cp/Cv
- `raw_props["isentropic_exponent"]` → gerçek κ_s (CoolProp için a²ρ/P, AGA8/GERG için pyaga8.kappa)

**Öneri:** Hesaplama yöntemlerinde kullanılan `k` alanı ileride `κ_s` olarak ayrılmalı; Cp/Cv yalnızca ısı kapasitesi oranı olarak tutulmalı. Bu, özellikle yüksek basınçlı doğal gazda doğruluğu artırır.

---

## 7. Üstünlük Değerlendirmesi

### NGP'nin KASP'a göre üstün olduğu alanlar

1. **GERG-2008 referans modeli** (artık KASP'a da eklendi).
2. **Z-faktörü korelasyon seti** (Standing-Katz ANN10/ANN5, DAK, Sutton, Wichert-Aziz) — hızlı ön hesap ve fallback.
3. **Hidrat oluşum tahmini** — LNG, CO₂ enjeksiyonu, su içeren gazlar için kritik.
4. **Faz zarfı** — yoğun faz/CO₂ taşımacılığında.
5. **Çoklu standart koşulu ve hacim dönüşümü** — ölçüm/ticari gaz mutabakatı.
6. **Transport properties (NeqSim ile)** — Java varsa viskozite, ısıl iletkenlik, Joule-Thomson, yüzey gerilimi.
7. **Daha geniş otomatik fallback zinciri** — GERG→AGA8→HEOS→SRK→PR→Z-only.

### KASP'ın NGP'ye göre üstün olduğu alanlar

1. **Kompresör tasarımı ve API 617 / ASME PTC-10 iş akışı** — NGP'de yok.
2. **Çoklu EOS: thermopack, ccp, DWSIM, NeqSim** — NGP'de yok.
3. **Politropik yol metotları (1-6), kademe döngüsü, VLE knockout** — NGP'de yok.
4. **Türbin seçimi, ISO 2314 derate, güç/yakıt/heat rate** — NGP'de yok.
5. **İstasyon modeli, boru boyutlandırma, 3D dijital ikiz** — NGP'de yok.
6. **ISO 6976 ısıtma değerleri** zaten eşdeğer.

### Sonuç

NGP, KASP'ın **termodinamik doğrulama ve referans katmanı** olarak kullanılmalı:
- **Birincil üretim çekirdeği:** KASP `ThermoEngine` kalsın.
- **Referans/audit:** NGP GERG-2008 ve Z-faktörü korelasyonları ile çapraz kontrol.
- **Yeni özellikler:** hidrat, faz zarfı, çoklu standart koşulu KASP'a modül olarak eklensin.
- **Gerçek κ_s:** KASP hesaplarına entegre edilsin.

---

## 8. Yapılan Kod Değişiklikleri

| Değişiklik | Dosya |
|---|---|
| `gerg2008` EOS'u gerçek `pyaga8.Gerg2008` ile çalışır hale getirildi | `kasp/core/properties.py` |
| `_create_gas_object` ve `_dispatch` içine `gerg2008` eklendi | `kasp/core/thermo.py`, `kasp/core/properties.py` |
| Desktop UI EOS eşlemesi `GERG-2008` → `gerg2008` | `kasp/ui/design_input_binding.py` |
| `pyaga8` bağımlılığı eklendi | `requirements.txt`, `requirements.lock.txt` |
| Gerçek izentropik üs `state.k_s` + `raw_props["isentropic_exponent"]` olarak eklendi | `kasp/core/models.py`, `kasp/core/properties.py` |
| Aerodinamik/termodinamik yöntemler `k_s` kullanacak şekilde güncellendi | `kasp/core/aerodynamics.py`, `kasp/core/thermo_methods.py`, `kasp/core/fallback.py` |
| Z-faktörü fallback'i (Kay + Wichert-Aziz + DAK) eklendi | `kasp/core/z_factor.py`, `kasp/core/properties.py` |
| Sonuç payload'ına `k_s_in/k_s_out` eklendi | `kasp/services/calculation_service.py` |
| Web termodinamik tablosuna "Gerçek İzentropik Üs" satırı eklendi | `kasp/web/src/components/resultsView.js` |
| GERG-2008, κ_s ve DAK regresyon testleri | `test_new_eos.py` |

**Test sonucu:** En son ilgili test setinde **56 + 70 + 10 test geçti** (toplam 136; bazı setler tekrar sayılırsa 120+ benzersiz). KASP GERG-2008, NGP GERG-2008 ile lean/zengin/CO₂/H₂ karışımlarında **birebir aynı** sonuç verdi.

---

## 8.1. Z-Faktörü Fallback Zinciri

EOS'ların tamamı başarısız olduğunda KASP artık şu sırayı izler:

1. PR
2. SRK
3. **Kay kuralı + Wichert-Aziz düzeltmesi + DAK (Dranchuk-Abou-Kassem)**
4. İdeal gaz (son çare)

DAK fallback çıktısı:
- `Z`, `Ppr`, `Tpr`, `Tpc`, `Ppc`
- `fallback_layer = "z_factor_dak"`
- `z_factor_valid`, `z_factor_method`
- Sağlık uyarıları (`health_reasons`)

Lean gaz, 20 bar / 25 °C için DAK Z ≈ 0.9533; GERG-2008 referansı 0.9555 (fark ~%0.24). Fallback için makul.

> ANN10/ANN5 ağırlıkları henüz eklenmedi; DAK tek başına sağlam bir fallback sağlıyor. İstenirse aynı modüle ANN10/ANN5 eklenebilir.

---

## 8.2. κ_s Entegrasyonunun Etkisi

- `state.k` artık **Cp/Cv** olarak korunuyor (geriye uyumluluk).
- `state.k_s` gerçek izentropik üs:
  - CoolProp: `a²ρ/P`
  - AGA8/GERG: `pyaga8.kappa`
  - PR/SRK/thermopack: `a²ρ/P` (ses hızı geçerliyse), yoksa Cp/Cv
- Hesaplama yöntemleri (`aerodynamics`, `thermo_methods`, `fallback`) artık `isentropic_exponent(state)` yardımcısıyla **κ_s** kullanıyor.

Bu değişiklik özellikle:
- izentropik sıcaklık başlangıç tahminleri,
- Metot 1/2/3 politropik üs hesabı,
- Schultz faktörü,
- k-tabanlı fallback

noktalarında doğruluğu artırır. Entalpi-entropi tabanlı Metot 4/6 sonuçları entalpi farkına dayandığı için daha az etkilenir.

---

## 9. Önerilen Sonraki Adım

1. **Faz 1A:** KASP'ta `κ_s`'yi hesaplama yöntemlerine bağla (özellikle Metot 1/2 ve izentropik referans); Cp/Cv'yi ayrı tut.
2. **Faz 1B:** NGP'nin Z-faktörü fallback zincirini ve hidrat modülünü `kasp/integrations/thermo_audit/` altına adaptörle ekle.
3. **Faz 1C:** "Termodinamik Doğrulama" paneli: seçilen EOS için GERG/AGA8/PR/SRK karşılaştırması, sapma yüzdeleri ve uyarılar.
4. **Faz 1D:** Çoklu standart koşulu (GPA/API/EPDK/GOST) ve hacim dönüşümü KASP raporlarına ekle.

---

*Bu rapor, aynı gaz karışımları ve aynı P/T noktalarında gerçek Python çağrılarıyla üretilmiştir.*
