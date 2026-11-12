---
name: kasp-api-contracts
description: >-
  KASP web istemcisi ile FastAPI v1 arasındaki sözleşmeyi korur: uç nokta,
  Pydantic şeması, kimlik/CSRF, hata gövdesi, dosya akışı ve proje kalıcılığı.
  API çağrısı eklerken veya backend yanıtını değiştirirken kullanılır; OpenCode
  ve Antigravity aynı kuralları okur.
---

# KASP API Contracts

Web istemcisi, API'nin **tipli tüketicisidir**. Sözleşme değişikliği hem
`kasp/api/v1/` hem `kasp/web/src/` hem de testlerde aynı anda yapılır.

## 1. Katmanlar ve sahiplik

```text
kasp/web/src/components/*  →  yalnızca api.* üzerinden konuşur
kasp/web/src/store/*       →  iş akışı + kalıcı durum
kasp/web/src/api/client.js →  tek fetch/CSRF/Bearer/indirme noktası
kasp/api/v1/*.py           →  yönlendirme + Pydantic + yetki
kasp/services/*            →  saf iş mantığı (UI/HTTP bilmez)
kasp/api/auth.py           →  session_store, CSRF, RBAC
```

Kurallar:

1. `fetch(` yalnızca `kasp/web/src/api/client.js` içinde bulunur. Bileşenler
   `api.get/post/put/delete/downloadFile` kullanır.
2. İş mantığı router içine gömülmez; `kasp/services/` çağrılır. Router ince
   kalır, hata eşlemesi yapar.
3. Aynı veri iki yerde hesaplanmaz. Özet kart, 3D ve P&ID aynı yanıtı tüketir.
4. Kullanıcıya görünen metinler web'de Türkçe tutarlılıkla yazılır; PyQt
   tarafında `kasp/i18n.py` `tr()` zorunludur.

## 2. Auth ve CSRF

- `POST /api/v1/auth/login` → `{user, token, csrf_token, must_change_password}`.
  Ayrıca `kasp_session` HttpOnly cookie set edilir.
- İstemci `token`'ı localStorage'da, `csrf_token`'ı bellekte tutar.
- Durum değiştiren her istek `X-CSRF-Token` taşır; Bearer da gönderilir.
- Okuma uç noktaları `get_current_user_optional` kullanabilir; kullanıcıya özel
  veri ve tüm mutasyonlar `get_current_user` / `require_permission` kullanır.
- `401` istemcide `kasp:unauthorized` olayını tetikler; oturum kapatılır.
- `must_change_password=1` ise kullanıcı şifre değiştirmeden işlem yapamaz.

Yetki seviyeleri: `admin` kullanıcı yönetimi ve tüm projeler; normal kullanıcı
yalnızca kendi kayıtları.

## 3. Uç nokta haritası

| Alan | Uç nokta | Not |
|---|---|---|
| Auth | `/api/v1/auth/*` | login, logout, me, change-password, recovery |
| Kullanıcılar | `/api/v1/users` | admin; reset-password |
| Meta | `/api/v1/meta/constants`, `/meta/presets`, `/thermo/gases` | public |
| Termo | `/api/v1/thermo/recommendations`, `/thermo/kij-matrix` | public |
| Hesap | `/api/v1/calculations/design`, `/performance`, `/station`, `/pipe-sizing` | ağır iş `asyncio.to_thread` |
| Ekipman | `/api/v1/equipment/turbines`, `/compressors` | CRUD + CSV import |
| Projeler | `/api/v1/projects` | liste/kaydet/sil, `export-kasp`, `import-kasp`, `export-results-json` |
| Raporlar | `/api/v1/reports/pdf`, `/modules-excel`, `/performance-pdf` | StreamingResponse |
| Jobs | `/api/v1/jobs/shootout`, `/{id}/status`, `/{id}/cancel`, `/{id}/stream` | SSE |
| Loglar | `/api/v1/logs`, `/logs/stream` | SSE, admin temizler |
| Modüller | `/api/v1/modules`, `/{id}/schema`, `/{id}/calculate` | entegrasyon |

## 4. Şema ve hata sözleşmesi

- İstek gövdesi Pydantic modelidir; `Field` ile aralık ve sonlu sayı kontrolü
  yapılır (`gt`, `le`, `allow_inf_nan=False`).
- Başarılı tasarım yanıtı:
  `{success, warnings, inputs, results, selected_units, charts}`.
- Hata gövdesi daima `{"detail": ...}` biçimindedir:
  - doğrulama: `422` + `detail: {errors: [...], warnings: [...]}`
  - yetki: `401/403`
  - bulunamadı: `404`
  - bağımlılık yok: `501` (ör. ReportLab yok)
  - beklenmeyen: `500`, mesaj kullanıcıya anlaşılır, stack trace sızdırılmaz.
- İstemci `detail` string/dizi/nesne biçimlerini tek mesaja çevirir; bileşen
  `error.message` gösterir, ham yanıtı HTML olarak basmaz.

## 5. Dosya ve akış

- PDF/Excel `StreamingResponse` ile bellekten akar; geçici dosya yazılmaz.
- İstemci `api.downloadFile(url, body, fallbackName)` kullanır; `Content-Disposition`
  dosya adını belirler.
- `.kasp` importu `multipart/form-data`, 2 MB üst sınır ve şema migrasyonu ile
  yapılır. Sınır `MAX_KASP_FILE_SIZE` ile korunur.
- Proje dosyasına token, şifre, session veya mutlak dosya yolu yazılmaz.

## 6. Değişiklik kontrol listesi

1. `python3 .agents/skills/graphify/scripts/graphify.py impact <dosya>` ile
   etkilenen servis/testleri çıkar.
2. Pydantic modelini ve yanıt şeklini güncelle; geriye dönük alanları silme,
   yeni alanı opsiyonel ekle.
3. `kasp/web/src/api/client.js` dışında `fetch` açmadığını doğrula.
4. `test_api_v1.py` içine mutlu yol + yetkisiz/bozuk gövde testi ekle.
5. `python3 -m pytest -q test_api_v1.py test_services.py` çalıştır.
6. Gerçek uygulamada `kasp_verify.py api` ve ilgili `Fxx` adımını doğrula.

## 7. Tuzaklar

- CSRF başlığı olmadan `POST` → `403`; yalnızca Bearer yeterli değildir.
- Oturum cookie'si `SameSite=Lax`; farklı origin'den çağrı yapma.
- `downloadFile` hata durumunda JSON `detail` okur; blob'u hata gövdesi sanma.
- Ağır hesabı event loop'ta çalıştırma; `asyncio.to_thread` kullan.
- SSE bağlantısı proxy/uvicorn tamponunda kalabilir; `text/event-stream` ve
  keep-alive yorumları gerekir.
- Test kullanıcısı oluşturup sil; `test_admin` gibi hesapların şifresini
  değiştirme.
