# KASP Web Platformu — Derinlemesine Analiz ve Program Haritası

> Kapsam: `kasp/web/` (tarayıcı), `kasp/api/` (FastAPI), `kasp/services/` (hesaplama servisleri), ilgili `kasp/core/` modülleri.
> Yöntem: statik kod okuma + gerçek API/servis çağrılarıyla doğrulama (design, station, pipe sizing).
> Belge tarihi: 2026-11-09

---

## 1. Yönetici Özeti

KASP web sürümü, masaüstü PyQt uygulamasının hesaplama çekirdeğini (`kasp/core`) yeniden kullanan, **zero-build ES6 modüler** bir ön yüz + **FastAPI REST/SSE** arka uçtan oluşur.

- **Ön yüz:** Framework yok. Vanilla JS ES modules + kendi pub/sub store'u + Plotly.js + Three.js. `index.html` yalnızca 3 CSS, 2 script (Plotly, Three) ve `main.js` yükler.
- **Arka uç:** `kasp/api/server.py` (legacy launcher + static mount) ve `kasp/api/v1/*` router'ları. İş mantığı `kasp/services/*` içinde.
- **Tek doğruluk kaynağı:** Tasarım hesabı `calculation_service.execute_design_calculation()` üzerinden yürür; masaüstü ve web aynı çekirdeği kullanır.
- **Ana ekranlar:** Tasarım, Performans (ASME PTC-10), Mühendislik Shootout, 3D İstasyon & P&ID, Sistem Logları.
- **En güçlü yön:** Termodinamik çekirdek, EOS/metot seçimi, türbin seçimi, 15 hatlı boru boyutlandırma ve prosedürel 3D tesis modeli gerçek mühendislik formülleri içeriyor.
- **En zayıf yön:** Katmanlar arası **veri sözleşmeleri tutarsız**. Özellikle kademe birimleri (Pa/K ↔ bar/°C), istasyon gaz MW anahtarları, istasyon debi önceliği ve performans tablosu alan adları hatalı. Bu nedenle bazı ekranlar yanlış/statik değer gösteriyor.

---

## 2. Çalışma Zamanı Mimarisi

```
Tarayıcı
  index.html
    ├─ /static/css/{tokens,layout,components}.css
    ├─ /static/vendor/plotly.min.js
    ├─ /static/vendor/three.min.js + OrbitControls.js
    └─ /static/src/main.js  (type=module)
         ├─ store/  (store.js, projectStore.js, uiStore.js, authStore.js)
         ├─ api/client.js  → fetch + Bearer + X-CSRF-Token
         └─ components/
              header, designSidebar, gasTable, resultsView, chartsView,
              performanceTab, shootoutTab, stationTab, station3dView,
              equipmentTeardown, logsTab, kijModal, equipmentModal, projectModal,
              userModal, authModal, handbookModal
                            │ HTTP / SSE
                            ▼
FastAPI  (kasp/api/server.py)
  ├─ /static  → kasp/web
  ├─ /        → kasp/web/index.html
  └─ /api/v1/* (kasp/api/v1/__init__.py)
       auth, users, metadata, calculations, equipment,
       projects, reports, jobs (SSE), logs (SSE)
                            │
                            ▼
Services (kasp/services/)
  calculation_service, chart_data_builder, station_service,
  pipe_sizing_service, performance_service, validation_service,
  gas_service, design_input_service, job_manager
                            │
                            ▼
Core (kasp/core/)
  thermo, thermo_design_orchestration, thermo_design_support,
  selection, pipe_sizing, aerodynamics, contracts, units, constants
```

### Çalıştırma

- `run_web.py` `KASP_API_ENABLE=1`, `KASP_API_TOKEN=kasp-local-token`, host `127.0.0.1` varsayılanlarını koyar; portu **8080 → 8000 → 8081 → 8082** sırasıyla arar.
- `README.md` hâlâ 8000 ve Vue/Tailwind/Chart.js'ten bahsediyor; **güncel değil**. Gerçek ön yüz vanilla JS + Plotly + Three.js.
- `kasp/api/server.py` modülü "legacy/experimental" olarak işaretli; `KASP_API_ENABLE` yoksa sadece uyarı basar, `__main__` ile başlatılırsa çıkar.

---

## 3. Ekran / Bileşen Haritası

| Sekme | Bileşen | Görev | Ana veri kaynağı |
|---|---|---|---|
| Tasarım | `designSidebar.js` | 5 adımlı girdi, önayar, canlı PR/ΔP, hesapla | `projectStore.inputs` |
| Tasarım | `gasTable.js` | 19 gaz mol%, toplam, normalize, kij | `/thermo/gases`, `/thermo/recommendations` |
| Tasarım | `resultsView.js` | 8 KPI + 7 alt sekme + türbin tablosu + derate | `/calculations/design` sonucu |
| Tasarım | `chartsView.js` | 8 Plotly grafiği + SVG mimari | `charts` payload |
| Performans | `performanceTab.js` | Saha verisi → PTC-10 sapma tablosu | `/calculations/performance` |
| Shootout | `shootoutTab.js` | 7 EOS × 6 metot benchmark, SSE ilerleme | `/jobs/shootout`, `/jobs/{id}/stream` |
| 3D İstasyon | `stationTab.js` | Özet kartlar, canlı parametre, 2D P&ID, düğümler, boru tablosu | `/calculations/station` |
| 3D İstasyon | `station3dView.js` | Three.js prosedürel tesis, tıklama, telemetri, kesit | `stationData` |
| Loglar | `logsTab.js` | REST + SSE log akışı | `/logs`, `/logs/stream` |
| Global | `header.js` | Proje adı, kaydet, export/import, PDF, modallar, tema/dil, auth | tüm store'lar |
| Modal | `kijModal`, `equipmentModal`, `projectModal`, `userModal`, `authModal`, `handbookModal` | kij, katalog, geçmiş, RBAC, giriş/kurtarma, el kitabı | ilgili endpoint'ler |

### Navigasyon

- `main.js:41-64` üst sekmeler: `design`, `performance`, `shootout`, `station`, `logs`.
- `main.js:231-239` URL hash yönlendirmesi: `#station` / `#3d`, `#performance`, `#shootout`.
- `uiStore.activeTab` değişince sekme içerikleri ve 3D renderer resize tetiklenir (`main.js:141-165`).

---

## 4. Hesaplama Akışı — Hangi Aşamada Hangi Değişken?

### 4.1 Aşama 0 — Kullanıcıdan beklenen girdiler

`projectStore.DEFAULT_DESIGN_INPUTS` (`projectStore.js:11-38`) ve `designSidebar.js`:

| Değişken | Varsayılan | Birim | Zorunlu? | Nerede kullanılıyor |
|---|---:|---|---|---|
| `project_name` | Yeni Kompresör Projesi | — | Hayır | Kayıt/export/PDF başlığı |
| `p_in` | 20.0 | bar(a) / bar(g) / kPa / psi | **Evet** | PR, yoğunluk, kademe hesabı |
| `p_out` | 60.0 | aynı | **Evet** | PR, kademe dağıtımı |
| `t_in` | 25.0 | °C / K / °F | **Evet** | Yoğunluk, entalpi, güç |
| `flow` | 12.0 | kg/s / Sm³/h / kg/h / MMSCFD | **Evet** | Kütle debisi, güç, türbin, istasyon |
| `gas_comp` | CH4 88, C2H6 7, C3H8 3, N2 1, CO2 1 | mol % | **Evet** (≥1 bileşen) | EOS, MW, LHV/HHV, VLE, kij |
| `eos_model` | `pr` | — | Hayır | CoolProp/PR/SRK/RK/BWRS/GERG-2008 |
| `calc_method` | Metot 6: Schultz 3-Üslü | — | Hayır | Politropik yol yöntemi (1-6) |
| `poly_eff` | 82.0 | % | Hayır | Hedef politropik verim |
| `mech_eff` | 98.0 | % | Hayır | Şaft → motor gücü |
| `therm_eff` | 35.0 | % | **UI'da yok** | Yakıt tüketimi, heat rate |
| `num_units` | 1 | adet | Hayır | Paralel tren, türbin başına güç |
| `num_stages` | 2 | adet | Hayır | Kademe döngüsü |
| `intercooler_t` | 35.0 | °C | Hayır | Kademeler arası soğutma |
| `intercooler_dp_pct` | 2.0 | % | Hayır | Ara soğutucu basınç kaybı |
| `custom_kij` | `{}` | — | Hayır | PR/SRK ikili etkileşim |

**UI'da gizli/sabit kalanlar** (`core/contracts.py:16-46`): `ambient_temp=19`, `ambient_pressure=101.325`, `altitude=0`, `humidity=60`, `use_consistency_iteration=false`, `lhv_source="kasp"`, `enable_uncertainty=false`.
`i18n/locales.js:30` "6. Saha & Çevre Şartları" adımını tanımlar ama **designSidebar'da 6. adım yoktur**; sadece 1-5 render edilir.

### 4.2 Aşama 1 — Tarayıcıda yapılan anlık hesaplar

`projectStore.js`:
- `recalculateGasTotal()` (`87-91`): gaz bileşenlerinin toplamı → yeşil/sarı `%100` rozeti.
- `recalculateLiveMetrics()` (`93-112`): yalnızca basınç birim dönüşümü + `PR = P_out/P_in`, `ΔP`.
- `updateInput()` her değişimde canlı metrikleri yeniler.
- `fetchRecommendations()` (`137-147`): gaz + PR → EOS/metot önerisi.
- `fetchKijMatrix()` (`149-161`): N×N kij.
- `runDesignCalculation()` (`163-182`): `/api/v1/calculations/design` → `results`, `selectedUnits`, `charts`.

`designSidebar.js`:
- `convertPressure/Temperature/Flow` (`11-55`): birim değişince değeri dönüştürür. Akış için **sabit** `0.772 kg/Sm³`, `0.320 kg/s per MMSCFD` kullanır.
- Hesapla butonu (`465-467`) → `runDesignCalculation()`.

### 4.3 Aşama 2 — Backend doğrulama ve normalizasyon

`calculations.py:35-58` istek modeli; `65-115` endpoint.
`validation_service.validate_design_inputs()` (`147-223`):
- Basınç: mutlak > 0; bar(g) için vakum limiti; >500 bar(a) uyarı.
- Sıcaklık: 0 K üstü; <100 K / >900 K uyarı.
- Debi: >0; >1e8 uyarı.
- `PR = P_out/P_in`; PR ≤ 1 hata; PR > 4 ve tek kademe uyarı; kademe başı PR > 4.5 uyarı.
- Gaz toplamı 100'den %1'den fazla saparsa uyarı (normalize edilir).

`contracts.normalize_design_inputs()` (`61-100`):
- `eos_model → eos_method`, `calc_method → method`, `consistency_check → use_consistency_iteration`.
- Eksik alanları varsayılanlarla doldurur, bilinmeyenleri korur.

### 4.4 Aşama 3 — Termodinamik tasarım çekirdeği

`calculation_service.execute_design_calculation()` (`87-231`):
1. Doğrulama (tekrar).
2. Normalizasyon.
3. `engine.calculate_design_performance_with_mode()`.
4. **Türbin seçimi**: API 617 marjı geri alınmış motor gücü (`power_motor_per_unit_kw`) ile `select_units(..., limit=5)`.
5. Sonuçlara UI eşitliği için `p_in_bar`, `p_out_bar`, `t_in_c`, `t_out_c`, `z/k/rho/v/a/Cp/Cv/H/S/mu/phase` eklenir (`172-224`).
6. Süre + doğrulama uyarıları.

`core/thermo_design_orchestration.py` kademe döngüsü:
- Kademe basınç oranları, ara soğutucu ΔP ve sıcaklığı.
- Her kademede EOS ile P,T,v,h,s,Z,Cp,Cv.
- Metot 1-6 ile politropik yol entegrasyonu.
- Kademeler arası **VLE flash + liquid knockout**: iki faz oluşursa sıvı ayrılır, kalan buhar debisi/kompozisyonu sonraki kademeye taşınır.
- Enerji dengesi kontrolü; geçersiz kademe `INVALID/NOT_SELECTABLE`.

`_calculate_design_energy_context()` (`thermo.py`):
- Giriş hacimsel debisi ACMH.
- Mekanik kayıp (yatak/sızdırmazlık).
- Şaft gücü = gaz gücü + mekanik kayıp.
- Motor gücü = şaft / mekanik verim.
- Sürücü gücü = motor × (1 + API 617 marjı/100). **Marj sabiti %4** (`API_617_DRIVER_MARGIN_PCT=4.0`).
- Yakıt gücü = motor / termal verim; heat rate; LHV/HHV.

`build_design_results_payload()` (`thermo_design_support.py:238-354`):
- `t_out`, `head_kj_kg`, `compression_ratio`, `actual_poly_efficiency`,
  `power_gas/shaft/motor/unit_per_unit_kw` + `_total_kw`,
  `mech_loss_*`, `fuel_*`, `heat_rate`, `lhv`, `hhv`,
  `mass_flow_*`, `inlet_vol_flow_acmh_per_unit`,
  `inlet_properties`, `outlet_properties`, `stages`,
  `method_convergence`, `analysis_scope`, `warnings`, `engine_version`.

> **Kritik birim notu:** `stages[]` içindeki `p_in/p_out` **Pa**, `t_in/t_out` **K**'dir (`thermo_design_support.py:175-200`). `calculation_service.py:213-224` bunları `p_in_bar`/`t_in_c` adlarıyla **aynı Pa/K değerleriyle** doldurur. Ön yüz ise bunları bar/°C sanır (aşağıdaki hata listesi).

### 4.5 Aşama 4 — Türbin seçimi

`core/selection.py:22-123`:
- Gerekli güç: `power_motor_per_unit_kw` (API 617 marjı hariç).
- Saha koşulları: `ambient_temp=19`, `altitude=0`, `ambient_pressure=101.325`, `humidity=60`, debi.
- 146+ türbin kaydı; ISO 2314 sıcaklık/rakım düzeltmesi (OEM eğrisi varsa onu, yoksa genel formül).
- Ön filtre: güç marjı `<0` veya `>MAX_ALLOWED_OVERSIZE_PCT` olanlar elenir.
- Ağırlıklı skor: güç uyumu, ısı oranı, surge/stonewall marjı.
- En iyi `limit=5` döner; gerçek çalıştırmada 12 kg/s / 2.44 MW için **3 uygun türbin** döndü.

### 4.6 Aşama 5 — Grafik payload'ları

`chart_data_builder.build_all_chart_payloads()` (`613-654`) üretir:

| Anahtar | İçerik | UI'da gösterim |
|---|---|---|
| `ts_diagram` | T-s gerçek + izentropik yol | ✅ `chartsView` |
| `pv_diagram` | P-v politropik/izentropik | ✅ |
| `hs_mollier` | h-s Mollier | ✅ |
| `kz_path` | PR boyunca Z ve k | ✅ |
| `stage_overview` | Kademe güç/head | ✅ |
| `turbine_radar` | İlk 4 türbin 5 eksen | ✅ |
| `turbine_derate` | ISO 2314 -20…+50°C | ✅ + `resultsView` |
| `operating_envelope` | Surge/ASCL/choke eğrileri | ✅ + alt sekme |
| `power_sankey` | Enerji akışı | ❌ **render edilmiyor** |
| `convergence` | Tutarlılık iterasyonu | ❌ **render edilmiyor** |
| `architecture_svg` | 3 katmanlı SVG | ✅ |

### 4.7 Aşama 6 — İstasyon modeli (`station_service.py`)

Girdiler: `flow/flow_unit`, `p_in(+unit)`, `p_out(+unit)`, `t_in`, `gas_comp`, `num_units`, `comp_op_count`, `cyclone_op_count`, `filter_op_count`, `cooler_bays_count`, `pipe_material`, `design_factor_F`, `design_results`.

Hesaplananlar:
- Debisi kg/s'ye çevirme; kütlesel/standart hacimsel (MMSCMD).
- Gaz MW → yoğunluk (Z≈0.89 varsayımı).
- Siklon: debi/22 kg/s → adet (N+1), ΔP = 0.30·(q/22)^1.8.
- Kartuş filtre: debi/18 kg/s → adet (N+1), ΔP = 0.22·(q/18)^1.5.
- Kompresör: debi/35 kg/s → adet (N+1); **design_results yoksa** head = 115·ln(PR), verim %82.5, T_out politropik.
- Anti-surge: surge debisi = 0.68·q_tren; ASV çapı 8/12/16"; stroking 0.8 s.
- İstasyon recycle: debi×1.0.
- Fin-fan: Q = m·2.45·(T_discharge−45)/1000 MWth; bay kapasitesi 3.2 MW.
- PSV: 1.10·P_out; BDV 15 dk; kondensat tankı; pig kovan ölçüleri.
- **8 düğüm** (N01…N08) P/T/debi/faz.
- **15 hat** boru boyutlandırma (`pipe_sizing_service.py`): Barlow et kalınlığı, ASME B36.10M çap/seçim, Churchill sürtünme, API RP 14E erozyon, hız ve ΔP/100m.

> `design_results` entegrasyonu `design_results.get("summary")` arar (`station_service.py:122-128`). Gerçek payload'da `summary` yoktur; bu yüzden **tasarım sonuçları istasyona hiç yansımaz** (doğrulandı).

---

## 5. Değişken Sözlüğü (uçtan uca)

| Değişken | Üretildiği yer | Tüketildiği yer | Not |
|---|---|---|---|
| `p_in`, `p_out`, `t_in`, `flow` | Sidebar | validation → normalize → thermo | Birim dönüşümü core'da |
| `p_in_unit`, `p_out_unit`, `t_in_unit`, `flow_unit` | Sidebar | `contracts`, `units` | Station servisi tüm birimleri desteklemez |
| `gas_comp` | gasTable | EOS, MW, LHV, VLE, kij | Web'de `METHANE` anahtarları |
| `eos_model`/`eos_method` | Sidebar | `_create_gas_object` | Alias ile eşlenir |
| `calc_method`/`method` | Sidebar | Metot seçici | Alias ile eşlenir |
| `poly_eff` | Sidebar | Hedef verim, güç | |
| `mech_eff` | Sidebar | Motor gücü | |
| `therm_eff` | Sabit 35 | Yakıt/heat rate | UI'da düzenlenemez |
| `num_units` | Sidebar | Paralel tren, toplam güç | |
| `num_stages` | Sidebar | Kademe döngüsü | |
| `intercooler_t`, `intercooler_dp_pct` | Sidebar | Kademeler arası | |
| `custom_kij` | kijModal | PR/SRK | |
| `ambient_temp`, `altitude`, `humidity`, `ambient_pressure` | Backend varsayılan | Türbin seçimi, derate | UI'da yok |
| `results.power_*` | Thermo | KPI, türbin, PDF | |
| `results.stages[]` | Thermo | Tablo/grafik | **Pa/K** |
| `results.selected_units[]` | Selection | Türbin tablosu | En fazla 5 |
| `station_summary.*` | Station | 3D HUD, özet kartlar | |
| `equipment_sizing.*` | Station | 3D/2D/inspector | |
| `nodes[]` | Station | 8 düğüm tablosu, 2D | |
| `station_piping.lines{}` | Pipe sizing | 15 hat tablosu, 3D boru yarıçapı, kesit | |
| `pipe_flows` | Station | 3D akış hızı | 3D'de doğrudan kullanılmıyor; parçacık hızı toplam debiden |
| `charts.*` | Chart builder | Plotly | İki payload UI'da kullanılmıyor |

---

## 6. 3D Görünüm — Tıklama Haritası

`station3dView.js` prosedürel olarak ~2000 satırda tesisi kurar. Tıklama mekanizması:
- `pointerdown` → konum kaydı, kamera geçişi durur (`1899-1902`).
- `pointerup` → 6 px'den fazla sürüklendiyse tıklama sayılmaz (`1918-1921`).
- `Raycaster.intersectObjects(interactiveObjects, true)` (`1927-1938`).
- Seçim: kök grubun bounding box'ı cyan ve nabız atan çerçeveyle vurgulanır (`1843-1872`).
- Sağ üstte **telemetri HUD** açılır (`1874-1891`); alt inspector drawer ve 2D SVG de senkronize edilir (`onSelectEquipment`).
- `air_coolers`, `cyclones` ve `cartridge_filters` tıklamalarında ayrıca **teardown popup** açılır (`equipmentTeardown.js`). HUD içindeki `🔧 Teardown Aç` butonu popup'ı yeniden açar.

### 6.1 Tıklanabilir ekipmanlar ve gösterilen bilgiler

| `equipKey` | 3D'de tıklanan nesne | HUD'da gösterilenler | Kamera fly-to |
|---|---|---|---|
| `pig_receiver` | PIG-R skid, izolasyon vanaları, bağlantı borusu | ⚠️ **Özel dal yok** → genel "PIG_RECEIVER" HUD'u | ❌ yok |
| `pig_launcher` | PIG-L skid, soğutulmuş gaz dönüşü | Ana hat çapı, kovan 56"x48", işletme basıncı, MOV/ESDV | ✅ |
| `safety_relief` | 22 m vent stack, kırmızı PSV vanası, yangın binası | PSV ayar basıncı, tahliye kapasitesi, BDV süresi, baca | ✅ |
| `cyclones` | MFS platformu, siklon gövdeleri, vanalar | Proses basıncı, ΔP, giriş T, ünite debisi, ayırma verimi, branşman, N+1, drenaj · 🔧 Teardown | ✅ |
| `condensate_system` | Kondensat kutusu/drenaj | Tank hacmi, sıvı üretimi, LCV kaynağı, vent | ✅ |
| `cartridge_filters` | CFS gövdeleri, vanalar, kolektör | Giriş/çıkış P, temiz ΔP, 0.3 µm, debi, branşman, N+1 · 🔧 Teardown | ✅ |
| `air_coolers` | Fin-fan bankı, fanlar, riser'lar | Giriş/çıkış T, ısıl yük, fan sayısı, ΔP, TCV, kolektör · 🔧 Teardown | ✅ |
| `cooler_bypass` | TCV by-pass hattı ve vanası | ⚠️ **Özel dal yok** → genel HUD | ✅ |
| `turbo_compressors` | Her COMPRESSOR binası içi, branşmanlar, vanalar | Emiş/basma P, PR, T, tren gücü, debi, yakıt, nozul, ASV, surge debisi, N+1 | ✅ |
| `compressor_building` | Bina dış kaplaması; ayrıca kontrol, jeneratör, hava kompresörü, admin binaları | Boyut, alan, vinç, akustik, yangın/gaz, HVAC | ✅ |
| `station_recycle` | Yükseltilmiş pipe rack, ara header, doğu vana pit | Boru çapı/malzeme, sirkülasyon kapasitesi, PCV, işlev | ✅ |
| `anti_surge` | ASV döngüsü ve vanası | ⚠️ **Özel dal yok** → genel HUD | ❌ yok |
| `tiein` | — (kayıtlı nesne yok) | — | ✅ (sadece kamera hedefi) |

> **Tutarsızlık:** `buildEquipmentTelemetryHtml` (`1695-1808`) şu anahtarları özel olarak ele alır: `cyclones`, `cartridge_filters`, `turbo_compressors`, `compressor_building`, `air_coolers`, `station_recycle`, `safety_relief`, `condensate_system`, `pig_launcher`, `tiein`. `pig_receiver`, `cooler_bypass`, `anti_surge` genel dala düşer. Ayrıca tüm yardımcı binalar `compressor_building` anahtarıyla kaydedildiği için "AUXILIARY & CONTROL BUILDING" tıklaması kompresör binası telemetrisi gösterir.

### 6.2 3D araç çubuğu ve katmanlar

| Buton | İşlev | Kod |
|---|---|---|
| Bina Kesiti | `unitCutaway → all → none` döngüsü; X-Ray'de dış kaplama gizlenir, çelik/vinç/paket görünür | `1608-1623`, `1504-1515` |
| Bakım Hacimleri | Yarı saydam gri maintenance envelope kutularını açar/kapatır | `1626-1631` |
| Akış Okları & Parçacıklar | Cyan yön okları + boru içi animasyon parçacıkları | `1634-1642` |
| 180° Boru İçi Kesit | Emiş/branşman çapı, Sch, OD, malzeme, et kalınlığı, hız, erozyon, sürtünme, ΔP | `1644-1656`, overlay `152-168` |
| Mod | CAD gündüz ↔ gece HUD; gökyüzü, zemin, ışık yoğunluğu değişir | `1659-1670` |
| Kamera presetleri | iso, top, compCutaway, manifold, filtration, cooler, tiein, control | `1585-1605` |
| HUD kapat / Fly-To | Telemetriyi kapatır; ekipmana yumuşak kamera geçişi | `1880-1890` |

### 6.3 2D P&ID tıklama haritası

`stationTab.js:598-855` SVG'si `.station-equip-group` sınıfı ve `data-equip-key` taşır. Tıklama (`544-556`) → alt inspector drawer + 3D `selectEquipment` + kamera fly-to.

| `data-equip-key` | 2D görsel | Inspector içeriği |
|---|---|---|
| `pig_receiver` | PIG-R kovanı | Kovan ölçüsü, işletme basıncı, kapak, kicker |
| `cyclones` | Dinamik S-1…S-N | N+1, debi, ΔP, drenaj |
| `cartridge_filters` | Dinamik F-1…F-N | 0.3 µm, debi, temiz ΔP, PDT |
| `compressor_building` | Ünite binası | Boyut, alan, vinç, akustik, güvenlik |
| `turbo_compressors` | CMP/GT trenleri, ASV | Güç, debi, yakıt, heat rate, nozul, ASV, surge |
| `condensate_system` | Kondensat tankı | Hacim, vent, boşaltım |
| `station_recycle` | 48" recycle header | Çap, kapasite, PCV |
| `cooler_bypass` | TCV by-pass | Vana tipi, birincil/ikincil kontrol |
| `air_coolers` | Fin-fan bayları | Isıl yük, T, fan, ΔP |
| `safety_relief` | PSV/BDV | Ayar basıncı, kapasite, süre |
| `pig_launcher` | PIG-L kovanı | Kovan, basınç, pinger |

`anti_surge` yalnızca 3D'de kayıtlıdır; 2D'de ayrı grup yoktur.

---

## 7. Modülerlik Değerlendirmesi

### Güçlü yönler
- **Katmanlı ayrım:** UI / router / service / core net.
- **Yeniden kullanım:** Web ve masaüstü aynı `ThermoEngine`, `TurbineSelector`, `PipeSizingService`'i kullanıyor.
- **Router bazlı API:** auth, users, metadata, calculations, equipment, projects, reports, jobs, logs ayrı dosyalar.
- **Zero-build:** npm/Node gerektirmeden çalışır; air-gapped dağıtıma uygun.
- **Store deseni:** küçük, bağımlılıksız pub/sub; bileşenler abone oluyor.
- **SSE:** shootout ve log akışı için doğru tercih.
- **3D:** prosedürel üretim sayesinde tek HTML/JS ile tam tesis; harici model dosyası yok.

### Zayıf yönler
- **Dev bileşenler:** `station3dView.js` 2081, `stationTab.js` 1561, `resultsView.js` 901 satır. Test edilebilirlik ve bakım maliyeti yüksek.
- **Manuel DOM:** `innerHTML` + `querySelector` + tekrar bağlama; 32 `innerHTML` kullanımı. Odak kaybı, XSS ve tutarsız render riski.
- **Sözleşme testi yok:** Ön yüzün beklediği alan adları ile backend payload'ları arasında otomatik sözleşme testi yok; bu yüzden aşağıdaki hatalar fark edilmemiş.
- **Çift varsayılan seti:** `projectStore.DEFAULT_DESIGN_INPUTS` ↔ `core/contracts.DESIGN_INPUT_DEFAULTS` farklı değerler taşıyor.
- **i18n kısmi:** `t()` yalnızca başlık/sekme/butonlarda; kartlar, tablolar, 3D HUD ve modalların çoğu hardcoded Türkçe.
- **Grafik payload israfı:** `power_sankey` ve `convergence` hesaplanıp gönderiliyor ama render edilmiyor.
- **Statik/varsayılan değerler gerçekmiş gibi sunuluyor:** OPEX ($0.35/Sm³, $50/ton, 8000 saat), availability (%96.5/%99.85), PTC-10 belirsizlikleri (±%1.25/2.10/1.50), bazı KPI fallback'leri.

---

## 8. Tespit Edilen Hatalar / Tutarsızlıklar (öncelikli)

> **Düzeltme durumu (2026-11-09):** Aşağıdaki **P0-1 … P0-6** hataları giderildi. Ayrıca P1-7 (API 617 marj etiketi), P1-9 (grafik birim dönüşümü), P1-12 (3D telemetri eksikleri) ve PTC-10 sözleşmesi düzeltildi. Yeni regresyon testleri eklendi: `test_services.py`, `test_station_service.py`.

### ✅ Düzeltilenler

| No | Düzeltme | Değişen dosyalar |
|---|---|---|
| P0-1 | Kademe `p_in_bar/p_out_bar/t_in_c/t_out_c` artık Pa/K'den doğru türetiliyor; grafikler de aynı dönüşümü kullanıyor | `calculation_service.py`, `chart_data_builder.py`, `resultsView.js` |
| P0-2 | İstasyon MW'si `MOLAR_MASSES` + `normalize_component` ile hesaplanıyor; `METHANE/CH4` ikisi de çalışıyor | `station_service.py` |
| P0-3 | `mass_flow` (kg/s slider) `flow`'dan öncelikli; web slider'ı artık etkili | `station_service.py`, `stationTab.js` |
| P0-4 | İstasyon gerçek `power_shaft_per_unit_kw`, `t_out_c`, `head_kj_kg`, `actual_poly_efficiency` alanlarını kullanıyor; PR değişirse yerel tahmine düşüyor | `station_service.py`, `stationTab.js` |
| P0-5 | PTC-10 karşılaştırması hem eski hem web alan adlarını üretiyor; durumlar `OK/WARNING/CRITICAL` | `performance_service.py`, `performanceTab.js` |
| P0-6 | `bar(g)` / `K` / `°F` istasyon servisinde `UnitSystem` ile dönüştürülüyor | `station_service.py` |
| P1-7 | API 617 marjı etiketi çekirdekten (`api_617_margin_percent`, %4) okunuyor | `resultsView.js` |
| P1-9 | P-v, T-s ve kademe grafikleri kullanıcı basınç/sıcaklık birimlerini bar(a)/°C'ye çeviriyor | `chart_data_builder.py` |
| P1-12 | `pig_receiver`, `cooler_bypass`, `anti_surge` için özel 3D telemetri + kamera hedefleri eklendi | `station3dView.js` |

### Açık kalanlar

### P0 — Sonucu doğrudan yanlış gösterenler

1. **✅ Düzeltildi — Kademe sıcaklık/basınç birimleri yanlış.**
   - Backend `stages[].p_in/p_out` Pa, `t_in/t_out` K.
   - `calculation_service.py:217-224` bunları `p_in_bar/t_out_c` adlarıyla aynı değerlerle dolduruyor.
   - `resultsView.js:275-284` `p_in_bar` ve `t_out_c`'yi bar/°C sanıp `.toFixed()` ediyor.
   - Doğrulama: gerçek çalıştırmada `p_in_bar=2000000.0`, `t_out_c=346.1` (aslında 73 °C) döndü.
   - Etki: "Güç & Kademe VLE" tablosu ve T-s/stage grafikleri yanlış eksen gösterir.

2. **✅ Düzeltildi — İstasyon gaz molekül ağırlığı (MW) yanlış.**
   - `station_service.py:74` `mw_map` anahtarları `CH4, C2H6, C3H8, N2, CO2, H2`.
   - Web `gas_comp` anahtarları `METHANE, ETHANE, PROPANE, NITROGEN, CARBONDIOXIDE`.
   - Eşleşme yok → her bileşen `16.04` varsayılanına düşer → **MW her zaman 16.04**.
   - Etki: yoğunluk, MMSCMD, boru hızı/ΔP, ısıl yük, tüm istasyon boyutlandırması sapar.

3. **✅ Düzeltildi — İstasyon debi slider'ı/`mass_flow` girdisi yok sayılıyor.**
   - `station_service.py:35` önce `inputs.get("flow")` okuyor.
   - `stationTab.js:61-68` `mass_flow` yazıyor; `flow` proje girdisinden geliyor.
   - Doğrulama: `flow=12`, `mass_flow=300` → sonuç yine 12 kg/s.
   - Etki: "Canlı İşletme Parametreleri" debi kaydırıcısı ve reset varsayılanı (120 kg/s) çalışmıyor.

4. **✅ Düzeltildi — Tasarım sonuçları istasyon modeline aktarılmıyor.**
   - `station_service.py:122-128` `design_results["summary"]` arıyor; gerçek payload'da `summary` yok.
   - Doğrulama: `power_shaft_total_kw=9999` verilse bile istasyon gücü 1.88 MW kaldı.
   - Ayrıca `stationTab` başlangıçta bir kez fetch ediyor; tasarım tamamlanınca yeniden fetch tetiklenmiyor.

5. **✅ Düzeltildi — ASME PTC-10 performans tablosu alan adları uyuşmuyor.**
   - Backend: `parameter`, `test_value`, `design_value`, `deviation_pct`, `status = valid|warning|critical` (`performance_service.py:106-114`).
   - Frontend: `row.name`, `row.test_val`, `row.design_val`, `row.dev_pct`, `row.tol_crit`, `status === "OK"` (`performanceTab.js:113-125`).
   - Etki: parametre adları boş, değerler `undefined`, tüm satırlar kırmızı "kritik" görünür.

6. **✅ Düzeltildi — bar(g) istasyon servisinde mutlak basınca çevrilmiyor.**
   - `station_service.py:58-64`: `"bar" in unit` kontrolü bar(g)'yi de bar(a) sayıyor; +1.01325 eklenmiyor.
   - Doğrulama: 20/60 bar(g) → 20/60 bar(a) ve PR=3.0.
   - Etki: emiş/basma, PR, PSV ve boru boyutlandırma hatalı.

### P1 — Ciddi ama daha sınırlı etkili

7. **✅ Düzeltildi — UI'daki API 617 marjı ile motor marjı çelişiyor.**
   - Motor/sürücü gücü kartı "API 617 (%10)" diyor (`resultsView.js:593`).
   - Çekirdek `API_617_DRIVER_MARGIN_PCT=4.0` kullanıyor; `power_unit_kw = motor × 1.04`.
   - Türbin seçimi de 1.04 ile geri alıyor.

8. **Türbin tablosu "146+ Uygun Model" diyor, gerçekte en fazla 5.**
   - `calculation_service.py:152-157` `limit=5`; gerçek çalıştırmada 3 döndü.
   - Başlık `resultsView.js:716` `units.length` gösterse de üst metin/başlık 146+ imajı veriyor.

9. **✅ Düzeltildi — Grafiklerde birim dönüşümü yapılmıyor.**
   - P-v grafiği `inputs.p_in`/`p_out` değerlerini doğrudan bar kabul ediyor (`chart_data_builder.py:91-92`). Girdi kPa/psi/bar(g) ise eksen yanlış.
   - T-s grafiği `stages[].p_in` (Pa) ve `t_in` (K) değerlerini °C/bar gibi işliyor (`chart_data_builder.py:35-52`).

10. **Saha/çevre koşulları UI'da yok, varsayılanlar tutarsız.**
    - `locales.js:30` 6. adım var, `designSidebar` yok.
    - API `normalize` `ambient_temp=19` kullanıyor; `chart_data_builder` `15°C` varsayıyor; `resultsView` `proj.inputs.t_amb || 15` okuyor (alan hiç yok).
    - Etki: derate ve türbin seçimi farklı ortam sıcaklıklarına göre hesaplanabilir.

11. **`power_sankey` ve `convergence` hesaplanıyor ama gösterilmiyor.**
    - `chart_data_builder.py:646,652`; `chartsView.js:130-139` kuyruğunda yok.

12. **✅ Düzeltildi — İstasyon 3D telemetrisinde eksik anahtarlar.**
    - `pig_receiver`, `cooler_bypass`, `anti_surge` genel HUD'a düşüyor.
    - `EQUIP_CAMERA_TARGETS` içinde `pig_receiver` ve `anti_surge` yok; `tiein` hedefi var ama tıklanabilir nesne yok.
    - Yardımcı binalar `compressor_building` anahtarıyla kaydediliyor.

13. **İstasyon "Hesapla" butonu mevcut parametreleri kullanmıyor olabilir.**
    - `btn-recalc-station` doğrudan `fetchStationData` çağırır; paneldeki input değerleri yalnızca `change/input` event'lerinde `stationInputs`'a yazılır. Kullanıcı yazıp butona basarsa `change` tetiklenmemişse eski değer kullanılır.

### P2 — Bakım / güvenlik / tutarlılık

14. **CSRF altyapısı var ama hiç kullanılmıyor.**
    - `kasp/api/auth.py:204-232` `validate_csrf` tanımlı; hiçbir router `Depends(validate_csrf)` kullanmıyor.
15. **Hesaplama uç noktaları kimlik doğrulama gerektirmiyor.**
    - `calculations.py` tüm endpoint'lerde `get_current_user_optional`; design/performance/station/pipe-sizing oturumsuz çağrılabilir.
    - `/reports/pdf` ise `get_current_user` (zorunlu) — oturumsuz kullanıcı PDF alamaz, UI bunu önceden bildirmez.
16. **XSS yüzeyi:** `logsTab.js:52` log mesajını, `projectModal.js` proje adını, `header.js:29` proje adını `innerHTML` ile basıyor. Sunucu/DB kaynaklı metinler kaçışsız.
17. **Token `localStorage`'da:** `api/client.js:10-23`. HttpOnly cookie de destekleniyor ama Bearer token kalıcı.
18. **Log temizleme yetkisiz:** `DELETE /api/v1/logs` optional auth.
19. **README ve sürüm bilgisi eski:** README Vue/Tailwind diyor; status bar `v4.1.0`, `kasp_config.json` `2.6.2`, `release_metadata` farklı olabilir.
20. **`resultsView` içinde çok sayıda sentetik değer:** OPEX, availability, PTC-10 belirsizlikleri, fallback karşılaştırma yüzdeleri gerçek hesap çıktısı değil.

---

## 9. Doğrulama Notları

Aşağıdakiler bu analiz sırasında gerçek Python çağrılarıyla doğrulandı:

- `execute_design_calculation` (12 kg/s, 20→60 bar(a), 2 kademe, PR):
  - `power_shaft_total_kw = 2297.51`, `power_unit_kw = 2438.17`, `t_out_c = 84.4`.
  - `stages[0].p_in = 2,000,000.0`, `t_out = 346.12` → birim hatası doğrulandı.
  - `selected_units = 3` → türbin limiti doğrulandı.
- `calculate_station_process_model`:
  - `gas_mw = 16.04` → MW anahtar hatası doğrulandı.
  - `flow=12`, `mass_flow=300` → 12 kg/s → debi önceliği hatası doğrulandı.
  - 20/60 bar(g) → 20/60 bar(a), PR=3.0 → bar(g) hatası doğrulandı.
  - `design_results` verilse bile güç 1.88 MW'da kaldı → entegrasyon yok.
- `pipe_sizing_service`/`test_pipe_sizing.py`: 15 hat, Barlow, API RP 14E, hız ve status üretimi çalışıyor.

---

## 10. Hızlı Dosya Referansı

| Katman | Dosya | Satır | İçerik |
|---|---|---:|---|
| Boot | `kasp/web/src/main.js` | 247 | Layout, tab, mount, init |
| Store | `store/projectStore.js` | 182 | Girdi/sonuç/canlı metrik |
| Store | `store/uiStore.js` | 59 | Tab/tema/modal/toast |
| Store | `store/authStore.js` | 91 | Oturum/RBAC |
| API | `api/client.js` | 148 | Fetch, Bearer, CSRF, download |
| Girdi | `components/designSidebar.js` | 472 | 5 adım, birim dönüşümü, preset |
| Gaz | `components/gasTable.js` | 195 | 19 gaz, normalize, kij |
| Sonuç | `components/resultsView.js` | 901 | KPI, 7 alt sekme, türbin, derate |
| Grafik | `components/chartsView.js` | 344 | 8 Plotly + SVG |
| Performans | `components/performanceTab.js` | 192 | PTC-10 saha doğrulama |
| Shootout | `components/shootoutTab.js` | 270 | EOS×metot, SSE |
| İstasyon | `components/stationTab.js` | 1561 | Özet, 2D P&ID, düğümler, boru |
| 3D | `components/station3dView.js` | 2081 | Three.js tesis, tıklama, HUD, teardown bağlantısı |
| 3D | `components/equipmentTeardown.js` | — | Patlatılmış 3D ekipman söküm popup'ı |
| Log | `components/logsTab.js` | 146 | REST + SSE |
| API | `kasp/api/v1/calculations.py` | 213 | design/performance/station/pipe-sizing |
| API | `kasp/api/v1/*.py` | — | auth, users, meta, equipment, projects, reports, jobs, logs |
| Servis | `services/calculation_service.py` | 231 | Tasarım orkestrasyonu + türbin |
| Servis | `services/station_service.py` | 474 | İstasyon modeli |
| Servis | `services/pipe_sizing_service.py` | 379 | 15 hat boru ağı |
| Servis | `services/performance_service.py` | 154 | PTC-10 |
| Servis | `services/chart_data_builder.py` | 654 | Grafik payload |
| Servis | `services/validation_service.py` | 223 | Fiziksel doğrulama |
| Core | `core/thermo.py` | 1400+ | Termodinamik motor |
| Core | `core/thermo_design_orchestration.py` | — | Kademe döngüsü, VLE |
| Core | `core/thermo_design_support.py` | 380+ | Sonuç payload, stage |
| Core | `core/selection.py` | 200+ | Türbin seçimi |
| Core | `core/pipe_sizing.py` | 367 | ASME/API boru |
| Core | `core/contracts.py` | 116 | Varsayılanlar, alias |
| Core | `core/constants.py` | 200+ | Gazlar, kij, sabitler |

---

## 11. Önerilen İyileştirme Sırası

1. **Birim sözleşmesini tekilleştir:** `stages[]` için `_si` ve `_display` alanlarını ayır; `calculation_service` dönüşümü doğru yapsın.
2. **Station gaz haritasını merkezileştir:** `constants.MOLAR_MASSES` + `ALIAS_MAP` kullan; `CH4`/`METHANE` ikisini de destekle.
3. **Station girdi sözleşmesini düzelt:** `flow` yerine `mass_flow/flow_unit` önceliği; slider'ı `flow`'a yaz veya servisi `mass_flow`'a önceliklendir.
4. **`design_results` şemasını hizala:** `summary` yerine gerçek `power_*`, `t_out`, `head_kj_kg`, `mass_flow_per_unit_kgs` alanlarını oku.
5. **PTC-10 alan adlarını eşle:** backend `name/test_val/design_val/dev_pct/tol_crit/status` üretsin veya frontend `parameter/test_value/...` okusun; status `OK/WARNING/CRITICAL`.
6. **bar(g) dönüşümünü station'da `UnitSystem` ile yap.**
7. **API 617 marjını tek kaynaktan (4 veya 10) yayınla; UI metnini düzelt.**
8. **UI'da olmayan `therm_eff`, `ambient_temp`, `altitude`, `humidity` alanlarını 6. adım olarak ekle.**
9. **Kullanılmayan grafikleri kaldır veya render et; statik OPEX/availability değerlerini "varsayım" olarak etiketle.**
10. **Ön yüz sözleşme testleri + E2E smoke testleri ekle** (design → results → station → 3D tıklama → PDF).

---

*Bu belge, kodun mevcut hâlinin haritasıdır; düzeltmeler uygulandıkça güncellenmelidir.*
