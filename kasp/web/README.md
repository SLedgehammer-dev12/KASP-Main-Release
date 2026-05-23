# KASP V4 Web Analitik Platformu

KASP V4, artık modern bir web arayüzüne sahip. Bu arayüz, gelişmiş termodinamik hesaplamalarınızı (Çok Kademeli Sıkıştırma, Pompaj Analizi) tarayıcı üzerinden kolayca yapmanızı sağlar.

## 🚀 Hızlı Başlangıç

### 1. Sunucuyu Başlatın
Aşağıdaki komutu terminalde çalıştırın:
```bash
python kasp/api/server.py
```

### 2. Arayüze Erişin
Tarayıcınızda şu adrese gidin:
**[http://localhost:8000](http://localhost:8000)**

## ✨ Özellikler

- **Çok Kademeli Analiz**: 10 kademeye kadar otomatik basınç dağılımı ve ara soğutma hesabı.
- **Dinamik Grafikler**: Her hesaplama sonrası anında güncellenen T-s ve Güç grafikleri.
- **Modern Arayüz**: Karanlık mod, mobil uyumlu tasarım ve anlık veri girişi.
- **Kurulumsuz (No-Build)**: Node.js gerektirmez, tek bir Python komutuyla çalışır.

## 🛠️ Teknik Altyapı
- **Backend**: FastAPI (Python) - Yüksek performanslı asenkron API.
- **Frontend**: Vue.js 3 + TailwindCSS - CDN üzerinden çalışan modern SPA.
- **Motor**: KASP V4 ThermoEngine (CoolProp & Real Gas EOS).
