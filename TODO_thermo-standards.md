# Termodinamik Altyapı Derin Analizi — KASP v2.5.0
## Formülasyonlar, Yaklaşımlar ve Standartlara Uygunluk (ASME PTC 10 / API 617 / ISO 2314 / AGA8)

> Kapsam: `kasp/core/` altındaki tüm termodinamik dosyalar (properties, mixture, constants,
> thermo_methods, aerodynamics, fallback, thermo_design_orchestration/support, selection,
> uncertainty, compliance, performance_corrections, thermo_support, ccp_interface, units, models).
> Yöntem: satır-doğrulamalı formül denetimi + standart maddesi çapraz kontrolü.
> Referanslar: ASME PTC 10-1997 (§4 head/verim/Schultz, §5.3 düzeltmeler, App.B belirsizlik),
> Schultz 1962 Bull.217, Huntington ASME 85-GT-13, API 617 8th Ed., ISO 2314 / ASME PTC 22,
> AGA8-DC92 (ISO 12213-2), Soave 1972, Peng–Robinson 1976/1978.

## Bölüm A — EOS ve Özellik Modelleri

### A.1 EOS kapsamı ve dispatch (INFO)
- [ ] **TH-A1.1 [8 EOS + ideal son-çare]**:
  - **Konum**: `kasp/core/properties.py:298-315` (`_dispatch`), `:1056` (`_solve_fallback`)
  - **Durum**: `coolprop, pr, srk, aga8, thermopack, ccp, dwsim, neqsim` + `ideal` (yalnızca son çare). `else: raise ValueError` doğru.
- [ ] **TH-A1.2 [Tek gerçek PT-flash: DWSIM/NeqSim]**:
  - **Konum**: `properties.py:1313-1319` (DWSIM `SetFlashSpec("PT")`), `:1505-1513` (NeqSim `init(0)+init(1)`)
  - **Durum**: CoolProp/HEOS, PR/SRK (`thermo` PRMIX/SRKMIX + `G_dep` stabil-kök), AGA8 (`pyaga8`), ThermoPack (VAPPH→LIQPH sıralı deneme), CCP — hepsi tek PT noktası, eşzamanlı VLE flash yok. Kubbe-içi kompozisyon ayrışması (`x_i,y_i,K_i,β`) hiçbir backend'de üst katmana taşınmıyor.

### A.2 Karışım kuralları / kij (kritik)
- [ ] **TH-A2.1 [PR/SRK `kij=0` sessizliği — CRITICAL]**:
  - **Konum**: `properties.py:636-641` (`PRMIX/SRKMIX(...)` `kijs` argümansız → `thermo` varsayılanı `kij=0`)
  - **Fizik**: Klasik van der Waals one-fluid; Wong-Sandler / Huron-Vidal / MHV1 yok. `grep kij` tüm `kasp/` içinde 0 sonuç. Soave 1972 / PR 1976 atfı yok.
  - **Etki**: `CH4-CO2/H2S/H2/N2` ikililerinde Z %1-3, h %3-8 sapma.
  - **Öneri**: Literatür `kij` tablosu ekle (H2 için negatif `kij` dahil); yoksa `H2S/CO2/H2>eşik` ise `WARNING "kij=0, belirsizlik ±X%"` üret.
- [ ] **TH-A2.2 [NeqSim `setMixingRule(2)` sihirli sayı]**:
  - **Konum**: `properties.py:1503-1513`
  - **Durum**: Model sabit `SystemSrkCPA`, mixing-rule yorumsuz + sessiz `try/except`; `SystemSrkEos/SystemPrEos` (`:1452-1453`) ölü kod; yakınsama (`isConverged`) sorgulanmıyor.
  - **Öneri**: Modeli parametrize et, `init` sonrası `numberOfPhases/beta/K-values` kontrolü ekle, iki-fazda `β,x_i,y_i`'yi `raw_props`'a taşı.
- [ ] **TH-A2.3 [ThermoPack/CCP/DWSIM kij'siz]**:
  - **Konum**: `properties.py:851-858` (sabit `'PR'`), `:1019` (`EOS='PR'`), `:1308` (`PRPropertyPackage`)
  - **Durum**: Üçünde de `kij` matrisi set edilmiyor; H2-CH4, CO2-CH4, H2S ikililerinde hata büyür, uyarı yok. DWSIM'de NRTL/UNIQUAC/GERG/Sour-Water paketi yok (CHANGELOG "16+ model" iddiasına rağmen tek PR).
  - **Öneri**: Asimetrik ikili içeren gazda uyarı üret; model seçimini parametrize et.

### A.3 AGA8 (HIGH/CRITICAL)
- [ ] **TH-A3.1 [İsimlendirme hatası: `pyaga8` ≠ GERG-2008]**:
  - **Konum**: `properties.py:761-762` (docstring `pyaga8 (GERG-2008)`)
  - **Fizik**: `pyaga8.Detail/Composition` AGA8-DC92 Detail (ISO 12213-2) metodudur; GERG-2008 (Kunz-Wagner 2012) farklı korelasyondur.
  - **Öneri**: Docstring'i `AGA8-DC92 Detail` olarak düzelt.
- [ ] **TH-A3.2 [Geçerlilik aralığı kontrolsüz — CRITICAL]**:
  - **Konum**: `properties.py:761-849`
  - **Fizik**: AGA8-DC92 penceresi (yakl. T=143–473 K, P≤280-300 bar, CH4 %50-100 + 21 bileşen pencereleri) hiç kontrol edilmiyor; `pyaga8` sessiz ekstrapole eder veya `ValueError→PR fallback` olur.
  - **Öneri**: `T,P,x` girişinde ISO 12213-2 penceresi assert/warning'i + pencere-dışı önerili fallback.
- [ ] **TH-A3.3 [Kısmi implementasyon + faz eşiği]**:
  - **Konum**: `properties.py:768-797` (19 eşleme; Ne/Kr/Xe/Air yok → PR fallback, doğru davranış ama "AGA8" etiketi yanıltıcı), `:830-833` (`Z<0.3→liquid`, kubbe tespiti değil)
  - **Öneri**: Desteklenmeyen listesini yayınla + `fallback_from=aga8` işaretle; faz için kubbe/flash kullan.

### A.4 Faz sınıflandırma heuristic (CRITICAL)
- [ ] **TH-A4.1 [`_classify_phase` Z-eşiği fiziksel olarak geçersiz]**:
  - **Konum**: `properties.py:132-152,179`
  - **Fizik**: `Z>0.7 veya ρ<100→gas; 0.3<Z≤0.7→supercritical; Z≤0.3→liquid` — `Z=Pv/RT` tek başına faz belirlemez; kritik üstü yoğun gaz sıvı, sıvı süperkritik etiketlenir. `Tc/Pc`, `Tr/Pr`, kalite `Q` hesabı yok; `build_phase_envelope("")` (`:543`) kurulup hiç sorgulanmıyor (ölü hazırlık).
  - **Öneri**: Backend fazını esas al (`AbstractState.phase`, `G_dep`, `PhaseType`, `PresentPhases`); `Z/ρ` yalnızca `phase is None` iken `belirsiz` etiketiyle; gerçek çözüm için `TP-flash (Rachford-Rice)` ekle.
- [ ] **TH-A4.2 [Heuristic ezmesi + yanlış CRITICAL alarm]**:
  - **Konum**: `properties.py:179,142-145`, `:391-393`
  - **Durum**: `_build_state` her EOS çıktısını heuristic'ten geçiriyor; `liquid/two-phase/supercritical→thermo_health=CRITICAL` yanlış etiketle yanlış alarm üretir; gerçek iki-faz (%1 vs %99 kalite) ayırt edilmiyor.
  - **Öneri**: Faz-sağlık eşlemesini backend fazına bağla; kalite bilgisini taşı.

### A.5 H/S referans tutarsızlığı (CRITICAL)
- [ ] **TH-A5.1 [Backend-arası sıfır noktası farkı]**:
  - **Konum**: `properties.py:706-724` (PR: `T_ref=298.15K, P_ref=101325Pa → H=S=0`) vs `:583-584,824-826,930-931,1022-1023,1330-1337` (CoolProp/AGA8/ThermoPack/DWSIM/NeqSim/CCP mutlak referanslar)
  - **Fizik**: Backend-içi `Δh` tutarlı ama backend-arası mutlak `H/S` farklı; EOS zinciri/fallback karışınca head/güçte sistematik ofset.
  - **Öneri**: Ortak referansa indirge (`H_dep(T,P,x)−H_dep(Tref,Pref,x)` normalizasyonu) veya yalnızca aynı-backend `Δh/Δs` kullanan hesaba izin ver.
- [ ] **TH-A5.2 [`S_ideal` payda hatası — HIGH]**:
  - **Konum**: `properties.py:1154-1155` (`S_ideal=Cp·ln(T/273.15)−R·ln(P/STD)`)
  - **Fizik**: Payda `298.15` olmalı; aksi halde PR ile ~`Cp·0.087` (≈90 J/kgK) süreksizlik. Sabit-`Cp` log formülü PR'ın `∫Cp(T)/T dT` polinomuyla uyumsuz (v2.0.2'de H düzeltildi, S unutuldu).
  - **Öneri**: `ln(T/298.15)` + `HeatCapacityGases.integral_over_T`; regresyon testi `S(298.15,101325)==0`.

### A.6 Sabit/birim tutarlılığı
- [ ] **TH-A6.1 [Ses hızı ideal-formülü — HIGH]**:
  - **Konum**: `properties.py:127-130,1038,943,1550` (`a=√(kP/ρ)`, `Z` parametresi ölü)
  - **Fizik**: Sıvı/yoğun süperkritikte gerçek `a=√(∂P/∂ρ)_s`'den %10-50 sapar → Mach/surge tahminine yansır.
  - **Öneri**: Her backend'in kendi `a`'sını kullan; ideal formül yalnızca fallback'te kalsın.
- [ ] **TH-A6.2 [R tekrarları — LOW]**: `R=8.314462` 5 hard-coded tekrar (`:673,683,721,913,922`) → `R_UNIVERSAL_J_MOL_K` tek-kaynağa bağla. Değerler (R, STD/NORMAL/STANDARD, G, ISA, psi/kg-cm² yuvarlamaları) sayısal doğru.

### EOS olgunluk tablosu
| EOS | Olgunluk | Gerekçe |
|---|---|---|
| `coolprop` (HEOS) | **Üretim** | En doğru yoğunluk/Cp/Z; tek eksiği kubbe-içi `Q`-flash yokluğu |
| `pr` / `srk` (kij=0) | **Üretim (kuru/şartlı)** | Kübik + `G_dep` stabil-kök doğru; ekşi/asidik/H2'li gazda şartlı |
| `aga8` | **Hazır (doğalgaz penceresi)** | Satış gazında doğru; aralık kontrolü + faz/flash yok |
| `thermopack` | **Hazır** | VLE altyapısı güçlü; `kij` set edilmiyor + kurulum kırılgan |
| `neqsim` | **Deneysel** | TP-flash var ama model sabit, yakınsama kontrolsüz, faz-kesme var |
| `ccp` | **Deneysel** | `EOS='PR'` sabit + geometri/akış varsayımlı; çapraz kontrol için uygun |
| `dwsim` | **Deneysel** | Tek gerçek PT-flash ama `clr/dll` platform bağımlı + tek PR paketi |
| `ideal` | **Son-çare** | `S_ref` hatalı + `Z_ideal` lineer; yalnızca tüm EOS'lar çökerse |

## Bölüm B — Sıkıştırma Metotları (ASME PTC 10 §4 / Schultz 1962 / Huntington 85-GT-13)

Ortak çekirdek `thermo_methods.py:44-54`: `H_p = Z_avg·R_sp·T1·(PR^σ−1)/σ/1000` — ideal-gaz kapalı formu + Z çarpanı; **PTC 10 §4 `∫vdp` tanımı değildir**. M1/M2/M4/M6 nihai head'i yine buraya indirger (`:148-154,174-180,258-264,515-521,861-863`); logdaki "API 617 Appendix C — İntegral" ifadesi (`:64`) yanıltıcıdır (yalnızca üs entegre edilir).

- [ ] **TH-B1.1 [M2 en zayıf yaklaşım — CRITICAL]** (`thermo_methods.py:184-285`): Yalnız çıkış `k2` + ağır clamp (`k∈[1.02,1.8]`, `eta∈[0.3,0.99]`, `n∈[0.02,0.45]`, `T≤2.8·T1`); giriş koşulu yok; yüksek PR/CO2/H2S/kritik-yakında hata %5-15. **Öneri**: `k̄` kullan veya varsayılan zincirden çıkar; clamp'leri `converged=False+INVALID` ile işaretle.
- [ ] **TH-B1.2 [M1 toleransı aşırı sıkı — MEDIUM]** (`:56-138`): `|T2−T2_old|<0.01K`, EOS gürültüsü (~0.1K) ve izentropik `0.5K` yanında yalancı `max_iterations` riski; yakınsamasa bile sessizce head döner. **Öneri**: `0.1-0.5K` bandı + yakınsamasız head'e `converged=False`.
- [ ] **TH-B1.3 [M3 §4'e en yakın 2. metot — MEDIUM]** (`:287-349`): Parçalı-politropik `Σhead_step` sayısal karedir; kusurlar: nokta-`Z_step` (birinci-mertebe hata), aritmetik `np.mean(z)` (`:347`), `converged=True` sabit, Schultz `f` yok. **Öneri**: Adım≥20 + aralık-ort `Z` + `f` uygula.
- [ ] **TH-B1.4 [M4 hibrit tutarsızlığı — HIGH]** (`:351-521`): Pay gerçek (`dh_isen` EOS), payda ideal (`eta_isen(k)`); son head yine kapalı forma sokulur (`:511-521`); `tol_h=100J/kg` (≈0.05K) vs izentropik `0.5K` ölçek tutarsız. **Öneri**: `eta`'yı Schultz-X/Y ile değiştir; `tol_h`'yi head-oranlı yap.
- [ ] **TH-B1.5 [M5 referans — INFO/olumlu]** (`:579-773`): `dT/dP` ODE + `∫v dP` RKF45, Huntington 85-GT-13'e sadık **tek gerçek ∫vdp → tasarım/şahit-test referansı yap**. Kusur: yedek Simpson ağırlığı standart RK4 değil; `Cp` tabanı 100 + tek-yönlü `dv/dT` kritik bölgede gürültülü.
- [ ] **TH-B1.6 [M6 Schultz-orijinal — HIGH notlarla]** (`:778-881`): `X,Y→m_T,n_v` formülleri Schultz 1962 Eq.12-14'e doğru (**PTC 10 orijinal referansı**); kusur: türevler tek-noktada ileri fark, yola entegre değil; yakınsamazsa `:878-879` sessizce düz `n`'ye düşer. **Öneri**: M5 çapraz-kontrolü; düşüşü `fallback` olarak işaretle.
- [ ] **TH-B2.1 [Schultz `f_t` clamp'i standartta yok — HIGH]** (`aerodynamics.py:208-209`): `0.85-1.15` KASP guard'ı; %15'i aşan gerçek sapma sessizce kırpılır. **Öneri**: Kırpmayı uyarıya bağla.
- [ ] **TH-B2.2 [Dört sessiz `f_t=1.0` — HIGH]** (`aerodynamics.py:175-176,183-184,191,210-212`): `dh_isen≤0` dahil log'suz düzeltmesizlik; EOS/faz hatasının üstünü örter. **Öneri**: `fallback_from/reason` işle.
- [ ] **TH-B2.3 [`f_t` çift-yol tutarsızlığı — MEDIUM]** (`aerodynamics.py:253-257` vs `thermo_design_orchestration.py:235-236`): Aynı head iki yerde farklı `f` ile çarpılabilir/çarpılmaz. **Öneri**: Tek fonksiyonda merkezileştir.
- [ ] **TH-B3.1 [Verim tanımları doğru — INFO/olumlu]** (`aerodynamics.py:231-261`, `thermo.py:361-378,466-482`): `eta_p=H_p/Δh`, `eta_s=(H2s−H1)/(H2−H1)` PTC 10 §4'e uygun + her yerde 0-1 clamp + aralık-dışı uyarı. **Korunmalı.**
- [ ] **TH-B3.2 [Sessiz `0.0` verim — MEDIUM]** (`aerodynamics.py:225-239`): Ters-gradyan/EOS hatası `verim=0` olarak rapora gömülür. **Öneri**: `0` ile `hesaplanamadı (None)` ayrılsın.
- [ ] **TH-B4.1 [`k/Z` ortalama kaosu — HIGH]** (`aerodynamics.py:409-414` vs `thermo_methods.py:119,477,347,752`): Dört farklı `k` (aritmetik / basınç-ağırlıklı / tek-nokta) + M3/M5 aritmetik `Z` (logaritmik değil) → metotlar-arası %1-3 saçılımın birincil kaynağı; "basınç-ağırlıklı k = ASME uyumlu" yorumu (`:409`) kanıtsız. **Öneri**: Tek `Z̄=logmean` + tek `k̄` politikası; yorumu kaldır/kanıtla; `Z≤0`'da sessiz fallback yerine hata.
- [ ] **TH-B5.1 [Saha katsayıları belgesiz + ISO beyanı hatalı — CRITICAL]** (`performance_corrections.py:74-83` vs `reporting.py:501-502`): `0.005/egzoz`, `0.0002/nem` katsayılarının ISO 2314/PTC 22 referansı yok (dosya başlığı kendisi dürüst: OEM eğrisi önerir); rapor "ISO 2314'e uygundur" yazıyor. **Öneri**: Referans ekle veya rapor iddiasını "referans-tarzı, OEM'e özgü değildir" diye düzelt; çift ISA (`units.py` vs `:37`) tekilleştir.
- [ ] **TH-B6.1 [SolverChain tolerans-dışı kabul — HIGH]** (`fallback.py:314-353,361-371`): En-küçük-artıklı sonuç `mark_solver_nonconverged` ile döndürülür; hesap `INVALID` olmaz. **Öneri**: `history.converged=False + termination_reason=residual` üst katmana taşınsın; sıra `aj→brent→fd` olsun.
- [ ] **TH-B7.1 [Head katsayıları doğru, kaynak eksik — LOW]** (`thermo_support.py:171-181` vb.): `334.55`, `0.4299`, `0.7457` vb. değerler doğru; yalnızca `hp`/`Btu/hp-hr` türetmesi belgesiz. Fiziksel risk yok.
- [ ] **TH-B7.2 [Mekanik kayıp atfı dayanaksız — MEDIUM]** (`aerodynamics.py:274-293`): `0.65·ACMH^0.45` "ExxonMobil/PTC 10" atfı doğrulanamadı (PTC 10'da böyle formül yok); `10 kW` taban + `%10` tavan keyfi. **Öneri**: Kaynağı belgele/kaldır, tabanları ölçek-bağımlı yap.

### Metot olgunluk tablosu (referans: M5 ∫vdp + M6 Schultz)
| Metot | Sınıf | Temiz gaz PR<4 | Ağır gaz / PR>4 / kritik | Hüküm |
|---|---|---|---|---|
| M5 Huntington-RK45 | Referans | <%0.5 | <%1-2 | Şahit-test referansı yap |
| M6 Schultz 3-exp | Referans (gerçek-gaz) | %0.5-1 | %1-3 | M5 çapraz-kontrolü |
| M4 direct_hs | Yüksek yaklaşım | %0.5-1.5 | %2-5 | `eta` Schultz-X/Y ile değiştirilmeli |
| M3 incremental | Orta-yüksek | %1-2 | %2-4 | Adım≥20 + `f` ile güçlendirilmeli |
| M1 average | Orta | %1-3 | %3-8 | Hızlı tahmin; "integral" diye sunulmamalı |
| M2 endpoint | Düşük | %2-5 | %5-15 + sessiz clamp | Referans yapma; kaba tarama/devre-dışı |

## Bölüm C — Sistem Seviyesi (Orkestrasyon / Seçim / Belirsizlik / Uyumluluk)

- [ ] **TH-C1.1 [INVALID head/güç yarılması — CRITICAL]** (`thermo_design_orchestration.py:319-320` + `thermo_design_support.py:147-155`): Güç `0.0` sıfırlanırken head koşulsuz toplanıyor → `eta=Σhead/ΣΔh` yapay yükselir (`min(1.0,…)` ile %100'e kilitlenir). PTC 10 §4 bütünlük ihlali. **Öneri**: Head katkısını da hariç tut veya sonucu `None+INVALID` yap.
- [ ] **TH-C1.2 [INVALID `T_out` yayılımı — HIGH]** (`thermo_design_orchestration.py:347` + `thermo.py:997-1002`): Çıkış özellikleri fiziksel-dışı sıcaklıktan hesaplanıyor. **Öneri**: `final_t_out` dondur veya `None`+uyarı.
- [ ] **TH-C1.3 [Ara-soğutucu kontrolsüz — HIGH]** (`thermo.py:790` + `orchestration:349-351`): `intercooler_dp` aralıksız (`dp>1` → negatif basınç; `dp<0` → basınç kazancı); `ic_t > T_discharge` ise "soğutucu" gizlice ısıtıcı olur. **Öneri**: `0≤dp≤~0.15` + `ic_t<T_discharge` assert/warning.
- [ ] **TH-C1.4 [Kademe-arası EOS değişimi — MEDIUM]** (`orchestration:146-148`): Her kademe `reset_lock()` → kademe 1 CoolProp + kademe 2 PR gibi tutarsız model. **Öneri**: Lock'u makine-seviyesinde tut, değişimde kademe-kırılımlı uyarı ekle.
- [ ] **TH-C2.1 [API617 %4 marjı — çifte sayım yok (OLUMLU), dayanak zayıf]** (`thermo.py:959`, `workers.py:214-219`): Tek-nokta uygulama doğru; ancak `%4`'ün API 617 dayanağı yok (uygulamada tipik %10) + `%5-20` oversize bandıyla etkileşim belgeli değil.
- [ ] **TH-C2.2 [Surge paydası iyimser — MEDIUM]** (`selection.py:210`): `(Qop−Qsurge)/Qsurge` yerine standart `(Qop−Qsurge)/Qop`; `%10` eşiği etrafında karar değiştirir (gerçek %9.1 → kod %10.0). Stonewall ile payda tutarsız (`:211-215`). **Öneri**: İkisinde de payda `Qop` + tek placeholder filtresi.
- [ ] **TH-C2.3 [Skor eğimleri belgesiz — MEDIUM]** (`selection.py:232-243,237`): `1.33/2.0/1.5/0.5` için kalibrasyon referansı yok. **Öneri**: `EngineSettings`'e taşı + referans ekle.
- [ ] **TH-C3.1 [Belirsizlik yalnızca Tip-B — HIGH notlarla]** (`uncertainty.py:345-454`): Tip-A, korelasyon, EOS-model belirsizliği yok (`model_uncertainty_included=False` dürüst); ama rapor "tüm hesaplamalar doğrulanmıştır" diyor (`reporting.py:527-528`). **Öneri**: Başlığı "kısmi — yalnızca Tip-B" olarak düzelt.
- [ ] **TH-C3.2 [Breakdown formülü yanlış — MEDIUM-HIGH]** (`uncertainty.py:435-439`): `|Sᵢσᵢ|/Σ|Sⱼσⱼ|` yerine varyans-ağırlıklı `(Sᵢσᵢ)²/Σ(Sⱼσⱼ)²` olmalı; baskın kaynak küçültülüyor.
- [ ] **TH-C3.3 [`k=2` sabit — MEDIUM]** (`uncertainty.py:185,236-254`): Welch-Satterthwaite + t-dağılımı yok (özellikle 4 ölçümlü tasarımda). **Öneri**: `t95(νeff)` kullan.
- [ ] **TH-C3.4 [Sabit enstrüman haritası — HIGH]** (`thermo.py:903-920`): Her zaman `p:high-transducer/T:RTD/flow:orifice`; `t_out` yok; rapor tablosu (Coriolis ±%0.10) hesapla çelişiyor (`reporting.py:541-542`). **Öneri**: Enstrümanı input'tan al, 5 kanala çıkar, tabloyu hesaptan üret.
- [ ] **TH-C3.5 [Çift belirsizlik motoru — HIGH]** (`compliance.py:10-21` vs `uncertainty.py`): Göreli-RSS vs duyarlıklı-RSS çelişiyor. **Öneri**: Birleştir veya stub'ı sil.
- [ ] **TH-C4.1 [Koşulsuz "uygundur" beyanı — CRITICAL]** (`reporting.py:499-514` vs `compliance.py:26-89`): Kod `NOT_IMPLEMENTED`/stub derken rapor "ASME PTC-10/ISO 2314/API 616-617'ye uygundur" yazıyor. **Öneri**: Her standart için `uygun/kısmi+gerekçe` deseni (`reporting:594-599` örneğindeki gibi).
- [ ] **TH-C5.1 [Güç zinciri sıralaması doğru — OLUMLU]** (`thermo.py:947-959,383-384,488-491`): gaz→şaft→motor→ünite sırası doğru ve iki yol tutarlı. **Korunmalı.**
- [ ] **TH-C5.2 [`heat_rate` payda tutarsızlığı — MEDIUM]** (`thermo.py:973` vs `:536-540`): Tasarım `fuel/motor`, değerlendirme `fuel/shaft`. **Öneri**: Tek tanıma sabitle + belgele.
- [ ] **TH-C6.1 [H₂S LHV yanlış (≈HHV) — HIGH]** (`constants.py:118`): `16450 kJ/kg` HHV'ye karşılık geliyor; gerçek LHV `~15196` (kodun kendi ISO 6976 tablosu `thermo.py:228` doğru: `517.93`). Ekşi gazda yakıt ~%8 düşük. **Öneri**: `16450→~15200`, ISO 6976 molar tablosunu tek kaynak yap.
- [ ] **TH-C6.2 [Sessiz sıfır yakıt — HIGH]** (`thermo.py:974` vs `:501-502,518-524`): Tasarım yolu `fuel=0.0` sessiz; değerlendirme `50000+uyarı`. **Öneri**: Yolları birleştir veya `fuel=None+NOT_IMPLEMENTED`.

### Standart uygunluk tablosu
| Standart | Gerçek durum | Uyum | Eksik |
|---|---|---|---|
| ASME PTC 10 (head/verim/Schultz) | Schultz `f_t`, log-ort Z, head/güç ayrımı doğru | **Kısmi-iyi** | INVALID tutarsızlığı; Re/Mach stub; ölü PR-optimizasyon |
| ASME PTC 10 App.B/§7 belirsizlik | RSS + merkezi-fark + `k=2`, FS şeffaflığı | **Kısmi** | Tip-A yok, model yok, `k=2` sabit, breakdown yanlış, `t_out` yok |
| API 617 | `%4` tek-nokta, çifte-sayım önlenmiş; surge/stonewall eşikleri | **Kısmi** | `%4` dayanağı yok; surge paydası iyimser; lateral/torsional stub |
| ISO 2314 / PTC 22 | Jenerik `T·p` faktörleri | **Zayıf** | OEM-eğrisi/ISO-prosedürü yok; rapor iddiası fazla |
| AGA8 / GERG | Zincir + eşleme mevcut | **Kısmi** | Aralık kontrolü yok; faz/flash yok; isimlendirme hatası |

## En Kritik 10 (termodinamik, öncelik sıralı)
| # | ID | Başlık | Efor |
|---|---|---|---|
| 1 | TH-A2.1 | PR/SRK `kij=0` sessizliği | 1-2 gün |
| 2 | TH-A4.1 | `_classify_phase` Z-eşiği | 2-3 gün |
| 3 | TH-A5.1 | Backend H/S referans uyumsuzluğu | 1-2 gün |
| 4 | TH-C4.1 | Koşulsuz "uygundur" beyanı | 2-4 sa |
| 5 | TH-C1.1 | INVALID head/güç yarılması | 3-5 sa |
| 6 | TH-C6.1 | H₂S LHV≈HHV | 1-2 sa |
| 7 | TH-A5.2 | `S_ideal` payda hatası | 1-2 sa |
| 8 | TH-B1.1 | Kapalı-form "integral" sunumu + M2 | 1 gün |
| 9 | TH-B4.1 | `k/Z` ortalama kaosu | 1 gün |
| 10 | TH-B5.1 | Saha katsayıları + ISO beyanı | 4-8 sa |

## Komutlar (doğrulama)
```bash
QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg python3 -m pytest test_fallback_solvers.py test_p2_security.py test_thermo_limits.py test_verify_independent.py -q
rg -n "kij" kasp/ --type py ; rg -n "8\.314462" kasp/core/properties.py
```
