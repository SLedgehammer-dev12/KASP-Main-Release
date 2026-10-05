# KASP V4 Web Analitik Platformu

KASP V4, modern bir web arayüzü sunar. Bu arayüz ile çok kademeli sıkıştırma ve pompaj (benchmark) analizlerini tarayıcı üzerinden yapabilirsiniz.

> **Not:** `kasp/api/server.py` **legacy/experimental** olarak işaretlenmiştir ve varsayılan olarak **KAPALIDIR**. Kimlik doğrulama (Bearer token) ve IP bazlı hız sınırı uygulanır.

## 🚀 Hızlı Başlangıç

### 1. API'yi etkinleştirin
Sunucu, güvenlik gereği yalnızca `KASP_API_ENABLE=1` **ve** `KASP_API_TOKEN` ayarlandığında başlar. Token yoksa süreç başlatılmaz.

```bash
export KASP_API_ENABLE=1
export KASP_API_TOKEN="<guclu-rastgele-token>"
python3 kasp/api/server.py
```

Kök dizinden modül olarak da başlatılabilir:

```bash
python3 -m kasp.api.server
```

### 2. Arayüze erişin
Tarayıcınızda şu adrese gidin:

**[http://localhost:8000](http://localhost:8000)**

## ✨ Özellikler

- **Çok Kademeli Analiz**: 10 kademeye kadar otomatik basınç dağılımı ve ara soğutma hesabı.
- **Dinamik Grafikler**: Her hesaplama sonrası anında güncellenen T-s ve Güç grafikleri.
- **Modern Arayüz**: Karanlık mod, mobil uyumlu tasarım ve anlık veri girişi.
- **Kurulumsuz (No-Build)**: Node.js gerektirmez, tek bir Python komutuyla çalışır.

## 🛠️ Teknik Altyapı

- **Backend**: FastAPI (Python) — `uvicorn` ile çalışan asenkron REST API.
- **Frontend**: Vue.js 3 + TailwindCSS (CDN üzerinden), Chart.js ve Lucide ikonları.
- **Motor**: `kasp.core.thermo.ThermoEngine` (CoolProp & gerçek gaz EOS).

## 🔌 API Uç Noktaları

| Metot | Yol | Kimlik Doğrulama | Açıklama |
| :--- | :--- | :--- | :--- |
| GET | `/api/health` | Hayır | Sağlık durumu |
| GET | `/api/constants` | Hayır | Gaz listesi, birimler, varsayılan kompozisyon |
| POST | `/api/calculate/design` | Bearer token | Tek/çok kademeli tasarım hesabı |
| POST | `/api/calculate/benchmark` | Bearer token | EOS × metot karşılaştırması |

Korumalı uç noktalar `Authorization: Bearer <KASP_API_TOKEN>` başlığı gerektirir.

## ⚠️ Bilinen Kısıtlar

- Arayüz, üstteki **API Token** alanına girilen değeri `localStorage`'da saklar ve korumalı çağrılarda `Authorization: Bearer <token>` başlığı olarak gönderir. Token boş/geçersizse üstteki rozet **"Token gerekli"** olur ve çağrılar `401/403` döner.
- Üretim ortamı için tasarlanmamıştır; yalnızca yerel/geliştirme kullanımı içindir.
- CORS varsayılan olarak `http://127.0.0.1:8000` ve `http://localhost:8000` ile sınırlıdır (`KASP_API_ALLOWED_ORIGINS` ile genişletilebilir).
