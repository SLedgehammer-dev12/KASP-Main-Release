---
name: kasp-frontend
description: >-
  KASP web arayüzü için yapı ve görselleştirme kuralları: derlemesiz ES modülleri,
  store abonelikleri, i18n, güvenli innerHTML, Three.js 3D sahnesi, boru çapı
  türetimi, ekipman tıklama ve teardown popup. Web UI değiştirirken kullanılır.
---

# KASP Frontend

KASP web arayüzü **derlemesiz** çalışır: tarayıcı ES modüllerini doğrudan yükler,
üçüncü parti kütüphaneler `kasp/web/vendor/` altında yereldir. `npm install`,
bundler, transpiler veya CDN yoktur.

## 1. Yerleşim

```text
kasp/web/index.html                  → import map + kök DOM
kasp/web/src/main.js                 → sekmeler, mount, hash yönlendirme
kasp/web/src/components/*.js         → ekranlar ve modallar
kasp/web/src/store/{ui,project,auth}Store.js
kasp/web/src/api/client.js           → tek API girişi
kasp/web/src/i18n/locales.js         → t(key, lang)
kasp/web/css/{tokens,layout,components}.css
kasp/web/vendor/{three.min.js,OrbitControls.js,plotly.min.js,icons.js}
```

Yeni bir ekran:

1. `components/yeniEkran.js` içinde `export function renderYeniEkran(container)`.
2. `main.js` içinde mount noktasını ve gerekiyorsa `data-tab` düğmesini ekle.
3. `uiStore` aboneliğini mount içinde kur; her abonelikte DOM'u yeniden üretme,
   yalnızca değişen düğümü güncelle.
4. Temizlenecek listener/timer varsa `destroy()` döndür veya `uiStore`
   değişiminde tekrar mount edilirken öncekini kapat.

## 2. Durum ve veri akışı

- Kaynak gerçek tek yerde: `projectStore` (girdi/sonuç/modül/istasyon),
  `uiStore` (sekme, tema, modal, toast), `authStore` (kullanıcı).
- Bileşen kendi kopya state'ini tutmaz; store'dan okur, store'a yazar.
- Hesaplama `projectStore.runDesignCalculation()` üzerinden yapılır; bileşen
  doğrudan `api.post` çağırmaz (istisna: modül/istasyon alt çağrıları).
- `api` singleton'ı dışında `fetch` yoktur. Bkz. `kasp-api-contracts`.

## 3. i18n ve metin

- Web metinleri varsayılan Türkçe; çevrilebilir anahtarlar
  `t("anahtar", ui.lang)` ile `i18n/locales.js` üzerinden gelir.
- Yeni anahtar eklerken `tr` ve `en` sözlüklerine birlikte ekle; eksik anahtar
  ham anahtar olarak görünür.
- Teknik birimler (`bar(a)`, `kg/s`, `°C`, `MWth`, `NPS`, `OD`) çevrilmez.
- PyQt tarafı ayrıdır: `kasp/i18n.py` `tr()` zorunludur; web ve masaüstü
  metinlerini karıştırma.

## 4. Güvenli DOM

- Kullanıcı/API kaynaklı her değer `innerHTML` öncesi `escapeHtml()` ile
  kaçırılır. `logsTab`, `userModal`, `projectModal` bu deseni kullanır.
- Log mesajı, proje adı, ekipman modeli ve hata metni asla ham HTML basılmaz.
- `innerHTML` ile kurulan tablo satırlarında sayı biçimlendirmesi JS'te yapılır;
  template içinde Python biçim belirteci kullanılmaz. Örnek hata:
  `${Math.round(x):,}` → `Math.round(x).toLocaleString("tr-TR")`.
- `onclick="..."` üretme; `addEventListener` kullan.

## 5. 3D sahne (`station3dView.js`)

- `createStation3dView(container, stationData, onSelectEquipment, options)`
  `{destroy, getState, selectEquipment, clearSelection, ...}` döndürür.
- Boru yarıçapları **tek kaynaktan** türetilir:
  `visualPipeRadius(line.od_mm, fallbackOd)`; sabit yarıçap yazma.
- `createCadPipeRoute(points, radius, material, {flowArrows, equipKey, ...})`
  rotaları `pipeRoutes` denetim kaydına ekler; çakışma denetimi buna dayanır.
- Kesit/dirsek yükseklikleri (`coolerOutletCrossY`, `coolerBypassY`,
  `antiSurgeCrossY`) boru yarıçaplarından hesaplanır; sabit sayı yazma.
- Ekipman tıklaması `registerClickable(group, equipKey)` ile yapılır; kök grup
  `userData.equipKey` taşır.
- `air_coolers`, `cyclones`, `cartridge_filters` tıklamaları hem telemetri
  HUD'ını hem `openEquipmentTeardown()` popup'ını açar.
- `destroy()` içinde: RAF iptali, `ResizeObserver`, `OrbitControls`, tüm
  geometry/material/texture, `renderer.dispose()` ve `__KASP_3D__` temizliği.
- Debug köprüsü: `window.__KASP_3D__.audit()`, `.inspect(key)`, `.capture()`,
  `.scene`, `.renderer`.

3D kural özeti:

| Kural | Neden |
|---|---|
| Çap `od_mm`'den | Vana/boru/etiket tutarlılığı |
| Dinamik geçiş kotu | Çap büyüyünce çakışma olmaz |
| Tek anti-surge header | PFD topolojisi |
| Discharge header → gas cooler | Proses akışı |
| Ekipman seviyesinde tıklama | HUD + teardown aynı seçimi paylaşır |

## 6. Doğrulama

```bash
node --check kasp/web/src/components/station3dView.js
node --check kasp/web/src/components/equipmentTeardown.js
node --check kasp/web/src/components/stationTab.js
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py doctor
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py serve
```

Tarayıcıda:

1. Konsolu aç; beklenmeyen hata varsa dur.
2. `window.__KASP_3D__.audit().length` > 30 olmalı.
3. 2/3/4 ünite düzenlerini ayrı ayrı kontrol et; boru-boru çakışması 0 olmalı.
4. Ekipman tıkla → HUD → teardown → `Esc` ile kapanış.
5. Sekme değiştir, pencereyi yeniden boyutlandır; canvas ölçüsü ve RAF temiz
   kalmalı.

## 7. Tuzaklar

- `headerEastX` gibi değişkenleri kullanmadan önce tanımla; TDZ hatası tüm
  modülü düşürür.
- Template literal içinde `:` biçim belirteci kullanma.
- `innerHTML` ile yeniden kurulan canvas mount'unu boşaltmadan renderer oluşturma.
- Vendor dosyalarını değiştirme; `vendor/` upstream kopyasıdır.
- `kasp/web/README.md` eski Vue/Chart.js anlatımı içerebilir; gerçek kaynak
  `src/` altındaki ES modülleridir.
