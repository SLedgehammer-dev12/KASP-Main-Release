---
name: kasp-local-stack
description: >-
  KASP çalışma ortamlarını yönetir: PyQt5 masaüstü, FastAPI web sunucusu, test
  koşucusu, portlar, ortam değişkenleri ve süreç temizliği. Sunucu başlatırken,
  port çakışması yaşarken veya testleri izole çalıştırırken kullanılır.
---

# KASP Local Stack

KASP'nin iki çalışma yüzü vardır: **PyQt5 masaüstü** ve **FastAPI + ES modülü
web**. Aynı `kasp/core` ve `kasp/services` katmanını paylaşırlar.

## 1. Çalıştırma matrisi

| Mod | Komut | Varsayılan adres | Not |
|---|---|---|---|
| Masaüstü | `python3 main.py` | — | PyQt5; giriş ekranı açılır |
| Masaüstü (admin sıfırla) | `python3 main.py --reset-admin` | — | Etkileşimli; `--yes` olmadan headless reddeder |
| Web | `python3 run_web.py` | `http://127.0.0.1:<port>` | 8080 → 8000 → 8081 → 8082 ilk boş |
| Web (sabit port) | `KASP_API_PORT=8123 python3 run_web.py` | `127.0.0.1:8123` | Port doluysa `run_web.py` yine de dener |
| Legacy API | `KASP_API_ENABLE=1 KASP_API_TOKEN=... python3 -m kasp.api.server` | `127.0.0.1:8000` | Token yoksa çıkar |
| Test | `python3 -m pytest -q` | — | `QT_QPA_PLATFORM=offscreen` conftest'te |
| İzole web doğrulama | `python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve` | boş port | Kendi run dizini + log |

`run_web.py` şu ortamları `setdefault` ile kurar:

```text
KASP_API_ENABLE=1
KASP_API_TOKEN=kasp-local-token
KASP_API_HOST=127.0.0.1
```

Üretim/air-gapped dağıtımda token'ı mutlaka değiştir; varsayılan yalnızca yerel
geliştirme içindir.

## 2. Port ve süreç hijyeni

- Aynı makinede birden fazla ajan çalışabilir. **Kendi** sürecini yönet;
  `pkill -f run_web.py`, `killall python3` veya başka bir run dizinini kullanma.
- Yeni web oturumu için `kasp_verify.py serve` kullan: boş port seçer,
  `run.json`/`server.log` yazar, yalnızca kendi süreç grubunu kapatır.
- Kullanıcının açık sunucusuna bağlanacaksan portu tahmin etme; terminal
  çıktısındaki adresi veya `curl /api/health` yanıtını doğrula.
- Uzun süreli süreçleri arka planda başlat ve log dosyasını takip et; sonsuz
  bekleme yapma.

## 3. Veritabanı ve yapılandırma

- SQLite: `kasp_database.db` (repo kökü, `.gitignore`'da). `kasp_config.json`
  `database.path` ile aynı adı kullanır.
- Kullanıcılar, oturumlar, proje geçmişi ve ekipman kataloğu burada.
- DB yoksa web açılır ama giriş/kullanıcı işlemleri çalışmaz; `doctor` bunu
  `warn` olarak raporlar.
- Testler `test_admin` kullanıcısını oluşturur; `admin` hesabının şifresi
  bilinmiyorsa `python3 main.py --reset-admin` etkileşimli çalıştırılır.
- DB'yi silmeden önce kullanıcıya sor; proje geçmişi geri gelmez.

## 4. Test katmanları

```bash
python3 -m pytest -q                     # tam set (~3 dk)
python3 -m pytest -q test_api_v1.py      # API sözleşmesi
python3 -m pytest -q test_station_service.py test_pipe_sizing.py
QT_QPA_PLATFORM=offscreen python3 -m pytest -q test_ui_*.py
```

- Değişiklik öncesi etki alanı:
  `python3 .agents/skills/graphify/scripts/graphify.py impact <dosya>`
- TDD kapısı:
  `python3 .agents/skills/superpowers/scripts/superpowers_tdd.py run <test>`
- Tam set yeşil değilse iş tamam sayılmaz; yeni kırık test varsa önce onu
  düzelt veya gerekçesini raporla.

## 5. Web doğrulama akışı

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve
export KASP_VERIFY_RUN=$(cat .kasp-verify/last_run)
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py api
# tarayıcı: /#station, 3D, teardown, P&ID, raporlar
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py stop
```

`serve` çıktısındaki `base_url` kullanılır; 8081 sabit değildir.

## 6. Masaüstü notları

- Giriş ekranı PyQt5 diyaloğudur; otomatik testte `QT_QPA_PLATFORM=offscreen`.
- Masaüstü ve web aynı DB'yi paylaşır; eşzamanlı yazma için SQLite kilitleri
  kısa tutulur.
- Masaüstünde kullanıcıya görünen metinler `tr()` ile çevrilir.
- Masaüstü sürecini zorla kapatma; pencereyi kullanıcı kapatsın. Testte
  `QApplication` teardown'ı conftest tarafından yönetilir.

## 7. Tuzaklar

- `python3 kasp/api/server.py` doğrudan çalıştırıldığında `KASP_API_ENABLE=1`
  yoksa sessizce çıkar; bu bir hata değildir.
- `run_web.py` port ortam değişkenini `uvicorn.run` öncesi set eder; alt
  süreçlere açıkça geçir.
- `KASP_API_ALLOWED_ORIGINS` varsayılanı yalnızca 8000/8080'dir; farklı porttan
  tarayıcı çağrısı CORS'a takılabilir. Aynı origin'den servis edilen web UI
  etkilenmez.
- Testler CoolProp yükler; ilk açılış yavaştır. Sağlık kontrolünde en az 60 sn
  tanı.
- `.opencode/`, `.graphify/` ve `kasp_database.db` git dışıdır; run artefaktlarını
  commit etme. `.kasp-verify/` da git dışıdır.
