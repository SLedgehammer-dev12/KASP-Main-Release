# KASP Entegrasyon Faz 1B — Air-Cooler & Control Valve

Tarih: 2026-11-09  
Kapsam: Air-Cooler-Main ve Control Valve Sizing adaptörleri + istasyon entegrasyonu.

---

## 1. Tamamlananlar

### 1.1 Air-Cooler-Main modülü

```
kasp/integrations/air_cooler/
  adapter.py
  vendor/
    air_cooler_main_core.py
    air_cooler_neqsim.py
    air_cooler_users.py
```

Yetenekler:
- Gerçek gaz termodinamiği (CoolProp HEOS / SRK / PR)
- Fin-fan ısıl yük, LMTD/Ft, U değeri
- Gerekli/gerçek yüzey alanı, overdesign
- Gaz tarafı ΔP (sürtünme + minor)
- Fan gücü, fan uç hızı, fan ses gücü
- API 661 / ASME VIII-1 ön kontroller
- Otomatik boyutlandırma: `tubes_per_row` artırılarak min. overdesign ve max. ΔP sağlanır

Varsayılan geometri:
- 4 sıra, 2 geçiş, 24 tüp/sıra
- 1" tüp OD, 2.11 mm et kalınlığı
- 15.9 mm fin yüksekliği, 10 FPI
- 6 m tüp boyu, 63.5 mm pitch, 30° dizilim
- 2.44 m fan, 350 RPM, %65 fan verimi

Örnek (12 kg/s, 60→59.6 bar, 84.4→45 °C):
- Isıl yük: **~1,038 kW**
- Otomatik boyut: **4 sıra × 40 tüp**
- Gerekli/gerçek alan: **~1,370 / 1,486 m²**
- Overdesign: **%8.5**
- Gaz ΔP: **~0.47 bar**
- Fan gücü: **~11.9 kW**
- Fan uç hızı: **44.7 m/s** (API 661 ≤ 61 m/s)

> Not: Detaylı air-cooler hesabı istasyon servisinde varsayılan olarak **kapalıdır** (`include_air_cooler_design=False`), çünkü otomatik boyutlandırma 10+ saniye sürebilir. İstasyon ekranındaki **"API 661 Detaylı Tasarım"** butonu ile isteğe bağlı çalıştırılır.

### 1.2 Control Valve Sizing modülü

```
kasp/integrations/control_valve/
  adapter.py
  vendor/
    valve_sizing.py
    units.py
    valve_noise.py
    valve_selection.py
    trim_guidance.py
    actuator_sizing.py
    two_phase.py
```

Yetenekler:
- IEC 60534-2-1 / ISA 75.01.01 Cv/Kv
- Gaz ve sıvı servisi
- Choked flow kontrolü
- Vana seçimi, açıklık oranı, rangeability
- IEC 60534-8-4 gürültü tahmini
- Aktüatör itki/seçim ön kontrolü
- Trim önerileri (anti-kavitasyon, düşük gürültü, çok kademeli letdown)

KASP entegrasyonu:
- Gaz kompozisyonundan GERG-2008 ile Z/MW/k/viskozite
- Normal debi hesabı (15 °C, 1.01325 bar)
- İstasyon ASV / PCV / TCV otomatik boyutlandırma
- 3D telemetri ve inspector'da vana çapı/Cv/açıklık gösterimi

Örnek (12 kg/s, 60→20 bar ASV):
- Gerekli Cv: **41.7**
- Seçilen vana: **2"**
- Açıklık: **%96.4**
- Gürültü: **65.9 dB**
- Uyarı: açıklık > %85, çıkış Mach 0.70 → daha büyük vana / çok kademeli trim önerilir

### 1.3 İstasyon entegrasyonu

`station_service` çıktısına eklendi:
- `turbo_compressors.anti_surge_valve_sizing`
- `station_recycle.pcv_sizing`
- `air_coolers.cooler_bypass_valve_sizing`
- `air_coolers.detailed_design` (opsiyonel)
- `safety_relief_and_blowdown.psv_sizing`

UI:
- Turbo-kompresör inspector: ASV IEC 60534 boyutu
- Anti-surge inspector: Cv / gürültü
- Recycle inspector: PCV boyutu
- Cooler by-pass inspector: TCV boyutu
- Air cooler inspector: **API 661 Detaylı Tasarım** butonu
- 3D telemetri: aynı bilgiler

---

## 2. Bağımlılıklar

`requirements.txt` / `requirements.lock.txt`:
- `pint==0.25.3`
- `ht==1.2.0`
- `fluids==1.3.0`

Bu üç paket Air-Cooler ve Control Valve çekirdekleri için zorunludur. KASP'ta opsiyonel modül yüklenemezse registry o modülü listelemez; diğer modüller çalışmaya devam eder.

---

## 3. API

Yeni modüller registry'ye eklendi:

```bash
GET  /api/v1/modules
POST /api/v1/modules/air_cooler/calculate
POST /api/v1/modules/control_valve/calculate
```

Örnek air cooler:

```json
{
  "payload": {
    "composition": {"METHANE": 88, "ETHANE": 7, "PROPANE": 3, "NITROGEN": 1, "CARBONDIOXIDE": 1},
    "mass_flow_kgs": 12.0,
    "p_in_bar": 60.0,
    "p_out_bar": 59.6,
    "t_in_c": 84.4,
    "t_out_c": 45.0,
    "auto_size": true
  }
}
```

Örnek control valve:

```json
{
  "payload": {
    "service": "gas",
    "composition": {"METHANE": 88, "ETHANE": 7, "PROPANE": 3, "NITROGEN": 1, "CARBONDIOXIDE": 1},
    "mass_flow_kgs": 12.0,
    "p_in_bar": 60.0,
    "p_out_bar": 20.0,
    "t_c": 84.4,
    "path": "ASV"
  }
}
```

---

## 4. Doğrulama

`test_integrations.py` genişletildi:
- Air-Cooler detaylı tasarım
- Control Valve gaz boyutlandırma
- İstasyon ASV/PCV/TCV/PSV ve API 5L entegrasyonu

**Sonuç:** Entegrasyon + station + pipe + services: **25 passed**.  
Geniş regresyon: **87 passed**.  
JS syntax kontrolleri geçti.

---

## 5. Bilinen sınırlar

- Air-Cooler detaylı tasarımı ağırdır (~3–11 s); bu nedenle istasyon canlı güncellemelerinde varsayılan kapalıdır.
- Control Valve `steam` servisi adaptörde henüz açık değil; gaz/sıvı destekleniyor. Buhar için `SteamSizingInput` eklenebilir.
- Vana kataloğu temsilîdir; nihai seçim üretici yazılımı ile doğrulanmalıdır.
- Air-Cooler geometrisi varsayılan API 661 değerleridir; proje-spesifik geometri `geometry` alanıyla override edilebilir.
- `pint`, `ht`, `fluids` paketlenmiş uygulamaya dahil edilmelidir (PyInstaller hidden imports gerekebilir).

---

## 6. PDF Rapor Entegrasyonu

`ReportGenerator.generate_design_report()` artık `results["module_results"]` ve
`results["station_data"]` alanlarını okuyup rapora **"9. ENTEGRE MODÜL SONUÇLARI"**
bölümünü ekliyor.

Kapsanan modüller:
- 9.1 PSV / Emniyet Vanası (API 520/521)
- 9.2 Boru Et Kalınlığı (API 5L / BOTAŞ)
- 9.3 Hat Hidroliği (ASME B36.10M / API RP 14E)
- 9.4 Fin-Fan Hava Soğutucu (API 661)
- 9.5 Kontrol Vanası (IEC 60534)
- 9.6 İstasyon Özeti
- 9.7 Modül Uyarıları

Web arayüzünde **PDF Rapor İndir** butonu artık `modules` ve `station_data`
alanlarını da gönderiyor. Backend bu alanları rapor sonuçlarına birleştiriyor.

## 7. Proje Kalıcılığı

- `projectStore` içine `modules` ve `stationData` eklendi.
- İstasyon modeli her fetch'te `stationData` olarak saklanıyor.
- Air-Cooler detaylı tasarımı `modules.air_cooler` olarak saklanıyor.
- **Kaydet** ve **.kasp Dışa Aktar** artık modül/istasyon verilerini gönderiyor.
- Backend:
  - DB kaydında `results.module_results` ve `results.station_data` olarak saklanır.
  - `.kasp` dışa aktarımında üst düzey `modules` / `station_data` alanları eklenir.
  - `.kasp` içe aktarımında bu alanlar geri döner.
- **Geçmiş Projeler** modalından yükleme ve `.kasp` içe aktarma, modül/istasyon
  verilerini `projectStore`'a geri yükler.

## 8. Doğrulama

- Entegrasyon testleri: `test_integrations.py` → 11 passed.
- API testleri: `test_api_v1.py` → proje export/import ve PDF modül testleri dahil.
- **Tam test seti:** `460 passed, 12 skipped`.
- JS syntax kontrolleri geçti.

## 9. Ek Tamamlananlar (Faz 1C)

### 9.1 Air-Cooler 3D geometri senkronizasyonu

`station3dView.js` artık `equipment_sizing.air_coolers.detailed_design.geometry`
alanını okur:

- `tube_rows`
- `tubes_per_row`
- `tube_length`
- `n_fans`
- `fan_diameter`

3D cooler:
- Bay genişliği tüp sayısına göre ölçeklenir.
- Cooler derinliği tüp boyuna göre ölçeklenir.
- Fan sayısı ve fan çapı geometriden gelir.
- `GAS COOLER` etiketinin altında `4x40 TUBES` gibi dinamik etiket görünür.
- Detaylı tasarım tamamlanınca 3D sahne yeniden kurulur.

### 9.2 Excel/JSON modül raporları

- `GET/POST /api/v1/reports/modules-excel` eklendi.
- `kasp/services/module_report_service.py` ile çok sayfalı XLSX:
  - Özet
  - PSV
  - API5L
  - Hidrolik
  - AirCooler
  - KontrolVanasi
  - Istasyon
  - BoruHatları
  - Uyarılar
- `/api/v1/projects/export-results-json` artık `modules` ve `station_data` alanlarını da döndürür.
- Web header'a **Modül Excel** butonu eklendi.
- `openpyxl` bağımlılığı eklendi.

### 9.3 Modül şema migrasyonu

- `kasp/integrations/schema.py` eklendi.
- `MODULE_SCHEMA_VERSION = "1.0"`.
- Eski `schema_version` olmayan modül yükleri otomatik zarflanır.
- Daha yeni şema sürümleri uyarı ile korunarak okunur.
- `.kasp` içe aktarma ve `ProjectManager.load_project` sırasında
  `modules` ve `results.module_results` otomatik migrate edilir.

### 9.4 Gaz soğutucu ve kompresör boru hattı çap/geometri denetimi

- `PipeSizingService.size_station_network` suction ve discharge header'ları aynı
  ticari NPS'te eşitler (büyük olan çap seçilir, diğeri yeniden boyutlandırılır).
- 3D boru yarıçapları sabit değerler yerine `station_piping.lines[*].od_mm`
  değerlerinden tek görsel ölçekle türetilir.
- Kompresör emiş, basma ve anti-surge branşmanları ayrı çaplarda gösterilir.
- Gaz soğutucu inlet/outlet/riser/by-pass hatları kendi ASME OD'leriyle çizilir.
- Cooler by-pass batı uca alındı; soğuk header'ı ve doğu riser demetini kesmiyor.
- Soğuk riser'lar sıcak header üzerinden `y=3.0`'da geçer.
- Cooled gas return `y=3.8`'e kaldırıldı; sıcak header drop'u ve CFS kollektörü
  ile temas etmiyor.
- ASV loop'ları `y=4.2` üzerinden mevcut ara header'a (`z=-13.6`) iner;
  suction branch'a doğrudan girmez.
- Her ünite ASV loop'u suction ve discharge header'lar arasındaki mevcut
  **anti-surge / recycle header**'a bağlanır; header tek noktadan suction
  header'a döner.
- Discharge header doğrudan anti-surge header'a bağlanmaz; doğu ucundan gas
  cooler besleme hattına bağlanır.
- Gas cooler beslemesi, 3+ ünite düzenlerinde suction/anti-surge/discharge
  header'ların doğusundan dolaşır; hiçbir header'ı kesmez.
- Cooler outlet riser, cooled gas return, by-pass ve ASV crossing kotları boru
  çaplarına göre dinamik hesaplanır.
- MFS multi-siklon seperatörleri yatay gövdeden **dikey gövde + üst dome + konik
  alt + 3 destek ayağı** modeline çevrildi; CFS kartuş filtreleri yatay kaldı.
- CFS çıkışlarında üst üste binen iki hat yerine tek ortak outlet collector
  header kullanıldı.
- Türbin egzoz bacaları yere dik hale getirildi; türbin skid ile aynı renkte
  yatay geçiş kanalı ve dirsek ile bağlandı.
- 3D pipe inspector overlay'i header eşitliğini, kompresör branşmanlarını,
  ASV header'ı ve cooler çaplarını canlı gösterir.
- Programatik segment denetimi: bağlantı noktaları hariç 0 boru-boru çakışması.
- Ayrıntılar: `KASP_3D_PIPE_AUDIT.md`.

## 10. Son test durumu

- **Tam test seti:** `466 passed, 12 skipped, 0 failed`.
- JS syntax kontrolleri geçti.

## 11. Kalan tek kapsam

- Control Valve **steam** servisi (kullanıcı talebiyle kapsam dışı bırakıldı).
- İsteğe bağlı: Excel raporuna grafik/embed, modül sonuçlarının 3D sahneye tam entegrasyonu.
