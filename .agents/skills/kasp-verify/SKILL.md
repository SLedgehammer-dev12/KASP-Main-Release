---
name: kasp-verify
description: >-
  KASP'ı gerçek uygulama üzerinden doğrular: izole web sunucusu başlatır, sağlık
  ve API sözleşmelerini denetler, tarayıcı adımlarını yeniden çalıştırılabilir
  komutlara çevirir ve ekran görüntüsü/ledger kanıtı toplar. OpenCode ve
  Antigravity/Agent-Skills ile aynı şekilde çalışır.
---

# KASP Verify — gerçek uygulamayı kanıtla

OpenHands `verify-openhands` yaklaşımının KASP uyarlaması: **route açıldı** veya
**test geçti** demek yetmez; kullanıcının gördüğünü kanıtla.

Üç parça birlikte çalışır:

1. **`scripts/kasp_verify.py`** — izole sunucu başlatır, doctor/API kontrolü
   yapar, kanıt defteri tutar. Yalnızca Python standart kütüphanesi kullanır.
2. **`references/features.json`** — kararlı ID'li özellik haritası
   (`F01`…`F16`), giriş noktası, beklenen sonuç ve tuzaklar.
3. **Kanıt** — ekran görüntüsü, gözlem ve `pass/fail/blocked/not-run`
   kayıtları; sunucu kapandıktan sonra da kalır.

Hiçbir komut dış servise yazmaz, ücretli model çağırmaz veya kullanıcının
çalışan sunucusunu durdurmaz.

## 0. Kısa yol

```bash
cd <repo-kökü>
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve
export KASP_VERIFY_RUN=$(cat .kasp-verify/last_run)
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py api
# tarayıcı adımları...
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py stop
```

Her komut tek bir JSON nesnesi yazar. Çıkış kodları: `0` ok, `1` işlem
başarısız, `2` kullanım hatası, `3` ortam hatası.

## 1. Doctor

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
```

Denetlenenler:

- repo kökü, Python sürümü, `fastapi/uvicorn/httpx/CoolProp`
- web varlıkları (`index.html`, `main.js`, `station3dView.js`, `three.min.js`)
- `kasp_database.db`, Node sürümü
- `.agents/skills/*/SKILL.md` frontmatter sözleşmesi
- `references/features.json` bütünlüğü
- `.opencode/opencode.json` içinde `.agents/skills` kaydı
- kök `AGENTS.md`
- 8000/8080/8081 port durumu (bilgi amaçlı; izole run başka port seçer)

`status=fail` ise doğrulamaya başlama. `warn` kabul edilebilir; nedeni kayda geçir.

## 2. İzole run

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve
# veya sabit port:
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve --port 8123
```

- Boş port otomatik seçilir (8090–8199). Kullanıcının 8080/8081 sunucusuna
  dokunulmaz.
- `run.json`, `server.log` ve kanıtlar `.kasp-verify/runs/<id>/` altına yazılır.
- Sağlık kapısı: `/api/health` `healthy` **ve** `/` HTTP 200 **ve** gövdede
  `KASP` geçmeli.
- Başarısızsa süreç kapatılır, `log_tail` raporlanır.

```bash
export KASP_VERIFY_RUN=$(cat .kasp-verify/last_run)
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py status
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py api
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py stop
```

`stop` yalnızca bu run'ın süreç grubunu kapatır ve PID'in `run_web.py`
olduğunu doğrular. **Asla** `pkill -f run_web.py`, `killall` veya başka bir
ajanın run dizinini kullanma.

## 3. API sözleşmesi

```bash
python3 .../kasp_verify.py api
KASP_VERIFY_USER=test_admin KASP_VERIFY_PASSWORD='...' \
  python3 .../kasp_verify.py api --login
```

- `/api/health` ve `/api/constants` her zaman kontrol edilir.
- Login yalnızca ortam değişkenleri verildiğinde çalışır; şifre/token
  yazdırılmaz ve diske yazılmaz.
- Login akışı: `POST /api/v1/auth/login` → `GET /api/v1/auth/me`
  (`X-CSRF-Token` + Bearer) → `POST /api/v1/auth/logout`.
- Kimlik bilgisi yoksa auth adımı `skipped` olur, bu bir hata değildir.

## 4. Tarayıcı adımları

Tarayıcı aracı harness'a göre değişir (OpenCode `browser.*`, Antigravity'nin
tarayıcı aracı veya harici Playwright). Kural aynı: **her adım yeniden
çalıştırılabilir olmalı**.

Temel seçiciler:

| Hedef | Seçici |
|---|---|
| Tasarım sekmesi | `[data-tab="design"]` |
| Performans sekmesi | `[data-tab="performance"]` |
| Shootout sekmesi | `[data-tab="shootout"]` |
| İstasyon sekmesi | `[data-tab="station"]`, `#nav-btn-station` |
| Loglar sekmesi | `[data-tab="logs"]` |
| 3D köprüsü | `window.__KASP_3D__` |
| Telemetri HUD | `#equip-telemetry-hud` |
| Teardown popup | `#kasp-equipment-teardown` |
| PDF / Excel | `#btn-pdf-export`, `#btn-module-excel` |

3D doğrulama için:

```js
window.__KASP_3D__.audit().length          // > 30 rota
window.__KASP_3D__.inspect("cyclones")     // HUD + teardown
window.__KASP_3D__.capture()               // canvas data URL
```

Konsol hatası varsa kaydet. Logout durumunda yalnızca beklenen
`401 /api/v1/auth/me` kabul edilir.

WebGL yoksa (headless CI) sonuç `blocked` olur; `fail` yazma.

## 5. Kanıt defteri

```bash
python3 .../kasp_verify.py evidence add \
  --feature F07 \
  --result pass \
  --entry "3D İstasyon & P&ID > 3D görünüm" \
  --expected "prosedürel tesis, >30 boru rotası" \
  --actual "42 rota, 1605 mesh, konsol temiz" \
  --artifact .kasp-verify/runs/<id>/f07.png

python3 .../kasp_verify.py evidence list
```

- `--run` verilmezse global ledger kullanılır: `.kasp-verify/evidence/`.
- `fail` sonucu `--actual` olmadan yazılamaz.
- Artefakt yolu yoksa komut hata verir.
- `ledger.md` her eklemede yeniden üretilir.

Sonuç anlamları:

| Sonuç | Anlam |
|---|---|
| `pass` | Beklenen davranış gerçekten gözlendi |
| `fail` | Ürün hatası; gözlem yazıldı |
| `blocked` | Ortam/erişim engeli (WebGL yok, kimlik yok) |
| `not-run` | Henüz denenmedi |
| `xfail` | Bilinen hata, beklenen başarısızlık |
| `xpass` | Bilinen hata artık geçiyor; incele |

## 6. Kaynak sahipliği

- Bu skill ürün kodunu değiştirmez. Bulgu `fail` ise sorumlu ajana yönlendir:
  `kasp-ui-agent` (web UI), `kasp-core-agent` (hesap), `kasp-data-agent`
  (DB/rapor), `kasp-qa-agent` (test).
- Düzeltme sonrası aynı komut yeniden çalıştırılır; yeni kanıt eklenir,
  eski kanıt silinmez.
- Kullanıcı istemeden ürün düzeltmesi yapılmaz.

## 7. Kabul kapısı

Bir iş "tamam" sayılmaz, ta ki:

1. `doctor` fail içermiyorsa,
2. etkilenen `Fxx` adımları gerçek uygulamada çalıştıysa,
3. `pass`/`blocked` kanıtı ledger'a yazıldıysa,
4. bağlı pytest testleri geçtiyse (`graphify impact` + `superpowers_tdd.py run`),
5. `stop` ile izole sunucu kapatıldıysa.
