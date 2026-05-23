# KASP Development Agents

KASP projesi icin ozel gelistirme ajanlari. Her ajan kendi sahiplik alanindaki dosyalari yonetir, diger ajanlarin alanlarina mudahale etmez.

## Ajan Listesi

| Ajan | Sahiplik | Sorumluluk |
|------|---------|-------------|
| **kasp-core-agent** | `kasp/core/` | Termodinamik hesaplama motoru, EOS, aerodinamik, turbin secimi |
| **kasp-ui-agent** | `kasp/ui/`, `kasp/i18n.py` | PyQt5 arayuz, tema, dil, validasyon, diyaloglar |
| **kasp-data-agent** | `kasp/data/`, `kasp/utils/` | SQLite, JSON projeleri, PDF raporlama, grafik uretimi, onbellek |
| **kasp-qa-agent** | `test_*.py`, `conftest.py` | Test kosumu, hata analizi, kalite guvencesi |
| **kasp-release-agent** | `release_metadata.py`, `build_*.py`, `*.spec` | Versiyon yonetimi, PyInstaller paketleme, CI/CD |

## Kullanim

Ajanlari `.opencode/opencode.json` icinde tanimlandigi sekilde kullanin. Her ajan `mode: subagent` olarak calisir.

## Ornek Komutlar

```bash
# Testleri calistir
python3 -m pytest -v --tb=short

# Uygulamayi baslat
python3 main.py

# Release build
python3 build_release.py
```

## Kurallar

1. Her ajan sadece kendi sahiplik alanindaki dosyalari degistirir
2. Ajanlar arasi iletisim: QA ajan bulgulari sorumlu ajana yonlendirilir
3. Degisiklikler sonrasi tum testler calistirilir
4. Kullaniciya gorunen tum metinler `kasp/i18n.py` uzerinden `tr()` ile cevrilir
