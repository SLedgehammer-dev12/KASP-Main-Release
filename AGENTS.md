# KASP — Agent Guide

Bu dosya **tüm ajan harness'ları** için ortak giriş noktasıdır: OpenCode,
Antigravity ve ACP uyumlu istemciler (OpenHands Agent Canvas dahil).
OpenCode'a özel ajan tanımları `.opencode/` altındadır; beceriler tek kaynaktan
`.agents/skills/` altından okunur.

Makine-okunur kayıt: [`.agents/harness.json`](.agents/harness.json)

## 1. Proje

KASP, doğal gaz kompresör istasyonları için termodinamik tasarım, türbin seçimi,
ASME PTC-10 performans değerlendirmesi, entegrasyon modülleri, PDF/Excel raporlama
ve prosedürel 3D dijital ikiz sunan bir mühendislik platformudur.

| Katman | Yer |
|---|---|
| Termodinamik çekirdek, EOS, aerodinamik | `kasp/core/` |
| Servisler (istasyon, boru, hesap) | `kasp/services/` |
| Veri, SQLite, projeler, raporlama | `kasp/data/`, `kasp/utils/` |
| PyQt5 masaüstü | `kasp/ui/`, `kasp/i18n.py` |
| FastAPI v1 | `kasp/api/` |
| Web UI (derlemesiz ES modülleri) | `kasp/web/` |
| Entegrasyon modülleri | `kasp/integrations/` |
| Testler | `test_*.py`, `conftest.py` |

## 2. Hızlı komutlar

```bash
# Masaüstü
python3 main.py

# Web (ilk boş port: 8080 → 8000 → 8081 → 8082)
python3 run_web.py

# Tam test seti (~3 dk)
python3 -m pytest -q

# Etki analizi
python3 .agents/skills/graphify/scripts/graphify.py impact kasp/core/thermo.py

# TDD / bağlı test koşucusu
python3 .agents/skills/superpowers/scripts/superpowers_tdd.py run test_station_service.py

# Gerçek uygulama doğrulaması (izole sunucu + kanıt)
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve
export KASP_VERIFY_RUN=$(cat .kasp-verify/last_run)
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py api
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py stop
```

## 3. Sahiplik

| Ajan | Alan |
|---|---|
| `kasp-mudur-agent` | Tüm proje, ajan/skill orkestrasyonu, kalite kapıları |
| `kasp-core-agent` | `kasp/core/` |
| `kasp-ui-agent` | `kasp/ui/`, `kasp/i18n.py` |
| `kasp-data-agent` | `kasp/data/`, `kasp/utils/` |
| `kasp-qa-agent` | `test_*.py`, `conftest.py` |
| `kasp-release-agent` | `release_metadata.py`, `build_*.py`, `*.spec` |
| `kasp-graphify-agent` | `.graphify/`, `.agents/skills/graphify/` |
| `kasp-superpowers-agent` | `.agents/skills/superpowers/` |

Her ajan yalnızca kendi alanını değiştirir. Alan dışı bir düzeltme gerekiyorsa
sorumlu ajana devreder; kullanıcı istemeden başka alana müdahale etmez.

## 4. Zorunlu kurallar

1. **Etki analizi**: `kasp/core`, `kasp/data`, `kasp/ui`, `kasp/services`
   değişikliklerinden önce `graphify impact` çalıştır ve bağlı testleri not et.
2. **TDD**: Önce başarısız test (Red), sonra minimal kod (Green), sonra refaktor.
3. **Doğrulama kapısı**: Bağlı testler + `kasp_verify.py doctor` + etkilenen
   `Fxx` adımı. Test yeşil değilse iş tamam değildir.
4. **i18n**: PyQt metinleri `kasp/i18n.py` içinden `tr()` ile; web metinleri
   `kasp/web/src/i18n/locales.js` içinden `t(key, lang)` ile.
5. **Sır yok**: Şifre, token, session veya `.env` içeriği kod, test, log, kanıt
   ya da proje dosyasına yazılmaz.
6. **Süreç hijyeni**: `pkill -f run_web.py`, `killall` veya başka ajanın run
   dizinini kullanma. `kasp_verify.py stop` yalnızca kendi sürecini kapatır.
7. **İletişim**: Varsayılan Caveman protokolü — `[Bileşen] [Eylem] [Gerekçe].
   [Sonraki Adım].` Dosya yolları, satır numaraları, birimler ve hata metinleri
   birebir korunur. Güvenlik/veri kaybı uyarılarında tam cümle kullan.
8. **Kullanıcı onayı**: Yıkıcı işlem (DB silme, force push, release, admin
   şifresi değiştirme) öncesi sor.
9. **Kapsam**: İstenmeyen refaktor veya özellik ekleme yapma. Tek seferde tek
   yüksek etkili iyileştirme.

## 5. Beceriler

| Skill | Ne zaman |
|---|---|
| `mudur` | Çok adımlı işi planla, ajanlara böl, kalite kapısı koy |
| `superpowers` | Planlama, TDD, 4 aşamalı hata ayıklama |
| `graphify` | Değişiklik öncesi etki alanı ve test haritası |
| `repo-indexer` | Repo haritası, giriş noktaları, sıcak dosyalar |
| `iterative-improver` | Tek bir iyileştirme öner ve onayla uygula |
| `caveman` | Token tasarruflu ajan iletişimi |
| `equipment-teardown` | 3D ekipman söküm popup'ı |
| `kasp-verify` | Gerçek uygulamada doğrulama + kanıt defteri |
| `kasp-api-contracts` | FastAPI/web sözleşmesi değişikliği |
| `kasp-frontend` | Web UI, ES modülleri, Three.js sahnesi |
| `kasp-local-stack` | Sunucu, port, test, masaüstü çalıştırma |
| `kasp-harness-interop` | Harness uyumluluğu ve yeni skill ekleme |

## 6. Harness uyumluluğu

- **OpenCode**: `.opencode/opencode.json` içinde `skills.paths` hem
  `.opencode/skills` hem `.agents/skills` içerir. Ajanlar `.opencode/agents/`
  altında `mode: subagent` olarak tanımlıdır.
- **Antigravity**: Repo kökünü aç; bu dosya ve `.agents/skills/*/SKILL.md`
  okunur. Ek kurulum gerekmez.
- **ACP / OpenHands Agent Canvas**: OpenCode'u ACP backend olarak ekle
  (`command: opencode`, workspace: repo kökü). Sandbox modu önerilir.

Skill taşınabilirlik kuralları: `name` = klasör adı, açıklama ≥ 30 karakter,
repo-relative yollar, harness'a özel araç adı yok, script'ler stdlib.
Ayrıntı: `.agents/skills/kasp-harness-interop/SKILL.md`.

## 7. Tamamlanma tanımı

- [ ] Değişiklik yalnızca sahiplik alanında
- [ ] Etki analizi ve bağlı testler çalıştırıldı
- [ ] Yeni/değişen davranış için test var
- [ ] `python3 -m pytest -q` yeşil (veya bilinen, gerekçeli istisna)
- [ ] JS için `node --check` geçti
- [ ] `kasp_verify.py doctor` fail içermiyor
- [ ] Etkilenen `Fxx` adımı gerçek uygulamada doğrulandı, kanıt yazıldı
- [ ] İzole sunucu `stop` ile kapatıldı
- [ ] Kullanıcıya dosya yolu + test sonucu + kalan risk özeti verildi
