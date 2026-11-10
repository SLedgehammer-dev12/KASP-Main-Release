# KASP Entegrasyon Faz 1A — Durum Raporu

Tarih: 2026-11-09  
Kapsam: modül iskeleti + PSV + API 5L + Natural Gas hidrolik + istasyon entegrasyonu.

---

## 1. Tamamlananlar

### 1.1 Modül altyapısı

```
kasp/integrations/
  base.py                 # ModuleManifest, ortak cevap şeması
  registry.py             # modül keşfi, listeleme, hesaplama
  psv/
    adapter.py
    vendor/core/...       # PSV Sizing Suite (MIT)
  api5l/
    adapter.py
    vendor/...            # API 5L Pipe core (MIT)
  pipe_hydraulics/
    adapter.py
```

Ortak API sözleşmesi:
- Girdi: SI birimleri (`bar(a)`, `°C`, `kg/s`) + KASP `gas_comp`.
- Çıktı: `schema_version`, `module_id`, `success`, `warnings`, `provenance`, `results`.

### 1.2 Web API

Yeni endpoint'ler:

| Metot | Yol | İşlev |
|---|---|---|
| GET | `/api/v1/modules` | Kayıtlı modülleri listeler |
| GET | `/api/v1/modules/{id}/schema` | Modül girdi şeması |
| POST | `/api/v1/modules/{id}/calculate` | Modül hesabı |

Örnek:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/modules/api5l/calculate \
  -H "Content-Type: application/json" \
  -d '{"payload":{"diameter_in":"48","material_grade":"X65","design_pressure_bar":75,"design_factor_f":0.50,"location_type":"Station","standard_code":"BOTAŞ","psl_level":"PSL2","compare_standards":true}}'
```

### 1.3 PSV modülü

- API 520 Part I / API 521 ön boyutlandırma.
- Gaz, sıvı, buhar, iki faz, fire-wetted, fire-unwetted, termal genleşme servisleri.
- KASP gaz kompozisyonundan Z/MW/k otomatik hesabı.
- İstasyon modeline `psv_sizing` olarak bağlandı:
  - `required_area_sqin`
  - `selected_orifice`
  - `selected_orifice_area_sqin`
  - `orifice_loading_pct`
  - `flow_type`
  - standart referansı

### 1.4 API 5L modülü

- Barlow et kalınlığı.
- ASME B36.10M schedule seçimi.
- BOTAŞ 5120_R7 standart et kalınlığı matrisi.
- API 5L PSL1/PSL2, SMLS/ERW/SAWH/SAWL.
- Negatif imalat toleransı (API 5L Table 11 / BOTAŞ Madde 5.5).
- BOTAŞ vs ASME B31.8 karşılaştırması (`compare_standards`).

İstasyon boru tablosuna eklendi:
- `standard_recommendation.standard`
- `psl_level`
- `required_thickness_mm`
- `selected_nominal_thickness_mm`
- `botas_standard_thickness_mm`
- `minimum_standard_thickness_mm`
- `tolerance_rule`
- `is_sufficient`

Web tablosunda yeni sütunlar:
- **Standart t_min**
- **Standart** (BOTAŞ/PSL2 veya API 5L)

### 1.5 Natural Gas hidrolik modülü

`kasp/core/pipe_sizing.py` genişletildi:
- `length_m`
- `fitting_k_total`
- `elevation_m`
- `density_kgm3`
- `viscosity_pa_s`
- `z_factor`

Yeni çıktılar:
- `pressure_drop_friction_bar`
- `pressure_drop_fittings_bar`
- `pressure_drop_elevation_bar`
- `pressure_drop_bar_total`
- `outlet_pressure_bar`

Modül, gaz kompozisyonu verildiğinde KASP GERG-2008 ile gerçek yoğunluk/Z/viskozite kullanır.

### 1.6 İstasyon UI entegrasyonu

- Canlı parametre paneline **Boru Standardı** ve **PSL Seviyesi** eklendi.
- Boru tablosuna standart/tolerans sütunları eklendi.
- PSV inspector ve 3D telemetriye API 520 ön boyutlandırma satırları eklendi.

---

## 2. Doğrulama

Yeni test dosyası: `test_integrations.py`

- Modül registry
- API 5L BOTAŞ vs ASME
- Hidrolik toplam ΔP
- PSV gaz boyutlandırma
- `/api/v1/modules` endpoint

**Sonuç:** `15 passed` (entegrasyon + station + pipe sizing), ardından geniş regresyon setinde `80 passed`.

Örnek istasyon çıktısı (12 kg/s, 20→60 bar):
- PSV: gerekli alan **1.474 in²**, seçilen orifis **K (1.838 in²)**, yük **%80.2**, akış **CRITICAL**.
- Emiş header: BOTAŞ PSL2, t_req **1.69 mm**, seçilen **3.40 mm**, BOTAŞ standart **8.70 mm**, uygun.

---

## 3. Sıradaki adım — Faz 1B

1. **Air-Cooler-Main** adaptörü:
   - `AirFinnedGasCooler` çekirdeği.
   - Gerekli ekler: `pint`, `ht`, `fluids`.
   - İstasyon cooler bay/ısıl yük hesabını gerçek API 661 hesabına çevir.
2. **Control Valve Sizing** adaptörü:
   - `size_gas_valve` / `size_liquid_valve`.
   - Gerekli ek: `fluids`.
   - ASV/TCV/PCV otomatik boyutlandırma.
3. Modül UI:
   - Genel "Modüller" sekmesi veya ekipman inspector'da "Detaylı Tasarım" butonu.
4. Rapor entegrasyonu:
   - PDF rapora PSV/API 5L/hidrolik bölümleri.

---

## 4. Lisans / Kaynak

- PSV Sizing Suite core: MIT, `kasp/integrations/psv/vendor/LICENSE.txt`.
- API 5L Pipe core: MIT, `kasp/integrations/api5l/vendor/LICENSE.txt`.
- Natural Gas Flow Calc: KASP içinde gömülü motor (`kasp/core/pipe_sizing.py`).
