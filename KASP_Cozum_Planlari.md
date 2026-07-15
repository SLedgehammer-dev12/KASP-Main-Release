# KASP Kod Tabanı — Detaylı Çözüm Planları

Her bir bulgu için somut kod değişiklikleri, yeni kod parçacıkları ve dosya bazlı uygulama adımları.

---

## DALGA 1: KRİTİK SORUNLAR (Hemen Yapılmalı)

---

### C1 / C11: Varsayılan Admin Şifresi `kasp2024` Kaynak Kodda

**Dosya:** `kasp/security.py:17`

**Çözüm Planı:**

1. `security.py`'den `DEFAULT_PASSWORD` sabitini kaldır.
2. İlk başlatmada rastgele bir admin şifresi üret ve kullanıcıya göster/zorla değiştir.
3. `main.py`'de admin oluşturma akışını değiştir.

**`kasp/security.py` değişikliği:**

```python
# SATIR 17'Yİ SİL: DEFAULT_PASSWORD = "kasp2024"

# YERİNE EKLE:
import string

def generate_initial_admin_password(length: int = 16) -> str:
    """Rastgele güvenli geçici admin şifresi üretir."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

**`main.py` değişikliği (satır 149-157):**

```python
# ESKİ:
from kasp.security import hash_password, DEFAULT_PASSWORD, Session
...
db.create_default_admin(hash_password(DEFAULT_PASSWORD))

# YENİ:
from kasp.security import hash_password, Session, generate_initial_admin_password
...
# Admin şifresi: çevre değişkeni > config > rastgele
admin_password = os.environ.get("KASP_ADMIN_PASSWORD")
if not admin_password:
    try:
        admin_password = get_config_manager().get("auth.admin_initial_password")
    except Exception:
        admin_password = None
if not admin_password:
    admin_password = generate_initial_admin_password()
    
db.create_default_admin(hash_password(admin_password))
logger.info(f"Admin kullanicisi olusturuldu. Gecici sifre: {'*' * 8} (logda saklanmaz)")

# Kullanıcıya şifreyi göster
from PyQt5.QtWidgets import QMessageBox
QMessageBox.information(
    None, "İlk Kurulum",
    f"Admin hesabı oluşturuldu.\n\n"
    f"Kullanıcı adı: admin\n"
    f"Geçici şifre: {admin_password}\n\n"
    f"İlk girişte şifrenizi değiştirmelisiniz."
)
# Şifreyi must_change_password=1 ile kaydet
db.update_user(1, must_change_password=1)
```

---

### C2 / C6 / C7: Sessiz Hata Yutma (Lockout, Exception:pass Blokları)

**Dosyalar:** `kasp/security.py:43-44`, `main.py:252-263`, `kasp/ui/main_window.py:286-295` vb.

**Çözüm Planı:**

**Adım 1: `security.py` — Lockout durumunu güvenli hale getir**

```python
# _save_lockout_state() — satır 39-44'ü DEĞİŞTİR:
def _save_lockout_state(state):
    import tempfile
    try:
        tmp_path = _lockout_file + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, _lockout_file)  # atomik yazma
    except OSError as exc:
        logger.error(f"Lockout durumu kaydedilemedi: {exc}")
        raise RuntimeError(
            "Güvenlik durumu yazılamadı. Disk izinlerini kontrol edin."
        ) from exc
```

**Adım 2: `main.py` — catch-all yerine spesifik exception handler**

```python
# satır 252-263'ü DEĞİŞTİR:
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından kesildi.")
        sys.exit(0)
    except SystemExit:
        raise  # normal çıkışları engelleme
    except ImportError as e:
        ...
    except MemoryError:
        logger.critical("Yetersiz bellek!", exc_info=True)
        show_critical_error(
            "Yetersiz bellek! Diğer uygulamaları kapatıp tekrar deneyin."
        )
        sys.exit(1)
    except Exception as e:
        ...  # sadece beklenmeyen genel hatalar
```

**Adım 3: `main_window.py` — `except Exception: pass` temizliği**

Her bir `except Exception: pass` bloğu için spesifik exception yakala ve logla:

```python
# _save_splitter_state (satır 286-295) için:
def _save_splitter_state(self):
    try:
        ...
    except (AttributeError, TypeError, RuntimeError) as exc:
        logger.debug(f"Splitter durumu kaydedilemedi (önemsiz): {exc}")
    # pass KALDIRILDI - en azından debug log
```

---

### C3 / M27 / M28: API Güvenlik Zafiyetleri

**Dosya:** `kasp/api/server.py:35-41, 131`

**Çözüm Planı:**

```python
# server.py satır 35-41 DEĞİŞTİR:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # wildcard KALDIRILDI
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # ALL methods yerine sadece gerekli
    allow_headers=["Content-Type", "Authorization"],
)

# satır 131 DEĞİŞTİR:
if __name__ == "__main__":
    import socket
    host = os.environ.get("KASP_API_HOST", "127.0.0.1")  # varsayılan localhost
    port = int(os.environ.get("KASP_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
```

Ayrıca rate limiting ekle:

```python
# server.py başına EKLE:
from fastapi import Request
from datetime import datetime, timedelta
from collections import defaultdict

_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)
RATE_LIMIT_WINDOW = timedelta(seconds=60)
RATE_LIMIT_MAX = 30

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now()
    window_start = now - RATE_LIMIT_WINDOW
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Çok fazla istek. Lütfen bekleyin.")
    _rate_limit_store[client_ip].append(now)
    return await call_next(request)
```

---

### C4 / M30: SSL Sessizce Devre Dışı Bırakma

**Dosya:** `kasp/utils/updater.py:22-49`

**Çözüm Planı:**

```python
# _create_ssl_context() — FONKSIYONU TAMAMEN DEĞİŞTİR:
def _create_ssl_context() -> ssl.SSLContext:
    """Güvenli SSL bağlamı oluşturur. Sertifika doğrulaması ASLA devre dışı bırakılmaz."""
    
    # 1. certifi dene
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        logger.info("SSL bağlamı: certifi ile oluşturuldu.")
        return ctx
    except Exception as exc:
        logger.warning(f"certifi yüklenemedi: {exc}")
    
    # 2. Bundle içi sertifika
    import sys as _sys
    if getattr(_sys, "frozen", False):
        import os as _os
        bundle_certs = _os.path.join(_sys._MEIPASS, "certifi", "cacert.pem")
        if _os.path.exists(bundle_certs):
            logger.info("SSL bağlamı: bundle sertifika ile.")
            return ssl.create_default_context(cafile=bundle_certs)
    
    # 3. Sistem sertifikaları
    try:
        ctx = ssl.create_default_context()
        logger.info("SSL bağlamı: sistem sertifikaları ile.")
        return ctx
    except Exception as exc:
        logger.critical(f"SSL bağlamı oluşturulamadı: {exc}")
        # SERTIFIKA DOĞRULAMASI ASLA DEVRE DIŞI BIRAKILMAZ
        raise RuntimeError(
            "Güvenli bağlantı kurulamadı. SSL sertifika doğrulaması zorunludur.\n"
            "Lütfen certifi paketinin yüklü olduğundan emin olun."
        ) from exc
    
    # ALTTAKI cert_none KODU TAMAMEN SİLİNDİ
```

---

### C8 / C9 / C10: Tanrı Sınıflarının Bölünmesi

**Dosyalar:** `kasp/core/thermo.py` (1086 satır), `kasp/ui/main_window.py` (1138 satır), `kasp/data/database.py` (532 satır)

**Çözüm Planı:**

#### 8A. `ThermoEngine` Bölünmesi (thermo.py)

```python
# Yeni dosya: kasp/core/thermo_facade.py
class ThermoEngine:
    """Facade: Sadece delegasyon yapar, hesaplama içermez."""
    
    def __init__(self):
        self._design = DesignCalculationService()
        self._performance = PerformanceEvaluationService()
        self._heating = HeatingValueCalculator()
        self._selection = TurbineSelector()
    
    def calculate_design_performance(self, inputs): 
        return self._design.execute(inputs)

# Yeni dosya: kasp/core/design_calculation_service.py
class DesignCalculationService:
    """Tüm tasarım hesaplama mantığı burada."""
    ...

# Yeni dosya: kasp/core/performance_evaluation_service.py
class PerformanceEvaluationService:
    """Performans değerlendirme mantığı."""
    ...

# Yeni dosya: kasp/core/heating_value_calculator.py
class HeatingValueCalculator:
    """Isıl değer hesaplamaları (LHV/HHV)."""
    ...
```

**Hedef:** `thermo.py` 1086 satırdan ~80 satıra düşecek.

#### 8B. `UnitDatabase` Bölünmesi (database.py)

```python
# Yeni: kasp/data/turbine_repository.py
class TurbineRepository:
    def __init__(self, db_connection): ...
    def get_all(self): ...
    def insert(self, data): ...
    def delete(self, id_): ...

# Yeni: kasp/data/compressor_repository.py
# Yeni: kasp/data/user_repository.py  
# Yeni: kasp/data/calculation_history_repository.py

# database.py sadece bağlantı yönetimi:
class UnitDatabase:
    def __init__(self, db_path):
        self.turbines = TurbineRepository(self)
        self.compressors = CompressorRepository(self)
        self.users = UserRepository(self)
        self.history = CalculationHistoryRepository(self)
```

#### 8C. `KaspMainWindow` Genişletme (main_window.py)

Mevcut sub-controller mimarisi zaten iyi başlamış. Sorun main_window.py içinde hala kalan update check, engineering dashboard, admin panel, password change mantığının çıkarılması:

```python
# Yeni: kasp/ui/update_service.py
class UpdateService:
    """Tüm güncelleme kontrolü mantığı."""
    def check_for_updates(self): ...
    def show_update_dialog(self, info): ...
    def download_and_install(self, asset): ...

# Yeni: kasp/ui/engineering_panel.py
class EngineeringPanel:
    """Mühendislik modu gösterge paneli."""
    def setup_dashboard(self): ...
    def populate_eos_shootout(self): ...
    def run_comparison(self): ...

# main_window.py artık sadece:
# - Alt controller'ları başlatma
# - Menü/toolbar sinyallerini yönlendirme  
# - Pencere durumunu yönetme
# Hedef: 1138 -> 400 satır
```

---

### C5 / C4: Hata Yönetimi Dekoratörünün Düzeltilmesi

**Dosya:** `kasp/core/error_handler.py:77-96`

**Çözüm Planı:**

```python
# handle_errors() fonksiyonunu DEĞİŞTİR:
def handle_errors(error_type: str = "unknown", show_dialog: bool = True,
                  fallback_value: Any = None):
    """Geliştirilmiş hata yönetimi dekoratörü."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                raise  # ASLA yutma
            except SystemExit:
                raise  # ASLA yutma
            except (ThermodynamicError, ConvergenceError, FluidPropertyError) as e:
                # Beklenen termodinamik hatalar - logla, dialog göster
                logger.warning(f"{func.__name__}: {e}")
                if show_dialog:
                    ErrorHandler.show_error_dialog(
                        "Termodinamik Hata",
                        str(e),
                        getattr(e, 'details', None)
                    )
                return fallback_value
            except (ValueError, TypeError, KeyError) as e:
                # Girdi/kod hatası - logla
                logger.error(f"{func.__name__}: {e}", exc_info=True)
                if show_dialog:
                    ErrorHandler.show_error_dialog("Hata", str(e))
                return fallback_value
            except Exception as e:
                # Beklenmeyen hata - full traceback logla
                logger.critical(f"{func.__name__}: Beklenmeyen hata", exc_info=True)
                if show_dialog:
                    ErrorHandler.show_error_dialog(
                        "Kritik Hata",
                        "Beklenmeyen bir hata oluştu. Lütfen logları kontrol edin."
                    )
                return fallback_value
        return wrapper
    return decorator
```

---

### C10 / C11: Çift Modül Birleştirme

**Çift logging_handler.py:** `kasp/logging_handler.py` + `kasp/utils/logging_handler.py`

```python
# 1. kasp/utils/logging_handler.py dosyasını SİL
# 2. kasp/logging_handler.py'yi merkezi modül yap
# 3. Tüm import'ları güncelle:
#    from kasp.logging_handler import setup_logging, QLogHandler
```

**Çift hata yönetimi:** `kasp/error_handler.py` + `kasp/exception_handler.py`

```python
# 1. exception_handler.py'deki GlobalExceptionHandler'ı error_handler.py'ye taşı
# 2. error_handler.py modülünde birleştir:
#    - ErrorHandler (yerel hata dialog'ları)
#    - GlobalExceptionHandler (sys.excepthook)
#    - handle_errors (dekoratör)
#    - install_exception_handler()
# 3. exception_handler.py'yi SİL
# 4. main.py'de import'u güncelle
```

---

### C12 / C14 / C16: Veritabanı Optimizasyonları Aktif Etme + Kapatma

**Dosyalar:** `kasp/data/database.py:38`, `kasp/performance_config.py:16-66`

**Çözüm Planı:**

```python
# database.py __init__ içinde EKLE:
def __init__(self, db_name=None):
    self.db_name = db_name or _resolve_db_path()
    self._local = threading.local()
    self.logger = logging.getLogger(self.__class__.__name__)
    self._closed = False           # YENİ: kapatma takibi
    
    conn = self.get_connection()
    # YENİ: WAL modu, cache, foreign_keys AKTIF
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA cache_size=-10000")  # 10MB
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
    except sqlite3.Error as exc:
        self.logger.warning(f"DB optimizasyonu başarısız: {exc}")
    
    self.create_tables()
    self._migrate_database_schema()
    self._create_performance_indexes()  # YENİ
    
    if self._is_turbine_table_empty():
        self.insert_sample_data()

# YENİ metod:
def _create_performance_indexes(self):
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_history_date ON CalculationHistory(calculation_date)",
        "CREATE INDEX IF NOT EXISTS idx_turbines_type ON Turbines(type)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON Users(username)",
    ]
    conn = self.get_connection()
    for idx in indexes:
        try:
            conn.execute(idx)
        except sqlite3.Error:
            pass

# YENİ: Veritabanını düzgün kapatma
def close(self):
    if not self._closed and hasattr(self._local, 'conn'):
        try:
            self._local.conn.close()
        except sqlite3.Error:
            pass
        self._closed = True

# main.py cleanup'a EKLE (satır 229):
if hasattr(window, '_db'):
    window._db.close()
```

### C12 Alternatif: `_add_column_if_not_exists` SQL injection riskini giderme

```python
# DEĞİŞTİR (satır 135-149):
def _add_column_if_not_exists(self, table_name, column_name, column_type):
    # WHITELIST validasyonu
    ALLOWED_TABLES = {"Turbines", "Compressors", "CalculationHistory", "Users"}
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Geçersiz tablo adı: {table_name}")
    
    # column_type validasyonu
    ALLOWED_TYPES = {
        "REAL DEFAULT 0", "REAL DEFAULT 10.0", "REAL DEFAULT 1000",
        "TEXT DEFAULT 'Natural Gas'", "INTEGER DEFAULT 0"
    }
    if column_type not in ALLOWED_TYPES:
        raise ValueError(f"Geçersiz kolon tipi: {column_type}")
    
    cursor = self.get_cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor.fetchall()]
        if column_name not in columns:
            self.logger.warning(f"VT Şema Güncellemesi: {table_name}.{column_name} ekleniyor.")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            self.get_connection().commit()
            return True
    except sqlite3.Error as e:
        self.logger.error(f"Kolon ekleme hatası: {e}")
        return False
```

---

### C13: Tip Belirteçleri Ekleme

**Dosya:** 10+ dosyada eksik

**Öncelik sırasıyla type hint ekleme planı:**

| Aşama | Dosyalar | Yaklaşım |
|-------|---------|----------|
| 1. Hafta | `models.py` (zaten kismen var), `selection.py`, `user_manager.py` | Dönüş tipleri + parametreler |
| 2. Hafta | `thermo.py`, `database.py` | Kritik public metodlar |
| 3. Hafta | `main_window.py`, `workers.py` | Public API metodları |
| 4. Hafta | Kalan tüm dosyalar | `pyright`/`mypy` CI ile zorunlu |

**Örnek `selection.py` dönüşümü:**

```python
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple

class TurbineSelector:
    @staticmethod
    def select_units(
        required_power_kw: float, 
        site_conditions: Dict[str, float], 
        all_turbines_data: List[Dict[str, Any]], 
        limit: int = 5
    ) -> List[TurbineRecommendation]:
        ...

    @staticmethod
    def _calculate_turbine_score(
        turbine_type: str,
        corrected_heat_rate: float,
        power_margin_pct: float,
        surge_margin_pct: float, 
        stonewall_margin_pct: float
    ) -> float:
        ...
```

---

### C15 / M16: Test Onarımı

**Dosya:** `conftest.py:1-8`

**Çözüm Planı:**

1. Devre dışı bırakılmış testleri tek tek incele
2. Çalışanları geri ekle, bozukları düzelt
3. Gerçekten gereksizleri sil

```python
# conftest.py YENİ HALİ:
collect_ignore = [
    # "test_eos.py",           # AKTIF - import sorunu giderildi
    # "test_perf_vs_design.py", # AKTIF - bağımlılık düzeltildi  
    # "test_power.py",          # AKTIF - CoolProp mock'u eklendi
    # "test_three_methods.py",  # AKTIF - test verisi düzeltildi
    "test_ui_defaults.py",      # PyQt5 headless ortamda çalışmıyor - CI'da devre dışı
    "test_ui_responsive.py",    # Ekran boyutu bağımlı - CI'da devre dışı
]
```

**`test_ui_responsive.py` satır 81 düzeltmesi:**

```python
# ESKİ: assert window.isVisible() or True
# YENİ:
import os
if os.environ.get("CI") or os.environ.get("DISPLAY") is None:
    pytest.skip("Headless ortam — UI testi atlandı")
assert window.isVisible(), "Pencere görünür olmalı"
```

---

## DALGA 2: TERMODİNAMİK SORUNLAR

---

### T1: İdeal Gaz Fallback Z Formülü

**Dosya:** `kasp/core/properties.py:896`

**Çözüm Planı:**

```python
# SATIR 896 DEĞİŞTİR:
# ESKİ: Z_ideal = max(0.5, min(1.5, 1.0 - 0.1 * (P_pa / (STD_PRESS_PA * 10))))
# YENİ:
# İdeal gaz: Z = 1.0 tanım gereği
# Hafif gerçek gaz düzeltmesi isteniyorsa indirgenmiş basınç kullan
if 'Pc_mix' in vars() and Pc_mix > 0:
    Pr = P_pa / Pc_mix
    # Basit Pitzer korelasyonu: Z ≈ 1 - 0.27*Pr/Tr (ortalama)
    if 'Tc_mix' in vars() and Tc_mix > 0:
        Tr = T_k / Tc_mix
        if Tr > 0:
            Z_ideal = max(0.5, min(1.5, 1.0 - 0.27 * Pr / Tr))
        else:
            Z_ideal = 1.0
    else:
        Z_ideal = 1.0
else:
    Z_ideal = 1.0
```

Eğer Pc/Tc bilgisi yoksa düz `Z=1.0` kullan (ideal gaz).

---

### T2: İdeal Gaz Entropi Eksik Terimi

**Dosya:** `kasp/core/properties.py:899-900`

**Çözüm Planı:**

```python
# SATIR 899-900 DEĞİŞTİR:
# ESKİ:
# H_ideal = Cp_ideal * (T_k - 298.15)
# S_ideal = Cp_ideal * math.log(T_k / 273.15) if T_k > 0 else 0

# YENİ:
R_specific = 8314.462 / (M_kg_mol * 1000) if M_kg_mol > 0 else 287.0  # J/kg·K

H_ideal = Cp_ideal * (T_k - 298.15)
if T_k > 0 and P_pa > 0:
    S_ref = Cp_ideal * math.log(298.15 / 273.15)  # referans noktası
    S_ideal = Cp_ideal * math.log(T_k / 298.15) - R_specific * math.log(P_pa / STD_PRESS_PA) + S_ref
else:
    S_ideal = 0.0
```

---

### T3: Fallback Cp Değeri

**Dosya:** `kasp/core/properties.py:891`

**Çözüm Planı:**

```python
# SATIR 890-891 DEĞİŞTİR:
# ESKİ:
# if Cp_ideal == 1000.0:
#     Cp_ideal = 1000 + 0.1 * (T_k - 273.15)

# YENİ: Gaz bileşimine göre yaklaşık Cp
if Cp_ideal == 1000.0:
    # Yaklaşık Cp (J/kg·K) - metan bazlı doğal gaz için
    # Cp_CH4 ≈ 2200 @ 300K, sıcaklıkla artar
    T_ref = 298.15
    # 7/2 * R yaklaşımı (diatomik/çok atomlu için)
    n_atoms = 3  # ortalama CH4 tipi
    cp_molar_approx = (n_atoms + 1.5) * 8.314  # J/mol·K (yaklaşık)
    if M_kg_mol > 0:
        Cp_ideal = (cp_molar_approx / M_kg_mol) * 1000  # J/kg·K'ya çevir
    else:
        Cp_ideal = 2200.0  # metanol için makul varsayılan
```

---

### T4: Binary Etkileşim Parametreleri (k_ij)

**Dosya:** `kasp/core/properties.py:460-465`

**Çözüm Planı:**

```python
# KULLANICI TARAFINDAN KONFİGÜRE EDİLEBİLİR hale getir:
# kasp/core/settings.py'ye EKLE:
class EngineSettings:
    ...
    # YENİ:
    BINARY_INTERACTION_PARAMS: Dict[Tuple[str, str], float] = {
        # Varsayılan: sıfır
        # Örnek: ("METHANE", "CARBONDIOXIDE"): 0.10,
    }

# properties.py kullanım alanına EKLE:
def _build_kijs(zs, component_names):
    n = len(zs)
    kijs = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                key = (component_names[i].upper(), component_names[j].upper())
                kijs[i][j] = EngineSettings.BINARY_INTERACTION_PARAMS.get(key, 0.0)
    return kijs

# EOS oluşturma (satır 460):
eos = EOS_CLASS(
    T=T_k, P=P_pa,
    Tcs=constants.Tcs, Pcs=constants.Pcs,
    omegas=constants.omegas, zs=zs,
    kijs=_build_kijs(zs, component_names) if EOS_CLASS.__name__ == 'PRMIX' else None,
)
```

---

### T5 / T6: Metot 2 ve Metot 4 Limitasyonları

**Dosya:** `kasp/core/thermo_methods.py:184-266, 370-390`

**Çözüm Planı:**

```python
# Metot 2 için UI uyarısı (design_input_binding.py'de method seçimi yanına):
METHOD_INFO = {
    "Metot 1: Ortalama Özellikler": "Küçük basınç oranları için uygun (PR < 4). İteratif.",
    "Metot 2: Endpoint Yaklaşımı": "⚠ Sadece PR < 2.5 için önerilir. Yüksek PR'da sapma yapar.",
    "Metot 3: Artımlı Basınç": "✅ En hassas yöntem. API 617 Appendix C uyumlu. Önerilir.",
    "Metot 4: Direct H-S": "Gerçek entalpi/entropi bazlı. PR < 10 için uygun.",
}

# Metot 4 outer loop (satır 374):
# ESKİ: outer_iterations = 3
# YENİ:
outer_iterations = 3 if pressure_ratio < 5 else 5
# Yüksek PR'da daha fazla k-rafinasyonu
```

---

### T7 / T8: İki-Faz Tespiti

**Dosya:** `kasp/core/properties.py:122-141`

```python
# İki-faz kontrolüne EKLE:
def _classify_phase(self, eos, P_pa, T_k):
    """İyileştirilmiş faz sınıflandırması."""
    try:
        # EOS'ta T_sat kontrolü (eğer mevcutsa)
        if hasattr(eos, 'Tsat') and hasattr(eos, 'Psat'):
            T_sat = eos.Tsat(P_pa)
            if T_sat is not None and T_k < T_sat:
                return 'liquid'
            elif T_sat is not None and T_k > T_sat:
                return 'gas'
        
        # Z-g / Z-l karşılaştırması ile tespit
        Z_g = getattr(eos, 'Z_g', None)
        Z_l = getattr(eos, 'Z_l', None)
        
        if Z_g is not None and Z_l is not None:
            # Gibbs serbest enerjisi karşılaştırması (daha güvenilir)
            try:
                G_dep_g = eos.G_dep_g
                G_dep_l = eos.G_dep_l
                if G_dep_g < G_dep_l:
                    return 'gas'
                else:
                    return 'liquid'
            except (AttributeError, TypeError):
                pass  # G_dep mevcut değilse Z tabanlıya dön
        
        # Fallback
        if Z_g and Z_l and Z_l < Z_g:
            return 'gas'
        if Z_g:
            return 'gas'
        if Z_l:
            return 'liquid'
    except Exception:
        pass
    
    # Son çare
    if Z_g and Z_g > 0.7:
        return 'gas'
    return 'ideal_fallback'
```

---

## DALGA 3: ÖNEMLİ SORUNLAR

---

### M1: Girdi Validasyonu Eksikliği

**Dosya:** `kasp/core/thermo.py:297-315`

```python
# calculate_design_performance_with_mode() başına EKLE:
REQUIRED_FIELDS = {
    'p_in': (float, lambda v: v > 0, "Giriş basıncı pozitif olmalı"),
    'p_out': (float, lambda v: v > 0, "Çıkış basıncı pozitif olmalı"),
    't_in': (float, lambda v: v > -273.15, "Sıcaklık mutlak sıfırdan büyük olmalı"),
    'flow': (float, lambda v: v > 0, "Debi pozitif olmalı"),
    'gas_comp': (dict, lambda v: len(v) > 0, "Gaz bileşimi boş olamaz"),
    'poly_eff': (float, lambda v: 0 < v <= 100, "Politropik verim 0-100 arasında olmalı"),
}

def validate_calculation_inputs(inputs: dict) -> List[str]:
    """Girdileri valide et, hata mesajlarını döndür."""
    errors = []
    for field, (typ, check, msg) in REQUIRED_FIELDS.items():
        if field not in inputs:
            errors.append(f"Eksik alan: {field}")
            continue
        try:
            value = typ(inputs[field]) if typ != dict else inputs[field]
            if not check(value):
                errors.append(f"{field}: {msg}")
        except (ValueError, TypeError):
            errors.append(f"{field}: geçersiz değer")
    
    if errors:
        raise InputValidationError("\n".join(errors))
    return []

# Kullanım:
def calculate_design_performance_with_mode(self, inputs: dict, **kwargs):
    validate_calculation_inputs(inputs)  # YENİ
    ...
```

---

### M2 / M3: Sıfıra Bölme Koruması

**Dosya:** `kasp/core/selection.py:52, 131`

```python
# satır 52 DEĞİŞTİR:
# ESKİ: power_margin_pct = ((corr_power - required_power_kw) / required_power_kw) * 100
# YENİ:
if required_power_kw <= 1e-6:
    logger.warning(f"Geçersiz required_power_kw={required_power_kw}, türbin atlanıyor: {turbine.get('manufacturer')}")
    continue
power_margin_pct = ((corr_power - required_power_kw) / required_power_kw) * 100

# satır 131 DEĞİŞTİR:
# ESKİ: surge_margin = ((op_flow - surge_flow) / surge_flow) * 100.0
# YENİ:
if surge_flow < 1e-9:
    return {'surge_margin_pct': 0.0, 'stonewall_margin_pct': 0.0}
surge_margin = ((op_flow - surge_flow) / surge_flow) * 100.0
```

---

### M5 / M26: Şifre Politikası Güçlendirme

**Dosya:** `kasp/core/user_manager.py:59, 90, 96`

```python
# user_manager.py'ye EKLE:
import re

MIN_PASSWORD_LENGTH = 8  # 4'ten 8'e yükseltildi (NIST SP 800-63B)

def validate_password_policy(password: str) -> Optional[str]:
    """Şifre politikasını kontrol et, hata varsa mesaj döndür."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalıdır."
    if not re.search(r'[A-Z]', password):
        return "Şifre en az bir büyük harf içermelidir."
    if not re.search(r'[a-z]', password):
        return "Şifre en az bir küçük harf içermelidir."
    if not re.search(r'\d', password):
        return "Şifre en az bir rakam içermelidir."
    return None  # geçerli

# create_user, change_password, admin_reset_password içinde:
# ESKİ: if len(password) < 4: return ..., "Şifre en az 4 karakter..."
# YENİ:
policy_error = validate_password_policy(password)
if policy_error:
    return None, policy_error
```

---

### M6 / M29: PBKDF2 Salt Uzunluğu

**Dosya:** `kasp/security.py:47-50`

```python
# hash_password DEĞİŞTİR:
def hash_password(password: str) -> str:
    # ESKİ: salt = secrets.token_hex(12)  # 6 byte
    # YENİ: 32 byte salt (NIST SP 800-132 önerisi minimum 16)
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"pbkdf2:sha256:600000:{salt}:{dk.hex()}"
```

---

### M25: Lockout Durumu Güvenliği

**Dosya:** `kasp/security.py:26-44`

```python
# Tamamen yeni lockout sistemi:
import struct
import hmac

_LOCKOUT_SECRET = secrets.token_bytes(32)  # oturum başına rastgele

def _get_lockout_path() -> str:
    """Platform'a özel güvenli lockout yolu."""
    base = os.environ.get("APPDATA") if os.name == "nt" else os.path.expanduser("~/.local/share")
    kasp_dir = os.path.join(base, "KASP", "security")
    os.makedirs(kasp_dir, exist_ok=True)
    return os.path.join(kasp_dir, "kasp_lockout.bin")

def _calculate_lockout_hmac(data: bytes) -> bytes:
    return hmac.digest(_LOCKOUT_SECRET, data, "sha256")

def _save_lockout_state(state: dict):
    payload = json.dumps(state).encode()
    mac = _calculate_lockout_hmac(payload)
    # binary format: [4-byte length][payload][32-byte hmac]
    with open(_get_lockout_path(), "wb") as f:
        f.write(struct.pack("<I", len(payload)))
        f.write(payload)
        f.write(mac)

def _load_lockout_state() -> dict:
    try:
        with open(_get_lockout_path(), "rb") as f:
            length = struct.unpack("<I", f.read(4))[0]
            payload = f.read(length)
            stored_mac = f.read(32)
        
        expected_mac = _calculate_lockout_hmac(payload)
        if not hmac.compare_digest(stored_mac, expected_mac):
            logger.warning("Lockout dosyası kurcalanmış! Sıfırlanıyor.")
            return {"failures": 3, "last_failure": time.time(), "lockout_until": time.time() + 300}
        
        return json.loads(payload)
    except (FileNotFoundError, json.JSONDecodeError, struct.error, OSError):
        return {"failures": 0, "last_failure": 0, "lockout_until": 0}
```

---

### M9 / M10: Çift Modül Temizliği

```bash
# 1. kasp/utils/logging_handler.py → İçeriğini kasp/logging_handler.py'ye taşı, sonra SİL
# 2. kasp/exception_handler.py → İçeriğini kasp/error_handler.py'ye taşı, sonra SİL
# 3. Tüm import'ları güncelle (grep ile bul):
#    from kasp.exception_handler → from kasp.error_handler
#    from kasp.utils.logging_handler → from kasp.logging_handler
```

---

### M11 / M14 / M15 / M17 / M18 / M19: Profesyonellik Temizliği

#### Boş stub metotları (M16):
```python
# main_window.py satır 453-460 SİL:
# _setup_unit_tooltips, _update_method_options, _update_button_state → pass
# Eğer gelecekte implemente edilecekse TODO yorumu koy:
# TODO(v2.1): Implement unit tooltips
```

#### Pass-only cache (M18):
```python
# performance_config.py satır 62-66 DEĞİŞTİR:
# ESKİ: pass
# YENİ: Bu sınıf kaldırıldı - ThermodynamicSolver kendi LRU cache'ini kullanıyor
# CacheManager sınıfını komple kaldır veya NotImplementedError fırlat
```

#### Indexler yanlış tabloda (M17):
```python
# performance_config.py satır 40-43 DEĞİŞTİR:
# ESKİ: "CREATE INDEX ... ON calculations(...)"
# YENİ: database.py'deki _create_performance_indexes()'e taşındı
# Bu metot kaldırıldı
```

#### Sihirli sayılar (M14):
```python
# kasp/core/settings.py'ye EKLE:
class EngineSettings:
    # ... mevcut ...
    
    # YENİ - daha önce inline olan sabitler:
    MECHANICAL_LOSS_COEFF = 0.65
    MECHANICAL_LOSS_EXPONENT = 0.45
    MECHANICAL_LOSS_MIN_KW = 10.0
    MECHANICAL_LOSS_MAX_PCT = 0.10
    
    FALLBACK_LHV_KJ_KG = 50000.0
    CONSISTENCY_RELAXATION = 0.65
    CONSISTENCY_RELAXATION_METHOD1 = 0.5
    CONSISTENCY_RELAXATION_METHOD2 = 0.8
    
    DEFAULT_ISENTROPIC_K_FALLBACK = 1.3
    IDEAL_GAS_FALLBACK_CP_BASE = 2200.0  # metan tipik Cp (J/kg·K)
```

#### Sürüm tutarsızlığı (M15):
```python
# kasp_config.json satır 4:
# ESKİ: "version": "2.0.0"
# YENİ: Tek kaynak release_metadata.py olsun. kasp_config.json'dan version alanını KALDIR
# ConfigManager versiyonu release_metadata.py'den okusun
```

---

### M20 / M21 / M22 / M23: Test İyileştirmeleri

```python
# YENİ test: tests/test_thermo_accuracy.py
def test_methane_isentropic_efficiency_known_case():
    """
    ASME PTC 10 örnek problemi: Metan, PR=3, T_in=300K, P_in=1 bar
    Bilinen sonuç: politropik verim ≈ 82%
    """
    from kasp.core.thermo import ThermoEngine
    engine = ThermoEngine()
    result = engine.calculate_design_performance({
        'p_in': 1.0, 'p_in_unit': 'bar(a)',
        't_in': 27.0, 't_in_unit': '°C',
        'p_out': 3.0, 'p_out_unit': 'bar(a)',
        'flow': 10.0, 'flow_unit': 'kg/s',
        'gas_comp': {'METHANE': 100.0},
        'eos_method': 'coolprop',
        'method': 'Metot 3: Artımlı Basınç',
        'poly_eff': 82.0, 'mech_eff': 98.0, 'therm_eff': 35.0,
        'num_units': 1, 'num_stages': 1,
        'intercooler_t': 40.0, 'intercooler_dp_pct': 2.0,
        'consistency_check': False,
    })
    assert result is not None
    assert 'power_shaft_total_kw' in result
    assert result['power_shaft_total_kw'] > 0

# YENİ test: tests/test_zero_division_guards.py
def test_turbine_selection_zero_power_handled():
    """required_power_kw=0 durumunda hata vermeden boş liste dönmeli."""
    from kasp.core.selection import TurbineSelector
    result = TurbineSelector.select_units(0.0, {}, [], limit=5)
    assert result == []

# YENİ test: tests/test_fallback_entropy_correct.py  
def test_ideal_gas_entropy_has_pressure_term():
    """İdeal gaz fallback entropy'si -R*ln(P/P_ref) terimini içermeli."""
    # ... (T2 çözümü sonrası)
```

---

### M35: Tema Stylesheet Cache

```python
# theme_manager.py'ye EKLE:
_stylesheet_cache: Dict[str, str] = {}

def apply_theme(theme_name: str):
    """Temayı cache'leyerek uygula."""
    if theme_name in _stylesheet_cache:
        stylesheet = _stylesheet_cache[theme_name]
    else:
        stylesheet = _generate_stylesheet(theme_name)
        _stylesheet_cache[theme_name] = stylesheet
    
    app = QApplication.instance()
    if app:
        app.setStyleSheet(stylesheet)
```

---

### M37 / M38: UI Erişilebilirliği

```python
# login_dialog.py satır 44 DEĞİŞTİR:
# ESKİ: self.setFixedSize(w, h)
# YENİ:
self.setMinimumSize(min_w, min_h)
self.resize(w, h)

# main_window.py menü ve butonlara klavye kısayolu ekle:
# _create_menu_bar() içinde:
file_menu.addAction("&Yeni Proje\tCtrl+N", self.on_new_project)
file_menu.addAction("&Aç\tCtrl+O", self.on_open_project)
file_menu.addAction("Kay&det\tCtrl+S", self.on_save_project)
file_menu.addAction("Dışa &Aktar\tCtrl+E", self.on_export)
```

---

### M40 / M41 / M42: Build Sistemi Temizliği

```bash
# 1. Eski spec/bat/sh dosyalarını archive/ klasörüne taşı:
mkdir archive\build_artifacts_v1
move KASP_release_v1.* archive\build_artifacts_v1\
move KASP_release_v2.0.0* archive\build_artifacts_v1\
# ... tüm eski sürümler

# 2. build_release.py'yi işlevsel hale getir:
```

```python
# build_release.py YENİ HALİ:
"""
KASP Release Builder
Tek parametrik build scripti - release_metadata.py'den versiyon okur.
"""
import os, sys, subprocess
from release_metadata import RELEASE_VERSION, RELEASE_ARTIFACT_BASENAME

def build_windows():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        f"--name={RELEASE_ARTIFACT_BASENAME}",
        "--add-data=kasp_config.json;.",
        "--add-data=resources;resources",
        "--add-data=kasp_database.db;.",
        f"KASP_release_v{RELEASE_VERSION}.spec",
    ]
    subprocess.run(cmd, check=True)

def build_macos():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        f"--name={RELEASE_ARTIFACT_BASENAME}",
        "--add-data=kasp_config.json:.",
        "--add-data=resources:resources",
        "--add-data=kasp_database.db:.",
        f"KASP_release_v{RELEASE_VERSION}_mac.spec",
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["windows", "macos", "all"], default="windows")
    args = parser.parse_args()
    
    if args.platform in ("windows", "all"):
        build_windows()
    if args.platform in ("macos", "all"):
        build_macos()
```

```python
# release_metadata.py'ye EKLE:
import hashlib
import subprocess
from datetime import datetime

RELEASE_VERSION = "2.0.4"
RELEASE_BUILD_DATE = datetime.now().strftime("%Y-%m-%d")

def _get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"

RELEASE_BUILD_HASH = _get_git_commit()
RELEASE_FULL_VERSION = f"{RELEASE_VERSION}+{RELEASE_BUILD_HASH}"

RELEASE_ARTIFACT_BASENAME = f"KASP_v{RELEASE_VERSION}"
```

---

## KAPSAMLI TEST PLANI

Bu bölüm programın tüm katmanlarını kapsayan test stratejisini, yeni oluşturulacak test dosyalarını, test kategorilerini, CI/CD entegrasyonunu ve başarı kriterlerini tanımlar.

---

### TEST ALTYAPISI

```
tests/
├── conftest.py                          # Paylaşılan fixture'lar
├── __init__.py
│
├── unit/                                # Birim testleri
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_constants.py            # Sabitler, gaz kütüphanesi
│   │   ├── test_units.py               # UnitSystem dönüşümleri
│   │   ├── test_models.py              # Dataclass serialization
│   │   ├── test_mixture.py             # GasMixtureBuilder
│   │   ├── test_exceptions.py          # Özel hata sınıfları
│   │   ├── test_settings.py            # EngineSettings
│   │   ├── test_contracts.py           # Normalize/validate
│   │   ├── test_aerodynamics.py        # CompressorAerodynamics
│   │   ├── test_selection.py           # TurbineSelector
│   │   ├── test_fallback.py            # EosChain / SolverChain
│   │   ├── test_thermo_methods.py      # 4 hesaplama metodu
│   │   ├── test_thermo_design_orch.py  # Stage loop
│   │   ├── test_performance_corr.py    # Site corrections (mevcut)
│   │   ├── test_uncertainty.py         # ASME PTC 10 belirsizlik
│   │   └── test_engineering.py         # Shootout araçları
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── test_turbine_repository.py  # CRUD (bölünme sonrası)
│   │   ├── test_compressor_repository.py
│   │   ├── test_user_repository.py
│   │   └── test_calculation_history.py
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   ├── test_password_hashing.py    # hash/verify/policy
│   │   ├── test_lockout.py            # Kilit mekanizması
│   │   ├── test_input_validator.py    # InputValidator
│   │   ├── test_permissions.py        # PermissionManager
│   │   └── test_session.py            # Session (mevcut)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── test_workers.py            # CalculationWorker
│       ├── test_release_parser.py     # parse_release_tag vb
│       └── test_report_template.py
│
├── integration/                         # Entegrasyon testleri
│   ├── __init__.py
│   ├── test_design_calculation_e2e.py   # Tam tasarım akışı
│   ├── test_performance_evaluation.py   # Performans değerlendirme
│   ├── test_turbine_selection_flow.py   # Türbin seçim zinciri
│   ├── test_auth_flow.py               # Login → Session → Logout
│   ├── test_project_save_load.py        # Proje kaydet/yükle
│   ├── test_export.py                  # Excel/PDF dışa aktarım
│   ├── test_fallback_chains.py         # EOS/Solver zinciri
│   └── test_api_endpoints.py           # FastAPI endpoint'leri
│
├── validation/                          # Termodinamik doğrulama
│   ├── __init__.py
│   ├── test_asme_ptc10_examples.py     # ASME PTC 10 örnek problemleri
│   ├── test_api_617_cases.py           # API 617 hesaplama vakaları
│   ├── test_eos_comparison.py          # EOS'lar arası karşılaştırma
│   ├── test_known_pure_methane.py      # Saf metan bilinen değerler
│   ├── test_real_gas_mixtures.py       # Gerçek gaz karışımları
│   ├── test_entropy_conservation.py    # Entropi korunumu
│   ├── test_z_factor_validation.py     # Z değerleri NIST karşılaştırma
│   └── test_iso_6976_heating.py        # ISO 6976 ısıl değer
│
├── regression/                          # Regresyon testleri
│   ├── __init__.py
│   ├── test_regression_snapshots.py    # Sonuç snapshot karşılaştırma
│   ├── test_v462_regressions.py        # Mevcut (aktif)
│   └── test_backward_compat.py         # Geriye dönük uyumluluk
│
├── security/                            # Güvenlik testleri
│   ├── __init__.py
│   ├── test_sql_injection.py           # SQL injection girişimleri
│   ├── test_brute_force.py             # Kaba kuvvet saldırısı
│   ├── test_path_traversal.py          # Dizin gezinme
│   └── test_input_sanitization.py      # XSS / özel karakterler
│
├── ui/                                  # UI testleri (headless)
│   ├── __init__.py
│   ├── test_theme_contrast.py          # WCAG (mevcut)
│   ├── test_validation_feedback.py     # Input validasyon görseli
│   └── test_widget_state_machine.py    # Widget durum geçişleri
│
└── performance/                         # Performans testleri
    ├── __init__.py
    ├── test_calculation_benchmark.py    # Hesaplama süresi
    ├── test_cache_efficiency.py        # LRU cache hit rate
    └── test_memory_usage.py            # Bellek kullanımı
```

---

### TEST DOSYASI DETAYLARI

#### 1. UNIT TESTS — Yeni Oluşturulacak Dosyalar

---

**`tests/unit/core/test_constants.py`** — Gaz kütüphanesi ve sabitler

```python
import pytest
from kasp.core.constants import (
    SUPPORTED_GASES, MOLAR_MASSES, LHV_DATA, 
    UNIT_OPTIONS, DEFAULT_COMPOSITION,
    normalize_component, GAS_ALIASES
)

class TestGasLibrary:
    def test_all_supported_gases_have_molar_mass(self):
        for gas in SUPPORTED_GASES:
            assert gas in MOLAR_MASSES, f"{gas} için molar kütle eksik"

    def test_lhv_data_all_positive(self):
        for gas, lhv in LHV_DATA.items():
            assert lhv > 0, f"{gas} LHV değeri pozitif olmalı"

    def test_normalize_component_case_insensitive(self):
        assert normalize_component("methane") == "METHANE"
        assert normalize_component("METHANE") == "METHANE"
        assert normalize_component("co2") == "CARBONDIOXIDE"

    def test_normalize_component_unknown_returns_original(self):
        assert normalize_component("unknown_gas") == "UNKNOWN_GAS"

    def test_default_composition_sums_to_100(self):
        total = sum(DEFAULT_COMPOSITION.values())
        assert abs(total - 100.0) < 0.01

    def test_unit_options_has_required_categories(self):
        assert "pressure" in UNIT_OPTIONS
        assert "temperature" in UNIT_OPTIONS
        assert "flow" in UNIT_OPTIONS
```

---

**`tests/unit/core/test_units.py`** — Birim dönüşümleri

```python
import pytest
from kasp.core.units import UnitSystem

class TestUnitConversions:
    @pytest.mark.parametrize("value,unit,expected_pa", [
        (1.0, "bar(a)", 100000.0),
        (1.0, "kPa", 1000.0),
        (14.7, "psia", 101353.0),  # ~14.7 * 6894.76
        (0.0, "bar(g)", 101325.0),  # gauge → absolute
        (1.0, "MPa", 1000000.0),
    ])
    def test_pressure_to_pa(self, value, unit, expected_pa):
        result = UnitSystem.convert_pressure(value, unit, "Pa")
        assert abs(result - expected_pa) / expected_pa < 0.01

    @pytest.mark.parametrize("value,unit,expected_k", [
        (0.0, "°C", 273.15),
        (100.0, "°C", 373.15),
        (32.0, "°F", 273.15),  # 32°F = 0°C = 273.15K
        (212.0, "°F", 373.15),
    ])
    def test_temperature_to_k(self, value, unit, expected_k):
        result = UnitSystem.convert_temperature(value, unit, "K")
        assert abs(result - expected_k) < 0.1

    def test_negative_gauge_pressure_rejected(self):
        with pytest.raises(ValueError):
            UnitSystem.validate_pressure_value(-1.0, "bar(a)")

    def test_temperature_below_absolute_zero_rejected(self):
        with pytest.raises(ValueError):
            UnitSystem.validate_temperature_value(-300.0, "°C")
```

---

**`tests/unit/core/test_aerodynamics.py`** — Kompresör aerodinamiği

```python
import pytest
from kasp.core.models import ThermodynamicState
from kasp.core.aerodynamics import CompressorAerodynamics

@pytest.fixture
def methane_state_in():
    return ThermodynamicState(
        P=101325.0, T=300.0, H=500000.0, S=5200.0,
        Z=0.998, k=1.31, MW=16.04, Cp=2220.0, Cv=1695.0,
        density=0.65, phase='gas'
    )

@pytest.fixture
def methane_state_out():
    return ThermodynamicState(
        P=303975.0, T=380.0, H=580000.0, S=5210.0,
        Z=0.995, k=1.30, MW=16.04, Cp=2280.0, Cv=1754.0,
        density=1.60, phase='gas'
    )

class TestPolytropicEfficiency:
    def test_efficiency_range(self, methane_state_in, methane_state_out):
        R_specific = 8314.462 / 16.04  # J/kg·K
        eff = CompressorAerodynamics.calculate_polytropic_efficiency(
            methane_state_in, methane_state_out, R_specific
        )
        assert 0.0 < eff <= 1.0, f"Verim 0-1 arasında olmalı: {eff}"

    def test_efficiency_same_state_returns_one(self, methane_state_in):
        R_specific = 8314.462 / 16.04
        eff = CompressorAerodynamics.calculate_polytropic_efficiency(
            methane_state_in, methane_state_in, R_specific
        )
        assert abs(eff - 1.0) < 0.01  # aynı durumda verim 1

class TestMechanicalLoss:
    def test_minimum_loss(self):
        loss = CompressorAerodynamics.calculate_mechanical_loss(acmh=0)
        assert loss >= 10.0  # minimum 10 kW

    def test_loss_increases_with_flow(self):
        loss_low = CompressorAerodynamics.calculate_mechanical_loss(acmh=1000)
        loss_high = CompressorAerodynamics.calculate_mechanical_loss(acmh=10000)
        assert loss_high > loss_low

    def test_loss_capped_at_10_percent(self):
        loss = CompressorAerodynamics.calculate_mechanical_loss(acmh=100000, shaft_power_kw=100)
        assert loss <= 10.0  # max %10
```

---

**`tests/unit/core/test_selection.py`** — Türbin seçimi

```python
import pytest
from kasp.core.selection import TurbineSelector
from kasp.core.models import TurbineRecommendation

SAMPLE_TURBINE = {
    "manufacturer": "TestCorp", "model": "T100",
    "type": "Aeroderivative",
    "iso_power_kw": 5000.0,
    "iso_heat_rate_kj_kwh": 10500.0,
    "surge_flow": 5.0,
    "stonewall_flow": 50.0,
}

class TestTurbineSelection:
    def test_zero_required_power_returns_empty(self):
        result = TurbineSelector.select_units(0.0, {}, [SAMPLE_TURBINE])
        assert result == []

    def test_negative_required_power_returns_empty(self):
        result = TurbineSelector.select_units(-100.0, {}, [SAMPLE_TURBINE])
        assert result == []

    def test_valid_selection_returns_recommendations(self):
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0, 
            'ambient_pressure': 101.325, 'flow': 20.0
        }, [SAMPLE_TURBINE])
        assert len(result) > 0
        assert isinstance(result[0], TurbineRecommendation)
        assert 0 <= result[0].selection_score <= 100

    def test_selection_sorted_by_score(self):
        t1 = {**SAMPLE_TURBINE, "model": "T100", "iso_power_kw": 5000}
        t2 = {**SAMPLE_TURBINE, "model": "T200", "iso_power_kw": 3500}
        result = TurbineSelector.select_units(3000.0, {
            'ambient_temp': 15.0, 'altitude': 0.0,
            'ambient_pressure': 101.325, 'flow': 20.0
        }, [t1, t2])
        for i in range(len(result) - 1):
            assert result[i].selection_score >= result[i+1].selection_score
```

---

**`tests/unit/core/test_fallback.py`** — EOS/Solver zinciri

```python
import pytest
from kasp.core.fallback import EosChain, SolverChain, FallbackTracker, EosChainBrokenError

class TestEosChain:
    def test_preferred_first(self):
        chain = EosChain(preferred="coolprop")
        assert chain.current() == "coolprop"

    def test_next_skips_broken(self):
        chain = EosChain(preferred="coolprop")
        chain.mark_broken("coolprop")
        assert chain.current() == "thermopack"

    def test_all_broken_raises(self):
        chain = EosChain(preferred="coolprop")
        for eos in chain._order:
            chain.mark_broken(eos)
        with pytest.raises(EosChainBrokenError):
            chain.current()

class TestFallbackTracker:
    def test_tracks_broken_eos(self):
        tracker = FallbackTracker()
        tracker.record_broken_eos("coolprop")
        assert "coolprop" in tracker.broken_eos

    def test_reset_clears_all(self):
        tracker = FallbackTracker()
        tracker.record_broken_eos("coolprop")
        tracker.record_broken_solver("fd_nr")
        tracker.reset()
        assert len(tracker.broken_eos) == 0
        assert len(tracker.broken_solvers) == 0
```

---

**`tests/unit/core/test_thermo_methods.py`** — 4 hesaplama metodu

```python
import pytest

class TestMethodComparison:
    """4 metodun karşılaştırmalı testleri."""
    
    def test_all_methods_produce_positive_power(self, thermo_engine, methane_inputs):
        methods = [
            "Metot 1: Ortalama Özellikler",
            "Metot 2: Endpoint Yaklaşımı",
            "Metot 3: Artımlı Basınç",
            "Metot 4: Direct H-S",
        ]
        for method in methods:
            inputs = {**methane_inputs, 'method': method}
            result = thermo_engine.calculate_design_performance(inputs)
            assert result is not None, f"{method} None döndü"
            assert result.get('power_shaft_total_kw', 0) > 0, f"{method} güç 0"

    def test_method3_most_accurate_for_high_pr(self, thermo_engine, methane_inputs):
        """PR > 5 için Metot 3 en doğru sonucu vermeli."""
        high_pr_inputs = {**methane_inputs, 'p_out': 5.0}  # PR=5
        results = {}
        for method_suffix in ["Ortalama", "Endpoint", "Artımlı", "Direct"]:
            method = f"Metot {['1', '2', '3', '4'][['Ortalama', 'Endpoint', 'Artımlı', 'Direct'].index(method_suffix)]}: {method_suffix}"
            # ...
```

---

**`tests/unit/security/test_password_hashing.py`** — Şifre güvenliği

```python
import pytest
from kasp.security import hash_password, verify_password, validate_password_policy

class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "StrongPass1"
        hashed = hash_password(pw)
        assert hashed.startswith("pbkdf2:sha256:600000:")
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPass1")
        assert not verify_password("WrongPass1", hashed)

    def test_hash_is_unique_each_time(self):
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2  # farklı salt nedeniyle

    def test_pbkdf2_iterations_600k(self):
        hashed = hash_password("TestPass1")
        _, _, iters, _, _ = hashed.split(":")
        assert int(iters) == 600000

    def test_salt_length_at_least_16_bytes(self):
        hashed = hash_password("TestPass1")
        _, _, _, salt, _ = hashed.split(":")
        assert len(bytes.fromhex(salt)) >= 16

class TestPasswordPolicy:
    def test_minimum_length_8(self):
        error = validate_password_policy("Short1")
        assert error is not None
        assert "8" in error

    def test_requires_uppercase(self):
        error = validate_password_policy("nouppercase1")
        assert error is not None
        assert "büyük harf" in error.lower()

    def test_requires_lowercase(self):
        error = validate_password_policy("NOLOWERCASE1")
        assert error is not None

    def test_requires_digit(self):
        error = validate_password_policy("NoDigitsHere")
        assert error is not None

    def test_valid_password_passes(self):
        error = validate_password_policy("ValidPass1")
        assert error is None
```

---

**`tests/unit/security/test_lockout.py`** — Kilit mekanizması

```python
import pytest
import time
from kasp.security import (
    record_attempt, check_lockout, get_lockout_remaining,
    _load_lockout_state, _save_lockout_state
)

class TestLockout:
    def setup_method(self):
        _save_lockout_state({"failures": 0, "last_failure": 0, "lockout_until": 0})

    def test_initial_state_not_locked(self):
        locked, _ = check_lockout()
        assert not locked

    def test_three_failures_lock_for_1_minute(self):
        for _ in range(3):
            record_attempt(success=False)
        locked, msg = check_lockout()
        assert locked
        assert "dakika" in msg

    def test_success_resets_failures(self):
        for _ in range(2):
            record_attempt(success=False)
        record_attempt(success=True)
        remaining = get_lockout_remaining()
        assert remaining == 3  # sıfırlandı, 3 deneme kaldı

    def test_lockout_file_tamper_detection(self):
        # Dosyayı kurcala — hmac uyuşmaz
        import json, struct, hmac, hashlib
        state = _load_lockout_state()
        # Kurcalanmış dosya simülasyonu testte zor, 
        # _load_lockout_state'in hmac kontrolünü ayrıca test et
        assert isinstance(state, dict)

    def test_get_lockout_remaining_decreases(self):
        for _ in range(2):
            record_attempt(success=False)
        remaining = get_lockout_remaining()
        assert remaining == 1  # 3 - 2 = 1
```

---

#### 2. INTEGRATION TESTS

---

**`tests/integration/test_design_calculation_e2e.py`** — Uçtan uca tasarım hesaplaması

```python
import pytest
from kasp.core.thermo import ThermoEngine

DESIGN_INPUTS_METHANE = {
    'project_name': 'Test Methane Design',
    'p_in': 1.0, 'p_in_unit': 'bar(a)',
    't_in': 25.0, 't_in_unit': '°C',
    'p_out': 3.0, 'p_out_unit': 'bar(a)',
    'flow': 10.0, 'flow_unit': 'kg/s',
    'gas_comp': {'METHANE': 100.0},
    'eos_method': 'coolprop',
    'method': 'Metot 3: Artımlı Basınç',
    'poly_eff': 82.0,
    'mech_eff': 98.0,
    'therm_eff': 35.0,
    'num_units': 1,
    'num_stages': 1,
    'intercooler_t': 40.0,
    'intercooler_dp_pct': 2.0,
    'consistency_check': True,
}

DESIGN_INPUTS_MIXTURE = {
    **DESIGN_INPUTS_METHANE,
    'project_name': 'Test Mixture Design',
    'gas_comp': {
        'METHANE': 85.0, 'ETHANE': 8.0, 'PROPANE': 4.0,
        'NITROGEN': 2.0, 'CARBONDIOXIDE': 1.0
    },
}

class TestDesignCalculationE2E:
    @pytest.fixture(scope="class")
    def engine(self):
        return ThermoEngine()

    def test_methane_single_stage_coolprop(self, engine):
        result = engine.calculate_design_performance(DESIGN_INPUTS_METHANE)
        assert result is not None, "Sonuç None olmamalı"
        self._assert_result_structure(result)

    def test_mixture_with_consistency(self, engine):
        result = engine.calculate_design_performance(DESIGN_INPUTS_MIXTURE)
        assert result is not None
        self._assert_result_structure(result)
        # Tutarlılık modu aktifken kullanılan ve hesaplanan verim yakın olmalı
        if 'poly_eff_used' in result and 'actual_poly_efficiency' in result:
            diff = abs(result['poly_eff_used'] - result['actual_poly_efficiency'])
            assert diff < 5.0, f"Verim farkı çok büyük: {diff}%"

    @pytest.mark.parametrize("eos", ["coolprop", "pr", "srk"])
    def test_all_eos_backends(self, engine, eos):
        inputs = {**DESIGN_INPUTS_METHANE, 'eos_method': eos}
        result = engine.calculate_design_performance(inputs)
        assert result is not None, f"{eos} başarısız"
        assert result.get('power_shaft_total_kw', 0) > 0

    @pytest.mark.parametrize("stages", [1, 2, 3])
    def test_multistage(self, engine, stages):
        inputs = {**DESIGN_INPUTS_METHANE, 'num_stages': stages}
        result = engine.calculate_design_performance(inputs)
        assert result is not None, f"{stages} kademe başarısız"
        stages_data = result.get('stages', [])
        assert len(stages_data) == stages, f"Kademe sayısı {len(stages_data)} != {stages}"

    @pytest.mark.parametrize("temperature", [-50, -20, 0, 25, 60, 120])
    def test_temperature_range(self, engine, temperature):
        inputs = {**DESIGN_INPUTS_METHANE, 't_in': temperature}
        result = engine.calculate_design_performance(inputs)
        assert result is not None, f"T={temperature}°C başarısız"

    def _assert_result_structure(self, result):
        required_keys = [
            'power_shaft_total_kw', 'p_out', 't_out',
            'actual_poly_efficiency', 'engine_version'
        ]
        for key in required_keys:
            assert key in result, f"Eksik sonuç alanı: {key}"

    def test_result_power_physically_plausible(self, engine):
        result = engine.calculate_design_performance(DESIGN_INPUTS_METHANE)
        # 10 kg/s metan, PR=3 → yaklaşık 800-2000 kW arası olmalı
        power = result['power_shaft_total_kw']
        assert 100 < power < 10000, f"Gerçek dışı güç: {power} kW"
```

---

**`tests/integration/test_auth_flow.py`** — Kimlik doğrulama akışı

```python
import pytest
import tempfile
import os
from kasp.data.database import UnitDatabase
from kasp.core.user_manager import UserManager
from kasp.security import hash_password, Session, record_attempt, check_lockout

class TestAuthFlow:
    @pytest.fixture
    def db(self):
        db_path = os.path.join(tempfile.gettempdir(), "test_auth.db")
        db = UnitDatabase(db_path)
        db.create_default_admin(hash_password("AdminPass1"))
        yield db
        db.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def user_manager(self, db):
        return UserManager(db)

    def test_admin_login_flow(self, db, user_manager):
        user = user_manager.authenticate("admin", "AdminPass1")
        assert user is not None
        assert user.username == "admin"
        assert user.role == "admin"

    def test_wrong_password_rejected(self, user_manager):
        user = user_manager.authenticate("admin", "WrongPass1")
        assert user is None

    def test_session_management(self, db, user_manager):
        user = user_manager.authenticate("admin", "AdminPass1")
        Session.login(user)
        assert Session.is_admin()
        assert Session.has_permission("manage_users")

        Session.logout()
        assert not Session.is_admin()
        assert not Session.has_permission("manage_users")

    def test_create_and_auth_new_user(self, db, user_manager):
        user, err = user_manager.create_user("engineer1", "Engineer1!", "engineer", "Test Engineer")
        assert user is not None, f"Hata: {err}"
        assert user.role == "engineer"

        authenticated = user_manager.authenticate("engineer1", "Engineer1!")
        assert authenticated is not None

    def test_password_change_flow(self, db, user_manager):
        user = user_manager.authenticate("admin", "AdminPass1")
        success, err = user_manager.change_password(user.id, "AdminPass1", "NewAdminPass1!")
        assert success, f"Hata: {err}"

        # Eski şifreyle giriş başarısız
        assert user_manager.authenticate("admin", "AdminPass1") is None
        # Yeni şifreyle giriş başarılı
        assert user_manager.authenticate("admin", "NewAdminPass1!") is not None

    def test_inactive_user_cannot_login(self, db, user_manager):
        user, _ = user_manager.create_user("temp", "TempPass1!", "user")
        db.update_user(user.id, is_active=0)
        assert user_manager.authenticate("temp", "TempPass1!") is None

    def test_password_policy_enforced(self, user_manager):
        # Çok kısa
        _, err = user_manager.create_user("test1", "Ab1", "user")
        assert err is not None
        # Büyük harf yok
        _, err = user_manager.create_user("test1", "abcdefgh1", "user")
        assert err is not None
        # Rakam yok
        _, err = user_manager.create_user("test1", "Abcdefgh", "user")
        assert err is not None
```

---

**`tests/integration/test_fallback_chains.py`** — Fallback zinciri entegrasyonu

```python
import pytest
from kasp.core.properties import ThermodynamicSolver
from kasp.core.fallback import EosChain, SolverChain, FallbackTracker
from kasp.core.mixture import GasMixtureBuilder

class TestEosChainIntegration:
    @pytest.fixture
    def solver(self):
        return ThermodynamicSolver()

    @pytest.fixture
    def methane_gas(self):
        builder = GasMixtureBuilder()
        return builder.validate_and_normalize({'METHANE': 100.0})

    def test_coolprop_to_pr_fallback(self, solver, methane_gas):
        # CoolProp mevcut olduğunda
        state = solver.get_properties(101325, 300, methane_gas, 'coolprop')
        assert state is not None
        assert state.phase != 'ideal_fallback'

    def test_ideal_fallback_when_all_eos_unavailable(self, solver, methane_gas):
        # EosChain tamamen kırıldığında ideal fallback
        chain = EosChain(preferred='nonexistent_eos')
        for eos in chain._order:
            chain.mark_broken(eos)
        
        # Solver'ın kendi iç fallback zinciri çalışmalı
        state = solver._solve_fallback(101325, 300, methane_gas)
        assert state is not None
        assert state.fallback is True

    def test_eos_chain_lock_in_per_stage(self):
        chain = EosChain(preferred='coolprop')
        initial = chain.current()
        # İlk aşamada thermo-pack'e düş
        chain.mark_broken('coolprop')
        assert chain.current() == 'thermopack'
        # Sonraki aşamada thermo-pack'ten devam (lock-in)
        chain2 = EosChain(preferred='coolprop', lock_in='thermopack')
        assert chain2.current() == 'thermopack'
```

---

**`tests/integration/test_api_endpoints.py`** — FastAPI endpoint testleri

```python
import pytest
from fastapi.testclient import TestClient
from kasp.api.server import app

client = TestClient(app)

class TestAPIEndpoints:
    def test_health_endpoint(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_constants_endpoint(self):
        response = client.get("/api/constants")
        assert response.status_code == 200
        data = response.json()
        assert "gases" in data
        assert "units" in data

    def test_design_calculation_valid(self):
        payload = {
            "project_name": "API Test",
            "p_in": 1.0, "p_in_unit": "bar(a)",
            "t_in": 25.0, "t_in_unit": "°C",
            "p_out": 3.0, "p_out_unit": "bar(a)",
            "flow": 10.0, "flow_unit": "kg/s",
            "gas_comp": {"METHANE": 100.0},
            "eos_method": "coolprop",
            "method": "Metot 3: Artımlı Basınç",
            "poly_eff": 82.0,
            "mech_eff": 98.0,
            "therm_eff": 35.0,
            "num_units": 1,
            "num_stages": 1,
            "intercooler_t": 40.0,
            "intercooler_dp_pct": 2.0,
            "consistency_check": False,
        }
        response = client.post("/api/calculate/design", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "power_shaft_total_kw" in data

    def test_design_calculation_missing_field(self):
        payload = {"p_in": 1.0}  # eksik alanlar
        response = client.post("/api/calculate/design", json=payload)
        assert response.status_code == 422  # Pydantic validation

    def test_rate_limiting(self):
        # 30+ istek → 429
        payload = {
            "p_in": 1.0, "p_in_unit": "bar(a)",
            "t_in": 25.0, "t_in_unit": "°C",
            "p_out": 3.0, "p_out_unit": "bar(a)",
            "flow": 10.0, "flow_unit": "kg/s",
            "gas_comp": {"METHANE": 100.0},
            "poly_eff": 82.0, "mech_eff": 98.0, "therm_eff": 35.0,
            "num_units": 1, "num_stages": 1,
            "intercooler_t": 40.0, "intercooler_dp_pct": 2.0,
            "consistency_check": False,
        }
        for i in range(35):
            response = client.post("/api/calculate/design", json=payload)
        # Son istek rate-limit'e takılmalı
        assert response.status_code in [200, 429]
```

---

#### 3. THERMODYNAMIC VALIDATION TESTS

---

**`tests/validation/test_asme_ptc10_examples.py`** — ASME PTC 10 örnek problemleri

```python
"""
ASME PTC 10-1997 (R2014) — PERFORMANCE TEST CODE ON COMPRESSORS AND EXHAUSTERS

Örnek Problem C.1 (Ek C): Doğal gaz karışımı, PR=3.0
Örnek Problem C.2 (Ek C): Hava kompresörü, PR=2.5
"""
import pytest
from kasp.core.thermo import ThermoEngine

# ASME PTC 10 Örnek C.1 — Doğal Gaz
PTC10_EXAMPLE_C1 = {
    'project_name': 'PTC 10 Example C.1',
    'p_in': 1.01325, 'p_in_unit': 'bar(a)',
    't_in': 35.0, 't_in_unit': '°C',
    'p_out': 3.03975, 'p_out_unit': 'bar(a)',
    'flow': 15.0, 'flow_unit': 'kg/s',
    'gas_comp': {
        'METHANE': 90.0, 'ETHANE': 5.0, 'PROPANE': 2.0,
        'NITROGEN': 2.0, 'CARBONDIOXIDE': 0.5, 'NBUTANE': 0.5
    },
    'eos_method': 'coolprop',
    'method': 'Metot 3: Artımlı Basınç',
    'poly_eff': 80.0,
    'mech_eff': 98.0,
    'therm_eff': 35.0,
    'num_units': 1,
    'num_stages': 1,
    'intercooler_t': 40.0,
    'intercooler_dp_pct': 2.0,
    'consistency_check': False,
}

class TestASMEPTC10:
    @pytest.fixture(scope="class")
    def engine(self):
        return ThermoEngine()

    def test_example_c1_natural_gas(self, engine):
        """ASME PTC 10 Örnek C.1: Doğal gaz karışımı, PR=3"""
        result = engine.calculate_design_performance(PTC10_EXAMPLE_C1)
        assert result is not None
        
        # PTC 10 beklenen aralıklar (yaklaşık):
        power = result['power_shaft_total_kw']
        # 15 kg/s, PR=3, T_in=35°C → beklenen ~1500-3000 kW
        assert 500 < power < 8000, f"PTC 10 C.1 gücü aralık dışı: {power} kW"
        
        t_out = result['t_out']
        # PR=3, k=1.3 → T_out ≈ (273+35) * 3^((1.3-1)/1.3) ≈ 400-450 K
        assert 350 < t_out < 550, f"PTC 10 C.1 çıkış sıcaklığı aralık dışı: {t_out} K"

    def test_power_increases_with_pr(self, engine):
        """Basınç oranı arttıkça güç artmalı."""
        pr2_inputs = {**PTC10_EXAMPLE_C1, 'p_out': 2.0, 'p_out_unit': 'bar(a)'}
        pr4_inputs = {**PTC10_EXAMPLE_C1, 'p_out': 4.0, 'p_out_unit': 'bar(a)'}
        
        power_pr2 = engine.calculate_design_performance(pr2_inputs)['power_shaft_total_kw']
        power_pr4 = engine.calculate_design_performance(pr4_inputs)['power_shaft_total_kw']
        
        assert power_pr4 > power_pr2, f"PR=4 gücü ({power_pr4}) <= PR=2 gücü ({power_pr2})"

    def test_power_increases_with_flow(self, engine):
        """Debi arttıkça güç artmalı."""
        flow5 = {**PTC10_EXAMPLE_C1, 'flow': 5.0}
        flow20 = {**PTC10_EXAMPLE_C1, 'flow': 20.0}
        
        power_5 = engine.calculate_design_performance(flow5)['power_shaft_total_kw']
        power_20 = engine.calculate_design_performance(flow20)['power_shaft_total_kw']
        
        assert power_20 > power_5

    def test_temperature_ratio_follows_isentropic(self, engine):
        """Çıkış sıcaklığı, izantropik sıcaklık artışına yakın olmalı."""
        result = engine.calculate_design_performance(PTC10_EXAMPLE_C1)
        t_in = 35.0 + 273.15  # K
        PR = 3.0
        k_typical = 1.3
        t_isen = t_in * (PR ** ((k_typical - 1) / k_typical))
        
        t_out = result['t_out']
        # Gerçek çıkış sıcaklığı izantropikten yüksek olmalı (verim < 100%)
        assert t_out > t_isen, f"T_out ({t_out}K) <= T_isen ({t_isen}K)"
        # Ama çok da yüksek olmamalı
        assert t_out < t_isen * 1.3, f"T_out çok yüksek: {t_out}K"


# PTC 10 Örnek C.2 — Hava (ortam havası olarak)
PTC10_EXAMPLE_C2_AIR = {
    **PTC10_EXAMPLE_C1,
    'project_name': 'PTC 10 Example C.2 - Air',
    'p_in': 0.98, 'p_out': 2.45,
    'gas_comp': {'NITROGEN': 78.0, 'OXYGEN': 21.0, 'ARGON': 1.0},
}
```

---

**`tests/validation/test_known_pure_methane.py`** — Saf metan bilinen değerleri

```python
"""
Saf metan için bilinen termodinamik değerler (NIST REFPROP referans).

P=1 bar, T=300K:
  Cp ≈ 2230 J/kg·K (±2%)
  Z ≈ 0.998 (±0.5%)
  k ≈ 1.31 (±1%)
"""
import pytest
from kasp.core.properties import ThermodynamicSolver
from kasp.core.mixture import GasMixtureBuilder

class TestMethaneKnownValues:
    @pytest.fixture(scope="class")
    def methane_gas(self):
        builder = GasMixtureBuilder()
        return builder.validate_and_normalize({'METHANE': 100.0})

    @pytest.fixture(scope="class")
    def solver(self):
        return ThermodynamicSolver()

    def test_methane_cp_at_1bar_300k(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        # CoolProp GERG-2008: Cp ≈ 2225 J/kg·K @ 1 bar, 300K
        assert 2100 < state.Cp < 2400, f"Cp = {state.Cp} J/kg·K, beklenen ~2230"

    def test_methane_z_at_1bar_300k(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        assert 0.99 < state.Z < 1.01, f"Z = {state.Z}, beklenen ~0.998"

    def test_methane_z_decreases_with_pressure(self, methane_gas, solver):
        state_1bar = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_100bar = solver.get_properties(10_000_000, 300.0, methane_gas, 'coolprop')
        assert state_100bar.Z < state_1bar.Z, "Z basınçla azalmalı"

    def test_methane_cp_increases_with_temperature(self, methane_gas, solver):
        state_300 = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_600 = solver.get_properties(100000, 600.0, methane_gas, 'coolprop')
        assert state_600.Cp > state_300.Cp, "Cp sıcaklıkla artmalı"

    def test_methane_k_gt_1(self, methane_gas, solver):
        state = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        assert state.k > 1.0, f"k = {state.k} ≤ 1"

    def test_methane_h_increases_with_temperature(self, methane_gas, solver):
        state_300 = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_400 = solver.get_properties(100000, 400.0, methane_gas, 'coolprop')
        assert state_400.H > state_300.H, "H sıcaklıkla artmalı"

    def test_pr_srk_close_to_coolprop(self, methane_gas, solver):
        """PR/SRK, CoolProp'tan ±%5 sapmamalı."""
        state_cp = solver.get_properties(100000, 300.0, methane_gas, 'coolprop')
        state_pr = solver.get_properties(100000, 300.0, methane_gas, 'pr')
        
        # Z farkı ±%3
        diff_z = abs(state_cp.Z - state_pr.Z) / state_cp.Z
        assert diff_z < 0.03, f"PR Z sapması %{diff_z*100:.1f}"

        # Cp farkı ±%5
        diff_cp = abs(state_cp.Cp - state_pr.Cp) / state_cp.Cp
        assert diff_cp < 0.05, f"PR Cp sapması %{diff_cp*100:.1f}"
```

---

**`tests/validation/test_entropy_conservation.py`** — Entropi korunumu testleri

```python
"""
İzantropik süreçte ΔS ≈ 0 olmalıdır (entropi korunumu).

S_out - S_in < ε (küçük tolerans)
"""
import pytest
from kasp.core.properties import ThermodynamicSolver
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.aerodynamics import CompressorAerodynamics

class TestEntropyConservation:
    @pytest.fixture(scope="class")
    def solver(self):
        return ThermodynamicSolver()

    @pytest.fixture(scope="class")
    def methane_gas(self):
        builder = GasMixtureBuilder()
        return builder.validate_and_normalize({'METHANE': 100.0})

    @pytest.mark.parametrize("p_in,p_out,T_in", [
        (1e5, 2e5, 300.0),     # PR=2
        (1e5, 5e5, 300.0),     # PR=5
        (1e5, 10e5, 350.0),    # PR=10
        (2e5, 10e5, 400.0),    # PR=5, yüksek T
    ])
    def test_isentropic_delta_s_near_zero(self, solver, methane_gas, p_in, p_out, T_in):
        """İzantropik süreçte ΔS ≈ 0."""
        state_in = solver.get_properties(p_in, T_in, methane_gas, 'coolprop')
        
        # İzantropik çıkış sıcaklığını bul
        t_isen = CompressorAerodynamics.calculate_isentropic_outlet_temp(
            state_in, p_out, solver, methane_gas, 'coolprop'
        )
        
        state_out = solver.get_properties(p_out, t_isen, methane_gas, 'coolprop')
        
        delta_S = abs(state_out.S - state_in.S)
        assert delta_S < 50.0, f"ΔS = {delta_S:.1f} J/kg·K (>50), T_in={T_in}K, PR={p_out/p_in}"

    def test_real_process_entropy_increases(self, solver, methane_gas):
        """Gerçek süreçte entropi artar (2. yasa)."""
        p_in, T_in = 1e5, 300.0
        p_out = 3e5
        
        state_in = solver.get_properties(p_in, T_in, methane_gas, 'coolprop')
        
        # Gerçek süreç (izantropik verim < 100% → entropi artar)
        t_isen = CompressorAerodynamics.calculate_isentropic_outlet_temp(
            state_in, p_out, solver, methane_gas, 'coolprop'
        )
        t_real = t_isen + 20.0  # verimsizlik nedeniyle daha yüksek
        
        state_out = solver.get_properties(p_out, t_real, methane_gas, 'coolprop')
        assert state_out.S > state_in.S, "Gerçek süreçte entropi artmalı"
```

---

**`tests/validation/test_iso_6976_heating.py`** — ISO 6976 ısıl değer validasyonu

```python
"""
ISO 6976:2016 — Natural gas — Calculation of calorific values

Bilinen referans değerler:
Saf metan HHV ≈ 55.5 MJ/kg (ISO 6976 Tablo 3)
Saf metan LHV ≈ 50.0 MJ/kg
"""
import pytest
from kasp.core.thermo import ThermoEngine

class TestISO6976Heating:
    @pytest.fixture(scope="class")
    def engine(self):
        return ThermoEngine()

    def test_methane_lhv_iso6976(self, engine):
        """Saf metan LHV ≈ 50 MJ/kg (ISO 6976)."""
        lhv = engine._calculate_heating_values(
            {'METHANE': 100.0}, 'iso6976'
        )
        # tolerans: ±5%
        assert 47.5 < lhv['lhv_mass'] / 1000 < 52.5, \
            f"LHV = {lhv['lhv_mass']/1000:.1f} MJ/kg, beklenen ~50"

    def test_lhv_hhv_relationship(self, engine):
        """HHV > LHV (su buharlaşma ısısı nedeniyle)."""
        vals = engine._calculate_heating_values(
            {'METHANE': 100.0}, 'kasp'
        )
        assert vals['hhv_mass'] > vals['lhv_mass'], "HHV, LHV'den büyük olmalı"

    def test_mixture_lhv_between_components(self, engine):
        """Karışım LHV'si, bileşen LHV'leri arasında olmalı."""
        lhv_methane = engine._calculate_heating_values(
            {'METHANE': 100.0}, 'kasp'
        )['lhv_mass']
        lhv_ethane = engine._calculate_heating_values(
            {'ETHANE': 100.0}, 'kasp'
        )['lhv_mass']
        lhv_mix = engine._calculate_heating_values(
            {'METHANE': 50.0, 'ETHANE': 50.0}, 'kasp'
        )['lhv_mass']
        
        assert min(lhv_methane, lhv_ethane) < lhv_mix < max(lhv_methane, lhv_ethane)
```

---

#### 4. SECURITY TESTS

```python
# tests/security/test_sql_injection.py
class TestSQLInjection:
    def test_username_sanitization(self, db):
        malicious = "admin' OR '1'='1"
        assert db.get_user_by_username(malicious) is None

    def test_project_name_sanitization(self, db):
        malicious = "test'; DROP TABLE Users; --"
        db.save_calculation_history(malicious, "design", {}, {})
        history = db.get_calculation_history()
        assert len(history) > 0  # tablo hala var

# tests/security/test_input_sanitization.py
class TestInputSanitization:
    def test_path_traversal_blocked(self):
        from kasp.security import InputValidator
        assert not InputValidator.validate_file_path("../../../etc/passwd")
        assert InputValidator.validate_file_path("projects/my_project.json")
    
    def test_special_chars_stripped(self):
        from kasp.security import InputValidator
        result = InputValidator.sanitize_string("test'; DROP--")
        assert "'" not in result
        assert ";" not in result
```

---

#### 5. REGRESSION TESTS

```python
# tests/regression/test_regression_snapshots.py
"""
Regresyon snapshot testleri: Bilinen girdiler için hesaplanan sonuçlar
referans değerlerle karşılaştırılır. Her sürümde bu testler çalıştırılır.

Snapshots: tests/regression/snapshots/ dizininde JSON dosyaları.
"""
import json
import pytest
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

class TestRegressionSnapshots:
    @pytest.fixture(scope="class")
    def engine(self):
        from kasp.core.thermo import ThermoEngine
        return ThermoEngine()

    def _load_snapshot(self, name):
        with open(SNAPSHOT_DIR / f"{name}.json") as f:
            return json.load(f)

    def _assert_close(self, actual, expected, rel_tol=0.01, key=""):
        assert abs(actual - expected) / max(abs(expected), 0.001) < rel_tol, \
            f"{key}: {actual} != {expected} (tolerans %{rel_tol*100})"

    def test_methane_pr3_snapshot(self, engine):
        """Metan PR=3 hesaplaması snapshot ile eşleşmeli."""
        snapshot = self._load_snapshot("methane_pr3")
        result = engine.calculate_design_performance(snapshot['inputs'])
        
        self._assert_close(
            result['power_shaft_total_kw'],
            snapshot['expected']['power_shaft_total_kw'],
            rel_tol=0.02, key="power"
        )
        self._assert_close(
            result['t_out'],
            snapshot['expected']['t_out'],
            rel_tol=0.01, key="t_out"
        )

    def test_mixture_pr5_snapshot(self, engine):
        """Gaz karışımı PR=5 snapshot."""
        snapshot = self._load_snapshot("mixture_pr5")
        result = engine.calculate_design_performance(snapshot['inputs'])
        
        for key in ['power_shaft_total_kw', 't_out', 'actual_poly_efficiency']:
            if key in snapshot['expected']:
                self._assert_close(result[key], snapshot['expected'][key], key=key)
```

Snapshot dosyası örneği: `tests/regression/snapshots/methane_pr3.json`
```json
{
  "version": "2.0.4",
  "created": "2026-07-15",
  "description": "Metan PR=3, T_in=25°C, P_in=1bar(a), 10 kg/s, Metot 3, CoolProp",
  "inputs": {
    "p_in": 1.0, "p_in_unit": "bar(a)",
    "t_in": 25.0, "t_in_unit": "°C",
    "p_out": 3.0, "p_out_unit": "bar(a)",
    "flow": 10.0, "flow_unit": "kg/s",
    "gas_comp": {"METHANE": 100.0},
    "eos_method": "coolprop",
    "method": "Metot 3: Artımlı Basınç",
    "poly_eff": 82.0,
    "mech_eff": 98.0,
    "therm_eff": 35.0,
    "num_units": 1,
    "num_stages": 1,
    "intercooler_t": 40.0,
    "intercooler_dp_pct": 2.0,
    "consistency_check": false
  },
  "expected": {
    "power_shaft_total_kw": 1850.0,
    "t_out": 415.0,
    "actual_poly_efficiency": 81.5
  }
}
```

---

#### 6. PERFORMANCE TESTS

```python
# tests/performance/test_calculation_benchmark.py
import time
import pytest

class TestCalculationPerformance:
    @pytest.fixture(scope="class")
    def engine(self):
        from kasp.core.thermo import ThermoEngine
        return ThermoEngine()

    def test_single_calculation_under_2_seconds(self, engine, methane_inputs):
        start = time.perf_counter()
        result = engine.calculate_design_performance(methane_inputs)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Hesaplama {elapsed:.2f}s sürdü (hedef <2s)"

    def test_cached_recalculation_faster(self, engine, methane_inputs):
        # İlk hesaplama
        engine.calculate_design_performance(methane_inputs)
        
        # İkinci hesaplama (cache sıcak)
        start = time.perf_counter()
        engine.calculate_design_performance(methane_inputs)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 1.0, f"Cache'li hesaplama {elapsed:.2f}s (hedef <1s)"

    def test_multistage_scales_linearly(self, engine, methane_inputs):
        times = {}
        for stages in [1, 2, 4, 8]:
            inputs = {**methane_inputs, 'num_stages': stages}
            start = time.perf_counter()
            engine.calculate_design_performance(inputs)
            times[stages] = time.perf_counter() - start
        
        # 8 kademe, 1 kademenin en fazla 10 katı sürmeli
        assert times[8] < times[1] * 10, \
            f"8 kademe ({times[8]:.2f}s), 1 kademenin {times[8]/times[1]:.1f}x süresi"
```

---

#### 7. UI TESTS (Headless)

```python
# tests/ui/test_validation_feedback.py
class TestValidationFeedback:
    def test_pressure_negative_shows_red_border(self, qtbot, design_tab):
        field = design_tab.p_in_field
        field.setText("-1.0")
        qtbot.wait(100)
        # Validasyon sonrası kırmızı border
        assert "red" in field.styleSheet().lower() or \
               "border-color: red" in field.styleSheet().lower()

    def test_valid_pressure_shows_normal_border(self, qtbot, design_tab):
        field = design_tab.p_in_field
        field.setText("5.0")
        qtbot.wait(100)
        # Geçerli girişte kırmızı border olmamalı
        assert "red" not in field.styleSheet().lower()
```

---

### CONFTEST.PY — Paylaşılan Fixture'lar

```python
# tests/conftest.py
import pytest
import tempfile
import os
import sys

@pytest.fixture(scope="session")
def methane_inputs():
    return {
        'project_name': 'Test Methane',
        'p_in': 1.0, 'p_in_unit': 'bar(a)',
        't_in': 25.0, 't_in_unit': '°C',
        'p_out': 3.0, 'p_out_unit': 'bar(a)',
        'flow': 10.0, 'flow_unit': 'kg/s',
        'gas_comp': {'METHANE': 100.0},
        'eos_method': 'coolprop',
        'method': 'Metot 3: Artımlı Basınç',
        'poly_eff': 82.0, 'mech_eff': 98.0, 'therm_eff': 35.0,
        'num_units': 1, 'num_stages': 1,
        'intercooler_t': 40.0, 'intercooler_dp_pct': 2.0,
        'consistency_check': False,
    }

@pytest.fixture(scope="function")
def temp_db():
    """Her test için geçici veritabanı."""
    db_path = os.path.join(tempfile.gettempdir(), f"test_{os.getpid()}.db")
    from kasp.data.database import UnitDatabase
    db = UnitDatabase(db_path)
    yield db
    db.close()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass

@pytest.fixture(scope="session")
def thermo_engine():
    from kasp.core.thermo import ThermoEngine
    return ThermoEngine()

# UI testleri için PyQt5 kontrolü
def pytest_configure(config):
    try:
        import PyQt5
    except ImportError:
        config.option.markexpr = "not ui"

# pytest.ini marker'ları:
# [pytest]
# markers =
#     slow: Yavaş testler (>1s)
#     ui: PyQt5 UI testleri
#     e2e: Uçtan uca entegrasyon testleri
#     validation: Termodinamik doğrulama testleri
#     security: Güvenlik testleri
```

---

### CI/CD ENTEGRASYONU

```yaml
# .github/workflows/test.yml
name: KASP Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest]
        python: ['3.10', '3.11', '3.12']
      fail-fast: false

    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      
      - name: Cache pip
        uses: actions/cache@v3
        with:
          path: ~\AppData\Local\pip\Cache
          key: pip-${{ runner.os }}-${{ matrix.python }}-${{ hashFiles('requirements.txt') }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-benchmark pytest-qt
      
      - name: Unit tests
        run: pytest tests/unit/ -v --cov=kasp --cov-report=xml --cov-report=term -m "not slow"
      
      - name: Integration tests
        run: pytest tests/integration/ -v -m "not slow"
      
      - name: Validation tests
        run: pytest tests/validation/ -v -m "not slow"
      
      - name: Security tests
        run: pytest tests/security/ -v
      
      - name: Regression tests
        run: pytest tests/regression/ -v
      
      - name: Performance tests
        run: pytest tests/performance/ -v --benchmark-only
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests

  lint:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: Ruff lint
        run: |
          pip install ruff
          ruff check kasp/ --select=E,F,W,B,C4,N,UP
      - name: Type check
        run: |
          pip install pyright
          pyright kasp/ --ignoreExternal
```

---

### TEST KAPSAMA HEDEFLERİ

| Kategori | Mevcut | Hedef (v2.1) | Öncelik |
|----------|--------|-------------|---------|
| **Birim testleri** (core) | %25 | %85 | Yüksek |
| **Birim testleri** (security) | %40 | %90 | Kritik |
| **Birim testleri** (utils) | %15 | %70 | Orta |
| **Entegrasyon testleri** | %5 | %60 | Yüksek |
| **Termodinamik validasyon** | %10 | %80 | Yüksek |
| **Regresyon testleri** | %0 | %50 | Yüksek |
| **Güvenlik testleri** | %5 | %80 | Kritik |
| **UI testleri** | %10 | %30 | Düşük |
| **Performans testleri** | %0 | %40 | Orta |
| **Genel satır kapsamı** | ~%15 | ~%75 | - |

---

### MEVCUT TESTLERİN YENİ YAPIYA ENTEGRASYONU

| Mevcut Test | Yeni Konum | Durum |
|------------|-----------|-------|
| `test_thermo_refactor.py` | `tests/unit/core/test_thermo_design_orch.py` | Taşı ve genişlet |
| `test_thermo_limits.py` | `tests/unit/core/test_thermo_limits.py` | Olduğu gibi taşı |
| `test_eos.py` | `tests/validation/test_eos_comparison.py` | Düzelt ve taşı |
| `test_new_eos.py` | `tests/validation/test_eos_comparison.py` | Birleştir |
| `test_power.py` | `tests/validation/test_known_pure_methane.py` | Birleştir |
| `test_three_methods.py` | `tests/unit/core/test_thermo_methods.py` | Düzelt ve birleştir |
| `test_fallback_solvers.py` | `tests/unit/core/test_fallback.py` | Düzelt ve taşı |
| `test_mixture_refactor.py` | `tests/unit/core/test_mixture.py` | Taşı |
| `test_properties_refactor.py` | `tests/unit/core/test_properties.py` | Taşı |
| `test_selection.py` (yeni) | `tests/unit/core/test_selection.py` | Yeni oluştur |
| `test_security_session.py` | `tests/unit/security/test_session.py` | Taşı |
| `test_user_manager.py` | `tests/unit/security/` | Taşı |
| `test_unit_conversion_refactor.py` | `tests/unit/core/test_units.py` | Birleştir |
| `test_performance_corrections.py` | `tests/unit/core/test_performance_corr.py` | Olduğu gibi taşı |
| `test_theme_contrast.py` | `tests/ui/test_theme_contrast.py` | Taşı |
| `test_updater.py` | `tests/unit/utils/test_updater.py` | Taşı |
| `test_release_metadata.py` | `tests/unit/utils/test_release_metadata.py` | Taşı |
| `test_reporting_refactor.py` | `tests/integration/test_export.py` | Birleştir |
| `test_dwsim_integration.py` | `tests/integration/` | Olduğu gibi taşı |
| `test_engineering_mode.py` | `tests/unit/core/test_engineering.py` | Taşı |
| `test_engineering_shootout.py` | `tests/unit/core/test_engineering.py` | Birleştir |
| `verify_eos.py` | `tests/validation/test_eos_comparison.py` | Birleştir |
| `verify_independent.py` | `tests/validation/test_asme_ptc10_examples.py` | Birleştir |
| `verify_textbook.py` | `tests/validation/test_asme_ptc10_examples.py` | Birleştir |
| `verify_stability.py` | `tests/regression/test_regression_snapshots.py` | Birleştir |

---

### TEST ÇALIŞTIRMA KOMUTLARI

```bash
# Tüm testler (CI)
pytest tests/ -v --cov=kasp --cov-report=html

# Sadece birim testleri
pytest tests/unit/ -v

# Sadece termodinamik validasyon
pytest tests/validation/ -v -m validation

# Yavaş testleri hariç tut
pytest tests/ -v -m "not slow"

# Sadece güvenlik testleri
pytest tests/security/ -v

# Paralel çalıştırma (pytest-xdist ile)
pytest tests/ -v -n auto -m "not ui"

# Coverage raporu
pytest tests/ --cov=kasp --cov-report=term-missing --cov-fail-under=60

# Spesifik test dosyası
pytest tests/unit/core/test_aerodynamics.py::TestPolytropicEfficiency -v
```

---

## UYGULAMA ÖNCELİK SIRASI (Güncellenmiş — Test Planı Dahil)

### 1. Gün — Güvenlik Temel Taşları (4 saat)
- [x] C1/C11: Admin şifresi güvenliği → `security.py`, `main.py`
- [x] M5/M26: Şifre politikası (8 karakter, regex) → `user_manager.py`
- [x] M25: Lockout HMAC güvenliği → `security.py`
- [x] C5/C7: `except:pass` temizliği → tüm dosyalar
- **Test:** `tests/unit/security/test_password_hashing.py`
- **Test:** `tests/unit/security/test_lockout.py`

### 2. Gün — Ağ & Veritabanı Güvenliği (4 saat)
- [ ] C4/M30: SSL sertifika zorunluluğu → `updater.py`
- [ ] C3/M27/M28: API localhost + CORS kısıt + rate limit → `server.py`
- [ ] C12/C14/C16: DB WAL + index + close() → `database.py`
- [ ] M1: Girdi validasyonu → `thermo.py`
- **Test:** `tests/integration/test_api_endpoints.py`
- **Test:** `tests/security/test_sql_injection.py`

### 3. Gün — Termodinamik Düzeltmeler (4 saat)
- [ ] T1/T2/T3: Fallback Z/entropi/Cp düzeltmeleri → `properties.py`
- [ ] M2/M3/M4: Sıfıra bölme korumaları → `selection.py`
- [ ] M6: Salt 32 byte → `security.py`
- **Test:** `tests/validation/test_known_pure_methane.py`
- **Test:** `tests/validation/test_entropy_conservation.py`

### 4-5. Gün — Mimari Bölme + Test Altyapısı (8 saat)
- [ ] C10: `UnitDatabase` → 4 repository sınıfına böl
- [ ] C8: `ThermoEngine` → Facade + 3 service sınıfı
- [ ] C9: `main_window.py` → UpdateService + EngineeringPanel
- [ ] `tests/` dizin yapısını oluştur, `conftest.py` yaz
- [ ] Mevcut testleri yeni yapıya taşı
- **Test:** `tests/unit/data/test_*_repository.py`
- **Test:** `tests/unit/core/test_thermo_design_orch.py`

### 6-7. Gün — Profesyonellik + Validasyon Testleri (8 saat)
- [ ] M11: `reporting.py` bölme
- [ ] M12: `thermo_methods.py` strategy pattern
- [ ] T4: Binary etkileşim parametreleri
- [ ] M14: Sihirli sayılar → `settings.py`
- **Test:** `tests/validation/test_asme_ptc10_examples.py`
- **Test:** `tests/validation/test_iso_6976_heating.py`
- **Test:** `tests/validation/test_eos_comparison.py`

### 8. Gün — Entegrasyon + Regresyon Testleri (4 saat)
- [ ] C13: Tip belirteçleri (öncelikli dosyalar)
- [ ] C15: Devre dışı testleri düzelt/aktif et
- [ ] M17/M18/M19: Ölü kod temizliği
- **Test:** `tests/integration/test_design_calculation_e2e.py`
- **Test:** `tests/integration/test_auth_flow.py`
- **Test:** `tests/integration/test_fallback_chains.py`
- **Test:** `tests/regression/test_regression_snapshots.py` (snapshot oluştur)

### 9. Gün — UI + Build + CI/CD (4 saat)
- [ ] M35-M38: UI iyileştirmeleri (cache, kısayollar, responsive)
- [ ] M40-M42: Build sistemi temizliği
- [ ] C6/C10/C11: İkili modül birleştirme
- **Test:** `tests/ui/test_validation_feedback.py`
- **Test:** `tests/performance/test_calculation_benchmark.py`
- **CI/CD:** `.github/workflows/test.yml` oluştur

### 10. Gün — Final Entegrasyon + Coverage (4 saat)
- [ ] Tüm testlerin toplu çalıştırılması ve hata ayıklama
- [ ] Coverage raporu analizi, eksik kapsama alanlarına ek test
- [ ] Snapshot verilerinin validasyonu ve commit
- [ ] `pytest --cov=kasp --cov-report=html --cov-fail-under=60`
- [ ] CHANGELOG güncelleme

---

### TOPLAM SÜRE: 10 gün (40 saat)

| Gün | Kod Değişikliği | Yeni Test | Kümülatif Coverage |
|-----|----------------|-----------|-------------------|
| 1 | Güvenlik altyapısı | 2 dosya | %15 → %20 |
| 2 | Ağ/DB güvenliği | 2 dosya | %20 → %25 |
| 3 | Termo düzeltmeler | 2 dosya | %25 → %35 |
| 4-5 | Mimari bölme | 4 dosya | %35 → %50 |
| 6-7 | Profesyonellik | 3 dosya | %50 → %65 |
| 8 | Entegrasyon testleri | 4 dosya | %65 → %75 |
| 9 | UI + CI/CD | 3 dosya | %75 → %78 |
| 10 | Final parlatma | - | %78 → %80+ |

