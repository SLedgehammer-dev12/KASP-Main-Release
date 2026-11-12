---
name: kasp-harness-interop
description: >-
  KASP ajan ve becerilerini OpenCode, Antigravity ve ACP uyumlu istemcilerde
  (OpenHands Agent Canvas dahil) aynı kaynaktan çalıştırır. Yeni beceri eklerken,
  harness uyumluluğunu doğrularken veya taşınabilirlik bozukluğunu ayıklarken
  kullanılır.
---

# KASP Harness Interop

Amaç: **tek kaynak, çok harness**. Beceriler `.agents/skills/<ad>/SKILL.md`
altında yaşar; OpenCode, Antigravity ve ACP istemcileri aynı dosyaları okur.
Kopya skill, harness'a özel araç adı veya mutlak yol yoktur.

Makine-okunur kayıt: [`.agents/harness.json`](../../harness.json).

## 1. Keşif matrisi

| Harness | Talimat | Skill yolu | Ajan tanımı |
|---|---|---|---|
| OpenCode | `.opencode/AGENTS.md` | `.opencode/skills`, `.agents/skills` | `.opencode/agents/*.md` + `opencode.json` |
| Antigravity | `AGENTS.md` | `.agents/skills` | `.opencode/agents` (opsiyonel) |
| ACP / OpenHands Agent Canvas | `AGENTS.md` | `.agents/skills` | OpenCode'u ACP backend olarak çalıştırır |

OpenCode yapılandırması:

```json
{
  "instructions": [".opencode/AGENTS.md"],
  "skills": { "paths": [".opencode/skills", ".agents/skills"] }
}
```

Antigravity ek kurulum istemez: repo kökünü aç, `AGENTS.md` ve
`.agents/skills/*/SKILL.md` okunur.

OpenHands Agent Canvas: Agent Canvas → Add backend → ACP → komut `opencode`,
çalışma dizini repo kökü. Sandbox kullan; sandbox'sız mod tüm dosya sistemine
erişir.

## 2. Taşınabilirlik sözleşmesi

Bir `SKILL.md` şu kurallara uyar:

1. `---` ile başlayan YAML frontmatter; `name` ve `description` zorunlu.
2. `name` = klasör adı. Örn. `.agents/skills/kasp-verify/` → `name: kasp-verify`.
3. `description` en az 30 karakter; ne zaman kullanılacağını yazar.
4. Harness'a özel araç adı geçmez (`browser_*`, `read_file`, `task` gibi).
   Bunun yerine shell komutu, dosya yolu ve beklenen gözlem yazılır.
5. Tüm yollar repo köküne göre relative. Mutlak kullanıcı yolu yok.
6. Script'ler Python standart kütüphanesi veya repoda zaten olan bağımlılığı
   kullanır; `pip install` gerektirmez.
7. Script'ler idempotent ve kendi oluşturduğu süreci/dosyayı temizler.
8. Ağ, kimlik bilgisi ve dış servis varsayılan olarak kullanılmaz; gerekiyorsa
   ortam değişkeniyle opt-in olur.
9. Skill, ürün kodunu değiştirmez; bulguyu sorumlu ajana devreder.
10. Doğrulama komutu skill içinde açıkça yazılır.

## 3. Yeni skill iskeleti

```text
.agents/skills/<ad>/
├── SKILL.md
├── references/        # opsiyonel: harita, şema, uzun rehber
└── scripts/           # opsiyonel: stdlib CLI
```

```markdown
---
name: <ad>
description: >-
  Ne yapar, ne zaman kullanılır, hangi harness'larda çalışır.
---

# <Başlık>

## Ne zaman kullanılır
## Girdiler / sahiplik
## Adımlar
## Doğrulama
## Tuzaklar
```

Ekledikten sonra:

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py selftest
```

`doctor` frontmatter, isim klasör uyumu, `.opencode/opencode.json` kaydı ve
`AGENTS.md` varlığını denetler.

## 4. Mevcut KASP becerileri

| Skill | Görev | Script |
|---|---|---|
| `mudur` | Orkestrasyon ve kalite kapıları | — |
| `superpowers` | TDD, planlama, 4 aşamalı hata ayıklama | `superpowers_tdd.py` |
| `graphify` | AST etki analizi ve test eşleştirme | `graphify.py` |
| `repo-indexer` | Repo haritası ve bağlam özeti | — |
| `iterative-improver` | Tek yüksek etkili iyileştirme döngüsü | — |
| `caveman` | Sıkıştırılmış ajan iletişimi | — |
| `equipment-teardown` | 3D ekipman söküm popup'ı | — |
| `kasp-verify` | Gerçek uygulama doğrulama + kanıt | `kasp_verify.py` |
| `kasp-api-contracts` | FastAPI/web sözleşmesi | — |
| `kasp-frontend` | ES modülü UI + Three.js kuralları | — |
| `kasp-local-stack` | Masaüstü/web/test çalıştırma | — |
| `kasp-harness-interop` | Bu belge | — |

## 5. OpenCode akışı

OpenCode `skill` aracıyla yükler. Tipik sıra:

```text
mudur → graphify impact → superpowers (plan/TDD) → kasp-verify (gerçek uygulama)
```

Alt ajanlar `.opencode/opencode.json` içinde `mode: subagent` olarak tanımlıdır.
Caveman protokolü varsayılandır; dosya yolu, satır numarası, birim ve hata
metni birebir korunur.

## 6. Antigravity akışı

1. Repo kökünü aç.
2. `AGENTS.md` otomatik okunur; değilse elle referans ver.
3. Skill'i adıyla çağır veya `SKILL.md` yolunu göster.
4. Komutları repo kökünden çalıştır:

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/graphify/scripts/graphify.py impact kasp/core/thermo.py
```

Antigravity'nin tarayıcı aracı varsa `kasp-verify` seçicilerini kullan; yoksa
`blocked` kanıtı yaz, uydurma `pass` yazma.

## 7. ACP / OpenHands akışı

```text
Agent Canvas
  └─ backend: ACP
       └─ command: opencode
            └─ workspace: <KASP repo>
                 ├─ AGENTS.md
                 └─ .agents/skills/*/SKILL.md
```

- OpenCode ACP uyumludur; ayrı bir adaptör yazmak gerekmez.
- Sandbox modu önerilir; ajan tüm dosya sistemine erişebilir.
- Kimlik bilgilerini ortam değişkeniyle ver, istem/proje dosyasına yazma.
- Uzun süren doğrulamayı `kasp_verify.py serve` ile izole et.

## 8. Sorun giderme

| Belirti | Neden | Çözüm |
|---|---|---|
| Skill listede yok | frontmatter bozuk / yol eksik | `doctor`; `skills.paths` içine `.agents/skills` |
| İki harness farklı davranıyor | kopya skill veya mutlak yol | Tek kaynak `.agents/skills`; kopyayı sil |
| `name does not match folder` | klasör adı değişmiş | `name` alanını güncelle |
| Script başka makinede çalışmıyor | mutlak yol / eksik paket | Repo-relative yol, stdlib |
| Ajan ürün kodunu değiştirdi | skill sınırı yok | Skill'e "ürün kodunu değiştirmez" ekle |
| Kanıt kayboldu | run dizini silinmiş | Global `.kasp-verify/evidence/ledger.md` kullan |

## 9. Kabul kapısı

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py selftest
python3 -m pytest -q test_harness_contracts.py
```

Üçü de yeşil değilse harness uyumluluğu tamam sayılmaz.
