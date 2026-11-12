# KASP 3D Boru Yüzey Bütünlüğü ve Çap Denetimi

Tarih: 2026-11-10  
Kapsam:
- `kasp/web/src/components/station3dView.js` prosedürel 3D tesis modeli
- `kasp/services/pipe_sizing_service.py` istasyon boru ağı
- Gaz soğutucu giriş / çıkış / baypas hatları
- Turbo-kompresör emiş / basma / anti-surge hatları

Yöntem:
1. Tüm `createCadPipeRoute()` rotalarının noktaları ve çapları çıkarıldı.
2. Tarayıcıda 3D sahne çalıştırıldı; cutaway (X-Ray) görünümde kompresör binası ve gaz soğutucu görsel olarak kontrol edildi.
3. `window.__KASP_3D__.audit()` ile 40 boru rotası ve 1.605 mesh programatik olarak denetlendi.
4. Boru-boru çakışması, her segment çifti için eksen mesafesi − (r1 + r2) hesabıyla denetlendi. Kesişen bağlantı noktaları (tee/elbow) ayrı tutuldu.
5. Boruların ekipman gövdeleri, foundation, fan/louver ve instrument kutularıyla yüzey teması AABB + boru yarıçapı ile kontrol edildi.

---

## 1. Bulunan ve düzeltilen kritik süreksizlikler

| # | Sorun | Düzeltme |
|---|---|---|
| 1 | Kompresör binası içindeki `inPipe1`/`inPipe2` dekoratif boruları dış hatlara bağlanmıyordu. | Dekoratif borular kaldırıldı; barrel nozzle'larına giden gerçek rotalar eklendi. |
| 2 | Suction branch kompresör barrelının kuzey nozzle'ına ulaşmıyordu. | `north-wall → barrel north nozzle` rotası eklendi. |
| 3 | Discharge branch barrelın güney nozzle'ına bağlanmıyordu. | `barrel south top → skid üstü → discharge branch` rotası eklendi. |
| 4 | Discharge branch header'a `y=1.8`'de bağlanıyordu. | Branch son noktası header merkezi `y=1.5` yapıldı. |
| 5 | Filtered suction collector header'a 0.1 m sapmalı bağlanıyordu. | `(-32,1.5,-16.2)` header merkezine alındı. |
| 6 | MFS siklon çıkışları ile CFS inlet arasında ortak header yoktu. | MFS outlet collector ve CFS bağlantısı eklendi. |
| 7 | Pig receiver ile MFS inlet arasında 4 m kopukluk vardı. | Pig receiver rotası `(-72,2.2,-92)`'ye getirildi. |
| 8 | Cooler inlet header discharge header'a bağlanmıyordu. | Discharge header'dan cooler inlet header'a tap eklendi. |
| 9 | Cooler outlet header yoktu. | `z=-48` outlet header eklendi. |
| 10 | Cooler by-pass iki ucu boşta duruyordu. | Sıcak/soğuk header arasına kapalı U-loop olarak bağlandı. |
| 11 | Cooled gas return pig launcher'a 2 m mesafede bitiyordu. | `(-122,2.2,-52)` launcher minor barrel ucuna bağlandı. |
| 12 | Suction ve discharge arasındaki ara header izoleydi. | Tek noktadan suction header'a bağlandı; anti-surge / recycle header olarak kullanılıyor. |
| 13 | `TubeGeometry` açık uçları delik gibi görünüyordu. | Her rota ucuna spherical weld cap eklendi. |
| 14 | `${Math.round(...):,}` geçersiz template expression tüm web uygulamasını durduruyordu. | `toLocaleString('tr-TR')` ile düzeltildi. |
| 15 | `headerEastX` tanımdan önce kullanılıyordu (TDZ). | Header sabitleri fonksiyon başına taşındı. |
| 16 | Suction header 10", discharge header 6" seçiliyordu. | `PipeSizingService.size_station_network` iki header'ı büyük olan NPS'te (10") eşitler; discharge yeniden boyutlandırılır. |
| 17 | 3D boru çapları sabit değerlerdi (0.78 / 0.58 / 0.48). | Tüm proses hatları ASME OD'sinden tek görsel ölçekle (`visualPipeRadius`) türetilir. |
| 18 | Kompresör emiş ve basma branşmanı aynı 3D yarıçapı kullanıyordu. | `rCompSuctionBranch` (10"), `rCompDischargeBranch` (6"), `rAntiSurge` (5") ayrıldı. |
| 19 | Cooler inlet/outlet/riser/by-pass sabit yarıçaplıydı. | 6" / 6" / 5" / 3.5" ASME OD'lerinden türetildi. |
| 20 | By-pass soğuk header'ı dik kesiyor ve doğu riser demetine giriyordu. | Batı uca alındı: `(-4,-54) → y=5.2 → z=-48 → x=0 → cold header`; TCV `(-1, 5.2, -48)`. |
| 21 | Soğuk çıkış riser'ı zeminde ilerleyip sıcak header'ı `z=-54`'te kesiyordu. | Riser `z=-48`'de `y=3.0`'a yükselip sıcak header'ın üzerinden geçirildi. |
| 22 | Cooled gas return, sıcak header drop'unu (`x=-4`) ve CFS kollektörünü (`x=-12`) kesiyordu. | Hat `y=3.8`'e kaldırıldı; her iki hat üzerinden açık geçiş sağlandı. |
| 23 | ASV loop'ları ayrı ayrı suction branch'a bağlanıyordu. | Mevcut ara header (z = -13.6) anti-surge header olarak kullanıldı; ünite loop'ları bu header'a, header da tek noktadan suction header'a bağlandı. |
| 24 | Anti-surge header'a ayrı bir dördüncü header eklenmişti. | Fazladan `z = -7.5` header'ı kaldırıldı; mevcut suction/discharge arası header kullanıldı. |
| 25 | Discharge header, ara header'a U-tie'lerle bağlıydı. | Discharge header bağlantıları kaldırıldı; discharge header yalnızca gas cooler besleme hattına bağlandı. |
| 26 | MFS siklon seperatörleri yatay/eğik silindir olarak modellenmişti. | Dikey gövde + üst dome + konik alt + 3 destek ayağı olarak yeniden modellendi. |
| 27 | CFS çıkış hatları iki filtre arasında üst üste biniyordu. | Tek ortak CFS outlet collector header eklendi. |
| 28 | Türbin egzoz bacaları 0.38 rad eğik ve koyu renkteydi. | Bacalar yere dik hale getirildi; türbin skid rengiyle aynı malzeme ve yatay geçiş kanalı + dirsek ile bağlandı. |
| 29 | Büyütülen 10" suction borusu foundation plinth'e ve instrument kutusuna giriyordu. | Bina içi hat `y=2.6`'ya alındı; instrument kutuları `[-5.5, 0.5, 5.5]` konumlarına taşındı. |
| 30 | Riser üst yatayları fan shroud/louver'lara değiyordu. | Üst kot `y=10.6` → `y=9.5` yapıldı; boru plenum gövdesine temiz giriyor. |
| 31 | P&ID ve tablo etiketleri sabit `48"` / `30"` gösteriyordu. | Etiketler `station_piping` NPS değerlerinden dinamik üretiliyor. |
| 32 | Gas cooler besleme hattı 3+ ünite düzeninde suction/anti-surge/discharge header'ları kesiyordu. | Besleme, header uçlarının doğusuna alındı (`x = headerEastX + 4`, en az `coolerEndX + 4`); 2 ünite düzeninde `x = -4` kullanılır. |
| 33 | Sabit `3.0 / 3.8 / 5.2 / 4.2` kotları büyük çaplı 3-4 ünite düzenlerinde yetersiz kalıyordu. | Cooler riser, return, by-pass ve ASV crossing kotları boru yarıçaplarına göre dinamik hesaplanır. |

---

## 2. Gaz soğutucu geometrisi (düzeltme sonrası)

### Sıcak giriş ve soğuk çıkış header'ları
```
Hot inlet : (-10, 1.5, -11) → (-4, 1.6, -11) → (-4, 1.6, -54) → (18, 1.6, -54)
Cold outlet: (-2, 1.6, -48) → (18, 1.6, -48)
```

### Baypas + TCV (Note 17)
```
(-4, 1.6, -54)   [hot header tap]
  → (-4, 5.2, -54)
  → (-4, 5.2, -48)
  → ( 0, 5.2, -48)
  → ( 0, 1.6, -48) [cold header tap]
TCV: (-1, 5.2, -48)
```

### Cooled gas return
```
(-2, 1.6, -48) → (-2, 3.8, -48) → (-98, 3.8, -48)
→ (-98, 2.2, -52) → (-122, 2.2, -52)  [pig launcher]
```

### Riser'lar
```
Inlet : (x, 1.6, -54) → (x, 1.6, -65.5) → (x, 9.5, -65.5) → (x, 9.5, -71)
Outlet: (x, 1.6, -48) → (x, 3.0, -48) → (x, 3.0, -65.5)
        → (x, 9.5, -65.5) → (x, 9.5, -71)
```
Soğuk riser, sıcak header'ı `z=-54`'te `y=3.0` seviyesinde geçer; eksen farkı 1.4 m, yarıçap toplamı 0.867 m, net boşluk 0.53 m.

---

## 3. Kompresör bağlantı geometrisi (düzeltme sonrası)

Temsili ünite `cx = -68` için:

### Suction
```
suction header (-64.8, 1.5, -16.2)
  → (-64.8, 3.6, -15.0)
  → (-64.8, 3.6, -9.5)
  → (-64.8, 2.6, -9.5)
  → (-64.8, 2.6, 1.0)        [bina kuzey duvarı]
  → (-64.8, 2.6, 4.6)
  → (-64.8, 3.4, 4.6)
  → (-70.2, 3.4, 4.6)
  → (-70.2, 3.4, 6.4)        [barrel kuzey nozzle]
```

### Discharge
```
barrel güney üst (-70.2, 5.0, 11.2)
  → (-70.2, 6.5, 11.2)
  → (-70.2, 6.5, 12.4)
  → (-60.8, 6.5, 12.4)
  → (-60.8, 1.8, 12.4)
  → (-60.8, 1.8, 1.0)
  → (-60.8, 1.5, -11.0)      [discharge header]
```

### Anti-surge (ASV) ve mevcut ara header
```
Ünite loop: discharge branch (-60.8, 1.8, -2.0)
  → (-60.8, 4.2, -2.0)
  → (-67.5, 4.2, -2.0)
  → (-67.5, 4.2, -13.6)
  → (-67.5, 1.5, -13.6)      [anti-surge / recycle header]

Anti-surge header: (-10, 1.5, -13.6) → (-132, 1.5, -13.6)

Tek suction tie (batı ucu):
  (-132, 1.5, -13.6) → (-136, 1.5, -13.6)
  → (-136, 1.5, -16.2) → (-132, 1.5, -16.2) [suction header]
```
Ünite ASV loop'ları suction ve discharge header'ların arasındaki mevcut
ara header'a bağlanır. Bu header tek noktadan suction header'a döner;
discharge header'a doğrudan U-tie yapılmaz.

### Discharge header → gas cooler
```
Discharge header: (-132, 1.5, -11.0) → (-10, 1.5, -11.0)
Gas cooler feed:
  (-10, 1.5, -11.0) → (-4, 1.6, -11.0)
  → (-4, 1.6, -54.0) → (18, 1.6, -54.0) [cooler inlet header]
```
Discharge header'ın doğu ucundan çıkan hat, doğrudan gas cooler inlet
header'ına gider. Ara header ile discharge header arasında ek bağlantı yoktur.

### MFS siklon seperatörleri
```
Gövde: dikey silindir, r = 1.15 m, y = 1.4…8.6 m
Üst başlık: yarım küre, tepe y = 9.75 m
Alt: konik taban, y = 0…1.4 m
Destek: 3 adet çelik ayak
Giriş: ortak inlet header (-72, 6.6, -92…-56) → yan nozul
Çıkış: üst dome → y = 10.6 m → ortak outlet collector (x = -54.5)
```
CFS kartuş filtreleri yatay silindir olarak korunmuştur.

### Türbin egzoz bacası
```
Baca: dikey silindir, y = 0.6…15.6 m, r = 1.15 m
Bağlantı: GT skid batı yüzü → yatay geçiş kanalı (y = 5.4 m) → dirsek → baca
Malzeme: matSkidEnclosure (türbin skid ile aynı renk)
```
Baca ekseni yere diktir; eski 0.38 rad eğim kaldırılmıştır.

---

## 4. Akışa göre belirlenen çaplar

Test senaryosu: 12 kg/s, 20 → 60 bar, 1 aktif kompresör.

| Hat | NPS | OD (mm) | Sch | Debi (kg/s) | Hız (m/s) |
|---|---:|---:|---:|---:|---:|
| Suction header | 10" | 273.0 | 5 | 12.0 | 14.05 |
| Discharge header | 10" | 273.0 | 10 | 12.0 | 5.49 |
| Kompresör suction branch | 10" | 273.0 | 5 | 12.0 | 14.37 |
| Kompresör discharge branch | 6" | 168.3 | 5 | 12.0 | 14.51 |
| Anti-surge loop | 5" | 141.3 | 5 | 8.16 | 14.18 |
| Cooler inlet | 6" | 168.3 | 5 | 12.0 | 14.51 |
| Cooler riser (bay başına) | 5" | 141.3 | 5 | 6.0 | 10.42 |
| Cooler outlet | 6" | 168.3 | 5 | 12.0 | 13.18 |
| Cooler by-pass | 3 1/2" | 101.6 | 5 | 4.2 | 14.18 |

- Suction ve discharge header NPS'i **10" / 10"** olarak eşitlendi.
- Discharge header, eşitlik gereği 6"'dan 10"'a büyütüldü; hızı 5.49 m/s'ye düştü.
- Her ünite branşmanı kendi debisine göre seçilir. 4 ünite / 120 kg/s senaryosunda suction branch 18", discharge branch 10", ASV 8" olur.
- Cooler by-pass debisi %35, ASV debisi %68 surge limiti üzerinden boyutlandırılır.

---

## 5. Denetim sonuçları

- **40** prosedürel boru rotası
- **1.605** mesh
- Boru-boru segment denetimi: bağlantı noktaları (tee/elbow) hariç **0 çakışma**
- 2 ünite düzeni: 40 rota / 1.605 mesh / 0 çakışma
- 3 ünite düzeni (headerEastX = 6): 49 rota / 0 çakışma
- 4 ünite düzeni (headerEastX = 58): 68 rota / 0 çakışma
- Kompresör internal suction/discharge endpoint'leri barrel bounding box içinde
- Pig receiver/launcher endpoint'leri kovan bounding box içinde
- MFS/CFS endpoint'leri vessel bounding box içinde
- Cooler riser üstleri plenum içinde; fan shroud/louver teması yok
- 10" suction hattı foundation plinth ve instrument kutularıyla temas etmiyor
- Kasıtlı açık uçlar:
  - Gömülü ana hat stubları
  - Kuzeydeki dekoratif yükseltilmiş pipe rack
  - Ana hat/pig kovanı dış bağlantıları

---

## 6. Görsel doğrulama

Tarayıcıda cutaway görünümde:
- COMPRESSOR-02 binası açıldı.
- Suction/discharge branch'ların bina içine girdiği ve barrel nozzle'larına bağlandığı,
- Discharge hattının skid üstünden geçtiği,
- ASV loop'larının mevcut ara anti-surge header'a, header'ın da tek noktadan suction header'a bağlandığı,
- Discharge header'ın gas cooler besleme hattına bağlı olduğu, ara header'a doğrudan bağlanmadığı,
- MFS siklon seperatörlerinin dikey, CFS kartuş filtrelerinin yatay olduğu,
- Türbin egzoz bacalarının yere dik ve türbin skid rengiyle bağlı olduğu,
- Cooler inlet/outlet header, baypas ve cooled gas return hattının kapalı devre olduğu,
- Soğuk riser'ların sıcak header üzerinden ark yaparak geçtiği,
- By-pass TCV'sinin batı uçta, riser demetinden uzakta olduğu

doğrulandı.

### PFD gaz akışı kontrolü

3D rotalar PFD sırasına göre kontrol edildi:

```
Pig receiver → MFS → CFS → suction header
  → kompresör suction branch → kompresör
  → kompresör discharge branch → discharge header
  → discharge header doğu ucu → gas cooler inlet header
  → gas cooler → cooler outlet header → pig launcher → mainline out

Kompresör discharge branch → ASV loop → anti-surge (ara) header
  → tek noktadan suction header
```

- Discharge header ile anti-surge header arasında doğrudan bağlantı yoktur.
- Gas cooler beslemesi discharge header'ın doğu ucundan alınır.
  - 2 ünite: `(-10,-11) → (-4,-11) → (-4,-54)` (header uçlarının doğusu, outlet header'ın batısı).
  - 3+ ünite: `(headerEastX,-11) → (max(headerEastX+4, coolerEndX+4),-11) → aynı x'te -54 → coolerEndX`.
- Anti-surge header'a yalnızca ünite ASV loop'ları ve suction tie bağlanır.

---

## 7. Test

- JS syntax: `node --check station3dView.js`, `node --check stationTab.js`, `node --check chartsView.js`
- Yeni testler:
  - `test_station_headers_equal_nominal_size`
  - `test_compressor_and_cooler_lines_are_sized_by_flow`
- Tarayıcı: 3D sahne hatasız yüklendi; yalnızca misafir oturumdan kaynaklı beklenen `401 /auth/me` hatası.
- **Tam test seti:** `543 passed, 12 skipped, 0 failed`.

---

## 8. Ekipman modelleme ve teardown popup

### 8.1 Ana 3D sahnedeki modeller

- **Gas cooler:** fin-fan plenum, tüp tabloları, inlet/outlet headerları, fin-tüp
  bankı, louver slatları, fan halkaları, 6 kanatlı fanlar, motor ve kayış
  muhafazası eklendi.
- **Siklon seperatör:** dikey gövde, dished üst başlık, konik alt, inlet/outlet
  nozulları, drenaj nozulu, erişim merdiveni, üst bakım halkası ve destek
  ayakları eklendi.
- **Kartuş filtre seperatör:** yatay gövde, dished kapaklar, saddle destekler,
  üst inlet nozulu, uç outlet nozulu ve drenaj nozulu eklendi.

### 8.2 Vanalar

- Siklon inlet ve outlet hatlarına, CFS inlet ve outlet hatlarına **bağlı boru
  ile aynı görsel çapta** küresel vanalar yerleştirildi.
- Çaplar sabit değil; `station_piping.lines.cyclone_branch.od_mm` ve
  `filter_branch.od_mm` değerlerinden `visualPipeRadius()` ile türetilir.
- Her vanada iki adet weld-neck flanş, raised-face halkası ve 6 adet flanş
  cıvatası bulunur; bağlantı flanşlıdır.
- CFS outlet vanası uç nozuldan sonra `rotationY = π/2` ile Z ekseninde.

### 8.3 Teardown popup

- `kasp/web/src/components/equipmentTeardown.js` eklendi.
- Gas cooler, siklon ve kartuş filtre için ayrı patlatılmış 3D modeller.
- Sol panelde proses bilgileri ve tıklanabilir parça listesi.
- Sağ panelde OrbitControls, söküm/montaj slider'ı, otomatik döndürme ve
  sıfırlama.
- 3D parça etiketleri canlı olarak parçaları takip eder.
- Ekipmana tıklandığında popup otomatik açılır; telemetri HUD'ında ayrıca
  `🔧 Teardown Aç` butonu bulunur.
- Yeni yerel skill: `.agents/skills/equipment-teardown/SKILL.md`
  (OpenCode ve Antigravity/Agent-Skills uyumlu).
