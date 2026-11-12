---
name: equipment-teardown
description: >-
  KASP web 3D ekipman teardown görünümleri. Gas cooler, siklon seperatör ve
  kartuş filtre seperatör gibi proses ekipmanlarını tıklanabilir popup içinde
  patlatılmış (exploded) 3D olarak gösterir; parça listesi, proses bilgileri ve
  söküm animasyonu üretir. OpenCode ve Antigravity/Agent-Skills uyumludur.
---

# KASP Equipment Teardown Skill

## Ne zaman kullanılır

- 3D sahnedeki bir proses ekipmanına tıklandığında bilgi + teardown popup'ı
  isteniyorsa.
- Gas cooler, siklon seperatör, kartuş filtre/koaleser gibi ekipmanların
  parçalarına ayrılmış görünümü gerekiyorsa.
- Parça listesi, proses değerleri ve söküm/montaj animasyonu birlikte
  gösterilecekse.

## Mevcut KASP uygulaması

| Dosya | Görev |
|---|---|
| `kasp/web/src/components/equipmentTeardown.js` | Framework-free Three.js teardown modalı |
| `kasp/web/src/components/station3dView.js` | Ekipman tıklama → `openEquipmentTeardown()` bağlantısı |
| `kasp/web/vendor/three.min.js` | Global `window.THREE` |
| `kasp/web/vendor/OrbitControls.js` | `THREE.OrbitControls` |

## Kullanım

```js
import { openEquipmentTeardown, closeEquipmentTeardown } from "./equipmentTeardown.js";

openEquipmentTeardown("air_coolers", {
  eq,                 // equipment_sizing
  sm,                 // station_summary
  sucLine,            // station_piping.lines.suction_header
  numCyclones,
  numFilters,
  numCoolerBays,
  title: "Gas Cooler · Fin-Fan Teardown",
  subtitle: "E-101 · API 661 söküm görünümü",
});
```

Desteklenen anahtarlar:

- `air_coolers`
- `cyclones`
- `cartridge_filters`

## Tasarım kuralları

1. **Tek kaynak**: parça ölçüleri ve proses bilgileri aynı `context` verisinden
   gelir; panel ile model çelişmez.
2. **Gerçek referans**: fin-fan, dikey siklon ve yatay koaleser filtre
   geometrisi gerçek ekipman fotoğraflarına/kesitlerine göre modellenir.
3. **Patlatma yönleri**: ağır parçalar aşağı, üst kapak/louver yukarı, yan
   nozullar dışa; parçalar birbirinin içinden geçmez.
4. **Yarı saydam kabuk**: basınç kabuğu `opacity ≈ 0.30` ve `DoubleSide` olur;
   iç elemanlar (vorteks bulucu, koaleser, kartuşlar) görünür kalır.
5. **Temizlik**: modal kapanınca RAF, ResizeObserver, OrbitControls,
   geometry/material ve renderer dispose edilir.
6. **Erişilebilirlik**: `Esc` kapatır; parça listesi ve 3D etiketler tıklanabilir.

## OpenCode / Antigravity uyumu

- Skill yalnızca Markdown ve standart Agent-Skills frontmatter'ı kullanır.
- Uygulama kodu framework-free'dir; global THREE ve OrbitControls dışında
  bağımlılık yoktur.
- `npm`, `playwright`, `ffmpeg` veya harici build gerektirmez.
- Antigravity'de `.agents/skills/equipment-teardown/SKILL.md` olarak,
  OpenCode'da aynı yol veya `.opencode/skills/` üzerinden okunabilir.
- Büyük model dosyası (GLB/GLTF) yüklemez; geometri prosedürel üretilir.

## Genişletme

Yeni ekipman eklemek için:

1. `equipmentTeardown.js` içine `build<Equipment>()` fonksiyonu ekle.
2. Parçaları `addPart(name, desc, group, explodeVector, labelAnchor, color)` ile
   kaydet.
3. `infoRows()` içine ekipman proses bilgilerini ekle.
4. `key` eşlemesini `if/else` zincirine ekle.
5. `station3dView.js` içindeki `TEARDOWN_KEYS` kümesine anahtarı ekle.
