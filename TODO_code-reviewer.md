# Kod İnceleme Raporu — KASP v2.5.0

> Üretim: kıdemli kod incelemesi (güvenlik + performans + kalite + bug + veri bütünlüğü).
> Kapsam: `kasp/core/*`, `kasp/ui/*`, `kasp/utils/*`, `kasp/data/*`, `kasp/api/*`, `main.py`.
> Yöntem: doğrudan dosya okuma + paralel salt-okunur keşif ajanları; bulgular dosya:satır doğrulamalı.

## Context
- [ ] **CR-CTX-1.1 [Repo Bilgisi]**:
  - **Repo/branch**: `/Users/macbook/Documents/Kodlama/KASP`, branch `main` (commit `bafcc7c`, v2.5.0)
  - **Dil/framework/runtime**: Python 3.12, PyQt5 masaüstü, FastAPI (opsiyonel), CoolProp / `thermo` / thermopack / NeqSim / DWSIM / ccp backend'leri, SQLite, ReportLab, matplotlib
  - **Amaç/kapsam**: Kompresör tasarım + performans + mühendislik karşılaştırma uygulaması

## Review Plan
- [ ] **CR-PLAN-1.1 [Security Scan]**:
  - **Scope**: `kasp/security.py`, `kasp/core/user_manager.py`, `kasp/data/database.py`, `kasp/api/server.py`, `kasp/utils/updater.py`, `kasp/utils/project_manager.py`, config/lockout dosyaları
  - **Priority**: Critical — merge öncesi tamamlanmalı
- [ ] **CR-PLAN-1.2 [Performance Audit]**:
  - **Scope**: CoolProp çağrı yoğunluğu (`thermo_methods.py`, `aerodynamics.py`), cache stratejisi (`properties.py`), matplotlib figure lifecycle (`graphs.py`), API `/benchmark` amplifikasyonu
  - **Priority**: High — ölçülebilir darboğazlar işaretlendi
- [ ] **CR-PLAN-1.3 [Correctness & Robustness]**:
  - **Scope**: EOS fallback zinciri, sessiz hata yutma, dict erişimleri, magic number'lar, ölü kod (`compliance.py`, `thermo_support.py`)
  - **Priority**: High
- [ ] **CR-PLAN-1.4 [Quality & Tests]**:
  - **Scope**: Tip anotasyonları, uzun fonksiyonlar, pytest marker/config, kapsanmayan modüller
  - **Priority**: Medium

## Review Findings — Güvenlik
- [ ] **CR-ITEM-1.1 [API rate-limit auth'tan sonra çalışıyor — kaba kuvvet baypası]**:
  - **Severity**: High
  - **Location**: `kasp/api/server.py:78-93`
  - **Description**: `_PROTECTED=[auth, rate_limit]` sırasında auth başarısız olursa rate-limit sayacı artmıyor; token kaba-kuvvet denemeleri hız sınırına takılmıyor. Limiter bellek-içi `defaultdict(list)`, sınırsız büyüyor, kilit yok, `X-Forwarded-For` yok.
  - **Recommendation**: Sırayı tersine çevir (`rate_limit` önce), pencere başına sayaç + kilitli LRU kullan.
- [ ] **CR-ITEM-1.2 [API `/benchmark` amplifikasyonu]**:
  - **Severity**: Medium
  - **Location**: `kasp/api/server.py:157-203`
  - **Description**: Tek istekte 9 ardışık motor çağrısı; global `ThermoEngine()` singleton'ının thread-güvenliği belirsiz. DoS amplifikasyon vektörü.
  - **Recommendation**: Benchmark endpoint'ine ayrı kota (örn. dakikada 2) + eşzamanlı istek kilidi.
- [ ] **CR-ITEM-1.3 [Pydantic sınırları eksik — negatif basınç motora kalıyor]**:
  - **Severity**: Medium
  - **Location**: `kasp/api/server.py:122-142`
  - **Description**: `p_in/p_out/t_in` için `gt/le` yok; `gas_comp` toplam-%100/negatif denetimsiz; `eos_method/method/*_unit` enum değil; `project_name` uzunluk sınırsız.
  - **Recommendation**: Alanlara `Field(gt=0)`, `gas_comp` kök-validator (toplam≈1, negatif yok), `Literal` tipler ekle.
- [ ] **CR-ITEM-1.4 [Health endpoint iç durum sızdırıyor]**:
  - **Severity**: Medium
  - **Location**: `kasp/api/server.py:96-109`
  - **Description**: `/api/constants`, `/api/health`, `/`, `/static` auth'suz; health `api_enabled/coolprop_loaded` iç durumunu açıklıyor.
  - **Recommendation**: Health'i liveness (`{"status":"ok"}`) ile sınırla; sürüm/backend bayraklarını korumalı endpoint'e taşı.
- [ ] **CR-ITEM-1.5 [`Session.authorize` fail-open mirası]**:
  - **Severity**: Medium
  - **Location**: `kasp/security.py:417-427`
  - **Description**: Oturum yokken `manage_users`/`delete` ve strict-auth hariç `True` dönüyor. `main.py` strict-auth açıyor (olumlu), ancak kütüphane olarak import eden her yol fail-open kalıyor.
  - **Recommendation**: Varsayılanı fail-closed yap; geriye uyumluluk gerekiyorsa açık `KASP_DEV_NO_AUTH=1` bayrağı iste.
- [ ] **CR-ITEM-1.6 [Kilit dosyası izinleri + CWD-bağımlı yollar]**:
  - **Severity**: Low
  - **Location**: `kasp/security.py:99-106`, `kasp/data/database.py:155-166`
  - **Description**: Lockout/DB dosyaları varsayılan umask ile yazılıyor (`0o600` yok); dev modda göreli yollar CWD'ye bağlı.
  - **Recommendation**: `os.open(..., 0o600)` ile atomik yazı + uygulama-veri dizinini tekilleştir.

## Review Findings — Doğruluk / Sessiz Hata
- [ ] **CR-ITEM-2.1 [`compliance.py` stub'ları gerçek onay gibi raporlanıyor]**:
  - **Severity**: Critical
  - **Location**: `kasp/core/compliance.py:47-83`
  - **Description**: `lateral_critical_speed_analysis` Jeffcott stub + `meets_api=True` sabit; `torsional_analysis` hep Pass; `calculate_uncertainty` `value=0`'da ZeroDivision. Hiçbiri çağrılmıyor (ölü kod) ama rapor yoluna bağlanırsa API617 onayı izlenimi verir.
  - **Recommendation**: Stub'ları `NotImplementedError` yap veya `analysis_scope=NOT_IMPLEMENTED` ile işaretle; raporda gri göster.
- [ ] **CR-ITEM-2.2 [Logger'sız sessiz EOS fallback'leri]**:
  - **Severity**: High
  - **Location**: `kasp/core/thermo_methods.py:144, 167, 453, 485, 491`, `kasp/core/thermo_design_support.py:71`
  - **Description**: `except Exception:` ile `mw=state_in.MW`, `z=Z1`, `d_h_d_t=2000.0` gibi ikameler log'suz; kütüphane hatası gizlenip yanlış head/T_out üretiliyor.
  - **Recommendation**: En az `logger.debug(...)` ekle (davranış değişmeden gözlemlenebilirlik).
- [ ] **CR-ITEM-2.3 [Rapor diyagramı etkin EOS ile değil istenen EOS ile çiziliyor]**:
  - **Severity**: High
  - **Location**: `kasp/utils/reporting.py:353, 371`, `kasp/utils/graphs.py:1030`
  - **Description**: Gömülü T-s/P-v `inputs['eos_method']` ile üretiliyor; tablo `effective_eos` gösteriyor — fallback durumunda tablo ile grafik farklı fizikle çiziliyor.
  - **Recommendation**: Her iki tarafta `results.get('effective_eos') or results.get('_effective_eos') or inputs['eos_method']` birleştir.
- [ ] **CR-ITEM-2.4 [Karışım builder tutarsızlığı — sessiz fakirleşme]**:
  - **Severity**: High
  - **Location**: `kasp/core/mixture.py:100-125` vs `148-249`
  - **Description**: `validate_and_normalize` strict `raise`, ama `build_coolprop/thermo/neqsim` bilinmeyeni `warning+skip` ile düşürüyor.
  - **Recommendation**: Tek kural: builder'lar da `raise`, ya da düşürmede renormalize + `warnings: dropped_components` + `fallback_layer=composition` etiketi.
- [ ] **CR-ITEM-2.5 [Zorunlu girdi dict'leri doğrudan indeksleniyor]**:
  - **Severity**: High
  - **Location**: `kasp/core/ccp_interface.py:140-167`, `kasp/core/thermo_design_support.py:289-294, 317`, `kasp/core/thermo_support.py:379-382`
  - **Description**: `inputs['gas_comp']/['p_in']/['flow']` vb. `.get()`suz; eksik anahtar tüm yolu `KeyError` ile çökertiyor.
  - **Recommendation**: Girişte `contracts.normalize_design_inputs` zorunlu kıl + eksikte `FluidPropertyError("missing: p_in")`.
- [ ] **CR-ITEM-2.6 [Validasyon başlangıç durumu — boş form geçerli görünüyor]**:
  - **Severity**: Medium
  - **Location**: `kasp/ui/validators.py:98-104, 302, 314-321`
  - **Description**: İlk yüklemede boş alan `neutral+True`; sinyal gelene kadar `all_inputs_valid()==True` — boş formla hesaplama tetiklenebilir. `register_field` aliası yok.
  - **Recommendation**: Kayıt sonrası formu hemen valide et; `register_field = register_input` aliası ekle.

## Review Findings — Performans
- [ ] **CR-ITEM-3.1 [Figure lifecycle — `plt.close` etkisiz]**:
  - **Severity**: High
  - **Location**: `kasp/utils/graphs.py:1153-1165, 698-699`
  - **Description**: Figürler `Figure()` ile kurulduğundan `plt.close(fig)` etkisiz; başarısız `create_*` yolları yarım Figure kapatmıyor; `reporting.py:359,377` `savefig` sonrası kapatmıyor.
  - **Recommendation**: `fig.clf(); plt.close(fig)` + Qt `deleteLater` sırasını merkezileştir; `save_graphs_to_file` boşken `False` dönsün.
- [ ] **CR-ITEM-3.2 [Matplotlib backend sabit Qt5Agg]**:
  - **Severity**: High
  - **Location**: `kasp/utils/graphs.py:12`
  - **Description**: Headless/CI/offscreen ortamda Qt zorunlu; Agg fallback yok.
  - **Recommendation**: `QT_QPA_PLATFORM=offscreen` veya import hatasında `matplotlib.use("Agg")` fallback'i.
- [ ] **CR-ITEM-3.3 [Rapor tek `raise` ile tamamen çöküyor]**:
  - **Severity**: High
  - **Location**: `kasp/utils/reporting.py:1031`, `126-127`
  - **Description**: `results['inlet_properties/outlet_properties']` yoksa tüm PDF `raise` ile çöker; ReportLab yoksa alternatif yok.
  - **Recommendation**: Bölüm-seviyesi try/except + "üretilemedi: neden" kutusu.
- [ ] **CR-ITEM-3.4 [DB bağlantı sızıntısı (çok-thread)]**:
  - **Severity**: Medium
  - **Location**: `kasp/data/database.py:193-201`
  - **Description**: `close()` yalnızca çağıran thread'i kapatıyor; `atexit/__del` yok.
  - **Recommendation**: `atexit` hook ile tüm thread-bağlantılarını kapat; WAL sonucunu logla.
- [ ] **CR-ITEM-3.5 [Validasyon placeholder'ları DB'ye giriyor]**:
  - **Severity**: Medium
  - **Location**: `kasp/data/database.py:47-81, 355-409`
  - **Description**: `min=0/max=1000/500/9999`, `PR=10` yalnızca UYARI sayılıp `valid` listesine alınıyor; hata durumunda `insert_sample_data` sessizce boş kalıyor ve her açılışta `<146` sihirli sayıyla tekrar deneniyor.
  - **Recommendation**: Placeholder'ı `error` yap veya NULL yaz + "bilinmiyor" göster; `<146` yerine şema-sürümü kullan.

## Review Findings — Kod Kalitesi / Bakım
- [ ] **CR-ITEM-4.1 [Aşırı uzun fonksiyonlar]**:
  - **Severity**: High
  - **Location**: `thermo_methods.py:351` (227 satır), `:579` (198), `uncertainty.py:319` (144), `thermo_design_support.py:177` (110), `reporting.py:124-399`
  - **Description**: H-S/RKF45 iç-dış döngü + fallback tek gövdede; test edilemiyor.
  - **Recommendation**: Döngü gövdesi → `_hs_step()`, tolerans kontrolü → `_check_convergence()` gibi birimlere böl.
- [ ] **CR-ITEM-4.2 [Dağınık magic number'lar]**:
  - **Severity**: High
  - **Location**: `thermo_methods.py:221-237`, `selection.py:186,237,285`, `ccp_interface.py:156,170`
  - **Description**: Aynı sabitler 3-4 yerde tekrarlı, `EngineSettings`'te değil; PR≤8 varsayımı belgelenmemiş.
  - **Recommendation**: `EngineSettings`'e `K_CLAMP=(1.02,1.8)`, `EFF_CLAMP=(0.3,0.99)` vb. taşı.
- [ ] **CR-ITEM-4.3 [Ölü kod]**:
  - **Severity**: Medium
  - **Location**: `thermo_support.py:13,20,28,334,377`, `uncertainty.py:140`, `ccp_interface.py:266,315`, `exceptions.py:39`, `compliance.py` tamamı
  - **Description**: Greple doğrulandı — hiç çağrılmıyor.
  - **Recommendation**: Sil veya `tests/` altında belgele.
- [ ] **CR-ITEM-4.4 [Tip anotasyonu boşlukları]**:
  - **Severity**: Medium
  - **Location**: `thermo_methods.py` %0, `performance_corrections.py` %0, `compliance.py` %0, `exceptions.py` %0
  - **Description**: Kritik hesap yolları hintsiz; `mypy/pyright` config yok.
  - **Recommendation**: Önce `thermo_methods.py` + `performance_corrections.py`; CI'a `mypy` (salt-rapor).
- [ ] **CR-ITEM-4.5 [Şema anahtarı ıraksaması `version` vs `schema_version`]**:
  - **Severity**: High
  - **Location**: `kasp/utils/project_manager.py:34,128,162`, `kasp/core/contracts.py:103-104`
  - **Description**: `save_project` `schema_version`, `build_project_payload` `version` yazıyor; round-trip/drift riski.
  - **Recommendation**: Tek kanonik anahtar (`schema_version`), yazıcılar ikisini de yazıp tek kanondan okusun.
- [ ] **CR-ITEM-4.6 [Birim listesi uyumsuzluğu + gauge varyantları]**:
  - **Severity**: Medium
  - **Location**: `constants.py:155-160`, `units.py:20-27`, `validators.py:174-198`, `graphs.py:248-249`
  - **Description**: UI `UNIT_OPTIONS` ile `UnitSystem.UNITS` farklı; `kPa(g)/MPa(g)` gauge listesinde yok; grafikler `bar(g)`'yi hep 101325 Pa sayıyor.
  - **Recommendation**: Birim listelerini tek kaynaktan üret; grafik çağrılarına `ambient/altitude` geçir.

## Olumlu Bulgular
- PBKDF2-600k + `hmac.compare_digest`, kademeli kullanıcı-bazlı lockout, timing-safe dummy hash — iyi.
- Parametreli SQL + allowlist/regex korumalı migrasyon — iyi.
- Updater TLS fail-closed + SHA256 fail-closed + yarım dosya temizliği — iyi.
- Run-scoped iptal + thread-local `FallbackTracker` (v2.5.0) — doğru yön.
- `str(e)` istemciye dönmüyor, generic detail + `exc_info` log — iyi.

## Proposed Code Changes
```diff
--- a/kasp/api/server.py
+++ b/kasp/api/server.py
@@ -78,1 +78,1 @@
-        _PROTECTED = [auth, rate_limit]
+        _PROTECTED = [rate_limit, auth]  # CR-ITEM-1.1: önce hız sınırı
```
```diff
--- a/kasp/utils/reporting.py
+++ b/kasp/utils/reporting.py
@@ -353,1 +353,1 @@
-            inputs['eos_method']  # CR-ITEM-2.3: tablo ile farklı fizik
+            results.get('effective_eos') or results.get('_effective_eos') or inputs['eos_method']
```
```diff
--- a/kasp/core/compliance.py
+++ b/kasp/core/compliance.py
@@ -66,2 +66,2 @@
-            separation_margin=20, meets_api=True  # CR-ITEM-2.1: stub
+            raise NotImplementedError("FEA rotordynamics requires external solver")  # CR-ITEM-2.1
```

## Commands
```bash
QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg python3 -m pytest test_fallback_solvers.py test_p2_security.py test_thermo_limits.py -q
rg -n "def (safe_float|percent_deviation|build_summary_report|compare_with_kasp|suggest_solution)" kasp/ --type py
```

## Effort & Priority Assessment
| ID | Başlık | Efor | Karmaşıklık | Öncelik |
|---|---|---|---|---|
| CR-ITEM-2.1 | compliance stub'ları | 2-4 sa | Basit | **P0 — derhal** |
| CR-ITEM-2.3 | Rapor/grafik EOS birliği | 3-5 sa | Basit | **P0** |
| CR-ITEM-1.1 | Rate-limit sırası | 2-3 sa | Basit | **P1** |
| CR-ITEM-2.2 | Sessiz except'lere log | 3-4 sa | Basit | **P1** |
| CR-ITEM-2.4 | Karışım strictliği | 4-6 sa | Orta | **P1** |
| CR-ITEM-3.1 | Figure lifecycle | 4-6 sa | Orta | **P1** |
| CR-ITEM-4.5 | version/schema_version | 2-3 sa | Basit | **P1** |
| CR-ITEM-1.3 | Pydantic sınırlar | 3-5 sa | Basit | **P2** |
| CR-ITEM-4.1/4.2 | Refactor + sabitler | 1-2 gün | Orta | **P2** |
| CR-ITEM-3.5 | Placeholder politikası | 4-8 sa | Orta | **P2** |

## Quality Assurance Task Checklist
- [x] Güvenlik bulguları şiddetle sınıflandı, kritikler en üstte
- [x] Performans önerileri ölçülebilir gerekçeli
- [x] Her bulguda dosya:satır + somut düzeltme yönü var
- [x] Olumlu pratikler ayrıca kabul edildi
