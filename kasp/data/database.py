import sqlite3
import json
import shutil
import sys
import threading
import logging
import os
import re


# JSON şema doğrulama — her kayıt yüklenmeden önce kontrol edilir (P4-5).
# Eksik/yanlış tipli alanlar, negatif/placeholder değerler hata verir.
# Bu, "min_flow=0 / max_flow=1000 / PR=10" gibi placeholder'ların
# sessizce DB'ye girmesini engeller.

TURBINE_REQUIRED = {
    "manufacturer": str,
    "model": str,
    "type": str,
    "iso_power_kw": (int, float),
    "iso_heat_rate_kj_kwh": (int, float),
}

TURBINE_OPTIONAL = {
    "performance_correction_data": dict,
    "surge_flow": (int, float),
    "stonewall_flow": (int, float),
    "max_pressure_ratio": (int, float),
    "min_flow_kgs": (int, float),
    "max_flow_kgs": (int, float),
    "fuel_type": str,
}

COMPRESSOR_REQUIRED = {
    "manufacturer": str,
    "model": str,
    "max_pressure_ratio": (int, float),
    "min_flow_kgs": (int, float),
    "max_flow_kgs": (int, float),
}

COMPRESSOR_OPTIONAL = {
    "performance_map_data": dict,
}


def _validate_turbine_record(t: dict, idx: int) -> list[str]:
    """Tek bir türbin kaydını doğrular. Hata listesi döner (boşsa geçerli)."""
    errors = []
    for field, expected_type in TURBINE_REQUIRED.items():
        if field not in t:
            errors.append(f"Satır {idx}: Zorunlu alan eksik: '{field}'")
            continue
        val = t[field]
        if not isinstance(val, expected_type):
            errors.append(f"Satır {idx}: '{field}' tipi yanlış (beklenen: {expected_type.__name__ if isinstance(expected_type, type) else 'sayi'}, actual: {type(val).__name__})")
    for field, expected_type in TURBINE_OPTIONAL.items():
        if field in t:
            val = t[field]
            if val is not None and not isinstance(val, expected_type):
                errors.append(f"Satır {idx}: '{field}' tipi yanlış (beklenen: {expected_type.__name__ if isinstance(expected_type, type) else 'sayi/dict'}, actual: {type(val).__name__})")
    # Fiziksel mantık kontrolleri
    if "min_flow_kgs" in t and "max_flow_kgs" in t:
        mn = t["min_flow_kgs"]
        mx = t["max_flow_kgs"]
        if mn is not None and mx is not None and mx <= mn:
            errors.append(f"Satır {idx}: max_flow_kgs ({mx}) min_flow_kgs ({mn})'dan büyük olmalı")
    if "max_pressure_ratio" in t:
        pr = t["max_pressure_ratio"]
        if pr is not None and pr <= 1.0:
            errors.append(f"Satır {idx}: max_pressure_ratio > 1.0 olmalı (actual: {pr})")
    if "iso_power_kw" in t:
        pw = t["iso_power_kw"]
        if pw is not None and pw <= 0:
            errors.append(f"Satır {idx}: iso_power_kw > 0 olmalı (actual: {pw})")
    # Placeholder benzeri değerler için uyarı (hata değil)
    if t.get("min_flow_kgs") == 0 and t.get("max_flow_kgs") in (500, 1000, 9999):
        errors.append(f"Satır {idx}: UYARI - min_flow=0 ve max_flow={t['max_flow_kgs']} placeholder gibi görünüyor")
    if t.get("max_pressure_ratio") == 10.0 and t.get("surge_flow") == 0 and t.get("stonewall_flow") in (500, 1000, 9999):
        errors.append(f"Satır {idx}: UYARI - surge/stonewall placeholder gibi görünüyor")
    return errors


def _validate_compressor_record(c: dict, idx: int) -> list[str]:
    """Tek bir kompresör kaydını doğrular. Hata listesi döner (boşsa geçerli)."""
    errors = []
    for field, expected_type in COMPRESSOR_REQUIRED.items():
        if field not in c:
            errors.append(f"Satır {idx}: Zorunlu alan eksik: '{field}'")
            continue
        val = c[field]
        if not isinstance(val, expected_type):
            errors.append(f"Satır {idx}: '{field}' tipi yanlış (beklenen: {expected_type.__name__ if isinstance(expected_type, type) else 'sayi'}, actual: {type(val).__name__})")
    for field, expected_type in COMPRESSOR_OPTIONAL.items():
        if field in c:
            val = c[field]
            if val is not None and not isinstance(val, expected_type):
                errors.append(f"Satır {idx}: '{field}' tipi yanlış (beklenen: {expected_type.__name__ if isinstance(expected_type, type) else 'dict'}, actual: {type(val).__name__})")
    # Fiziksel mantık kontrolleri
    mn = c.get("min_flow_kgs")
    mx = c.get("max_flow_kgs")
    if mn is not None and mx is not None and mx <= mn:
        errors.append(f"Satır {idx}: max_flow_kgs ({mx}) min_flow_kgs ({mn})'dan büyük olmalı")
    pr = c.get("max_pressure_ratio")
    if pr is not None and pr <= 1.0:
        errors.append(f"Satır {idx}: max_pressure_ratio > 1.0 olmalı (actual: {pr})")
    # Placeholder uyarısı
    if c.get("min_flow_kgs") == 0 and c.get("max_flow_kgs") in (500, 1000, 9999):
        errors.append(f"Satır {idx}: UYARI - min_flow=0 ve max_flow={c['max_flow_kgs']} placeholder gibi görünüyor")
    if c.get("max_pressure_ratio") == 10.0 and c.get("performance_map_data") == {}:
        errors.append(f"Satır {idx}: UYARI - boş performance_map_data, seçimde harita kullanılamaz")
    return errors


def validate_sample_data(filepath: str, validator_fn) -> tuple[list[dict], list[str]]:
    """JSON dosyasını yükler ve her kaydı doğrular.
    
    Returns:
        (valid_records, errors)
    """
    if not os.path.exists(filepath):
        return [], [f"Dosya bulunamadı: {filepath}"]
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [], [f"Geçersiz JSON ({filepath}): {e}"]
    except Exception as e:
        return [], [f"Dosya okuma hatası ({filepath}): {e}"]

    if not isinstance(data, list):
        return [], [f"JSON kök bir dizi olmalı ({filepath})"]

    valid = []
    errors = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"Satır {i}: Nesne değil, {type(item).__name__}")
            continue
        item_errors = validator_fn(item, i)
        # "UYARI" prefix'i hata mesajının içinde geçiyor (Satır N: UYARI - ...)
        # Bu yüzden .startswith() yerine "UYARI" in string kontrolü yap.
        has_real_error = any("UYARI" not in e for e in item_errors)
        if has_real_error:
            errors.extend([e for e in item_errors if "UYARI" not in e])
        else:
            # Sadece uyarı varsa kaydı kabul et ama uyarıları logla
            for e in item_errors:
                if "UYARI" in e:
                    logging.getLogger(__name__).warning(f"{filepath}: {e}")
            valid.append(item)
    return valid, errors


def _resolve_db_path(db_name="kasp_database.db"):
    if not getattr(sys, "frozen", False):
        return db_name
    base = os.path.expanduser("~/Library/Application Support/KASP") if sys.platform == "darwin" \
           else os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KASP")
    os.makedirs(base, exist_ok=True)
    target = os.path.join(base, db_name)
    if not os.path.exists(target):
        bundled = os.path.join(sys._MEIPASS, db_name)
        if os.path.exists(bundled):
            shutil.copy2(bundled, target)
    return target


class UnitDatabase:
    def __init__(self, db_name=None):
        self.db_name = db_name or _resolve_db_path()
        self._local = threading.local()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cached_turbines = None
        self._cached_compressors = None
        self._cache_lock = threading.Lock()
        self.create_tables()
        self._migrate_database_schema()
        # Sync sample data if tables are empty or missing newer turbines (< 146)
        if self._get_turbine_count() < 146:
            self.insert_sample_data()
    
    def get_connection(self):
        """Thread-safe bağlantı oluştur"""
        if getattr(self._local, 'conn', None) is None:
            conn = sqlite3.connect(self.db_name, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA busy_timeout = 5000;")
                conn.execute("PRAGMA journal_mode = WAL;")
            except sqlite3.Error:
                pass
            self._local.conn = conn
        return self._local.conn
    
    def close(self):
        """Thread-local bağlantıyı kapat"""
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            self._local.conn = None
    
    def get_cursor(self):
        """Thread-safe cursor döndür"""
        conn = self.get_connection()
        return conn.cursor()

    def invalidate_catalog_cache(self):
        """Invalidate in-memory cache of turbines and compressors."""
        with self._cache_lock:
            self._cached_turbines = None
            self._cached_compressors = None

    def _get_turbine_count(self):
        """Return count of rows in Turbines table, or 0 if empty or table does not exist."""
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM Turbines")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0
        except sqlite3.Error as e:
            self.logger.warning(f"Türbin sayısı kontrol hatası: {e}")
            return 0
    
    def _is_turbine_table_empty(self):
        """Check if turbines table exists and has data"""
        return self._get_turbine_count() == 0

    def _needs_sample_data_sync(self):
        """Check if existing database is missing newer sample turbines (< 146)"""
        return self._get_turbine_count() < 146
    
    def create_tables(self):
        """Veritabanı tablolarını oluştur"""
        try:
            cursor = self.get_cursor()
            
            # Türbinler tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Turbines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer TEXT NOT NULL,
                    model TEXT NOT NULL,
                    type TEXT NOT NULL,
                    iso_power_kw REAL NOT NULL,
                    iso_heat_rate_kj_kwh REAL NOT NULL,
                    performance_correction_data TEXT,
                    surge_flow REAL DEFAULT 0,
                    stonewall_flow REAL DEFAULT 0,
                    max_pressure_ratio REAL DEFAULT 10.0,
                    min_flow_kgs REAL DEFAULT 0,
                    max_flow_kgs REAL DEFAULT 1000,
                    fuel_type TEXT DEFAULT 'Natural Gas',
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(manufacturer, model)
                )
            """)
            
            # Kompresörler tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Compressors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer TEXT NOT NULL,
                    model TEXT NOT NULL UNIQUE,
                    max_pressure_ratio REAL NOT NULL,
                    min_flow_kgs REAL NOT NULL,
                    max_flow_kgs REAL NOT NULL,
                    performance_map_data TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Hesaplama geçmişi tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CalculationHistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT,
                    calculation_type TEXT,
                    inputs_json TEXT,
                    results_json TEXT,
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_notes TEXT
                )
            """)

            # Kullanıcı yönetimi tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    full_name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    must_change_password INTEGER DEFAULT 0,
                    security_question TEXT DEFAULT '',
                    security_answer_hash TEXT DEFAULT '',
                    recovery_key_hash TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login TEXT
                )
            """)

            self.get_connection().commit()
            self.logger.info("Veritabanı tabloları başarıyla oluşturuldu.")
            
        except sqlite3.Error as e:
            self.logger.error(f"Tablo oluşturma hatası: {e}", exc_info=True)
            raise

    def _add_column_if_not_exists(self, table_name, column_name, column_type):
        """Eksik kolonu tabloya ekler (SQL injection korumalı)"""
        ALLOWED_TABLES = {"Turbines", "Compressors", "CalculationHistory", "Users"}
        if table_name not in ALLOWED_TABLES:
            self.logger.error(f"Geçersiz tablo adı: {table_name}")
            return False

        if not re.match(r"^[a-zA-Z0-9_]+$", column_name):
            self.logger.error(f"Geçersiz kolon adı: {column_name}")
            return False

        if not re.match(r"^[a-zA-Z0-9_\s\(\)\'\"\.\-]+$", column_type):
            self.logger.error(f"Geçersiz kolon veri tipi: {column_type}")
            return False

        cursor = self.get_cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if column_name not in columns:
                self.logger.warning(f"VT Şema Güncellemesi: {table_name} tablosuna '{column_name}' kolonu ekleniyor.")
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                self.get_connection().commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Kolon ekleme hatası ({table_name}.{column_name}): {e}")
            return False

    def _migrate_database_schema(self):
        """Var olan VT şemasını güncel versiyona taşır."""
        self.logger.info("VT Şema Güncellemesi Başlatıldı...")
        
        self._add_column_if_not_exists('Turbines', 'surge_flow', 'REAL DEFAULT 0')
        self._add_column_if_not_exists('Turbines', 'stonewall_flow', 'REAL DEFAULT 0')
        self._add_column_if_not_exists('Turbines', 'max_pressure_ratio', 'REAL DEFAULT 10.0')
        self._add_column_if_not_exists('Turbines', 'min_flow_kgs', 'REAL DEFAULT 0')
        self._add_column_if_not_exists('Turbines', 'max_flow_kgs', 'REAL DEFAULT 1000')
        self._add_column_if_not_exists('Turbines', 'fuel_type', 'TEXT DEFAULT "Natural Gas"')
        self._add_column_if_not_exists('Users', 'must_change_password', 'INTEGER DEFAULT 0')
        self._add_column_if_not_exists('Users', 'security_question', 'TEXT DEFAULT ""')
        self._add_column_if_not_exists('Users', 'security_answer_hash', 'TEXT DEFAULT ""')
        self._add_column_if_not_exists('Users', 'recovery_key_hash', 'TEXT DEFAULT ""')

        self.logger.info("VT Şema Güncellemesi Tamamlandı.")
    
    def insert_sample_data(self):
        """JSON dosyalarından örnek verileri yükle (şema doğrulamalı)."""
        try:
            cursor = self.get_cursor()

            # Turbines
            turbines_path = os.path.join(os.path.dirname(__file__), 'turbines.json')
            if os.path.exists(turbines_path):
                valid_turbines, errors = validate_sample_data(turbines_path, _validate_turbine_record)
                if errors:
                    raise ValueError(f"Türbin verisi doğrulama hataları: {'; '.join(errors)}")
                for t in valid_turbines:
                    correction_data = t.get('performance_correction_data', {})
                    if isinstance(correction_data, dict):
                        correction_data = json.dumps(correction_data)

                    cursor.execute("""
                        INSERT OR IGNORE INTO Turbines(
                            manufacturer, model, type, iso_power_kw, iso_heat_rate_kj_kwh,
                            performance_correction_data, surge_flow, stonewall_flow,
                            max_pressure_ratio, min_flow_kgs, max_flow_kgs, fuel_type
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        t['manufacturer'], t['model'], t['type'], t['iso_power_kw'], t['iso_heat_rate_kj_kwh'],
                        correction_data, t.get('surge_flow', 0), t.get('stonewall_flow', 0),
                        t.get('max_pressure_ratio', 10.0), t.get('min_flow_kgs', 0),
                        t.get('max_flow_kgs', 1000), t.get('fuel_type', 'Natural Gas')
                    ))
            else:
                self.logger.warning(f"Türbin veri dosyası bulunamadı: {turbines_path}")

            # Compressors
            compressors_path = os.path.join(os.path.dirname(__file__), 'compressors.json')
            if os.path.exists(compressors_path):
                valid_compressors, errors = validate_sample_data(compressors_path, _validate_compressor_record)
                if errors:
                    raise ValueError(f"Kompresör verisi doğrulama hataları: {'; '.join(errors)}")
                for c in valid_compressors:
                    map_data = c.get('performance_map_data', {})
                    if isinstance(map_data, dict):
                        map_data = json.dumps(map_data)

                    cursor.execute("""
                        INSERT OR IGNORE INTO Compressors(
                            manufacturer, model, max_pressure_ratio, min_flow_kgs, max_flow_kgs, performance_map_data
                        ) VALUES(?,?,?,?,?,?)
                    """, (
                        c['manufacturer'], c['model'], c['max_pressure_ratio'],
                        c['min_flow_kgs'], c['max_flow_kgs'], map_data
                    ))
            else:
                self.logger.warning(f"Kompresör veri dosyası bulunamadı: {compressors_path}")

            self.get_connection().commit()
            self.invalidate_catalog_cache()
            self.logger.info("Örnek veriler veritabanına yüklendi (doğrulamalı).")

        except Exception as e:
            self.logger.error(f"Örnek veri ekleme hatası: {e}", exc_info=True)
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
    
    def get_all_turbines_full_data(self):
        """Tüm türbin verilerini getir (önbellekli)"""
        with self._cache_lock:
            if self._cached_turbines is not None:
                return [dict(t) for t in self._cached_turbines]

        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM Turbines ORDER BY manufacturer, iso_power_kw")
            
            turbines = []
            for row in cursor.fetchall():
                turbine = dict(row)
                if turbine['performance_correction_data']:
                    try:
                        turbine['performance_correction_data'] = json.loads(turbine['performance_correction_data'])
                    except (json.JSONDecodeError, TypeError, ValueError):
                        turbine['performance_correction_data'] = {}
                else:
                    turbine['performance_correction_data'] = {}
                
                turbine.pop('temp_correction', None)
                turbine.pop('alt_correction', None)
                
                turbines.append(turbine)
            
            with self._cache_lock:
                self._cached_turbines = turbines
                return [dict(t) for t in self._cached_turbines]
        except sqlite3.Error as e:
            self.logger.error(f"Türbin verileri getirme hatası: {e}")
            return []
    
    def get_all_compressors_full_data(self):
        """Tüm kompresör verilerini getir (önbellekli)"""
        with self._cache_lock:
            if self._cached_compressors is not None:
                return [dict(c) for c in self._cached_compressors]

        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM Compressors ORDER BY manufacturer, max_pressure_ratio")
            
            compressors = []
            for row in cursor.fetchall():
                compressor = dict(row)
                if compressor['performance_map_data']:
                    try:
                        compressor['performance_map_data'] = json.loads(compressor['performance_map_data'])
                    except (json.JSONDecodeError, TypeError, ValueError):
                        compressor['performance_map_data'] = {}
                else:
                    compressor['performance_map_data'] = {}
                
                compressors.append(compressor)
            
            with self._cache_lock:
                self._cached_compressors = compressors
                return [dict(c) for c in self._cached_compressors]
        except sqlite3.Error as e:
            self.logger.error(f"Kompresör verileri getirme hatası: {e}")
            return []
    
    def get_turbine_by_id(self, turbine_id):
        """ID'ye göre türbin getir"""
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM Turbines WHERE id = ?", (turbine_id,))
            row = cursor.fetchone()
            if row:
                turbine = dict(row)
                if turbine['performance_correction_data']:
                    try:
                        turbine['performance_correction_data'] = json.loads(turbine['performance_correction_data'])
                    except (json.JSONDecodeError, TypeError, ValueError):
                        turbine['performance_correction_data'] = {}
                else:
                    turbine['performance_correction_data'] = {}
                
                turbine.pop('temp_correction', None)
                turbine.pop('alt_correction', None)
                
                return turbine
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Türbin getirme hatası: {e}")
            return None
    
    def add_turbine(self, turbine_data):
        """Yeni türbin ekle"""
        try:
            cursor = self.get_cursor()
            
            correction_data_str = turbine_data.get('performance_correction_data', '{}')
            if isinstance(correction_data_str, dict):
                 correction_data_str = json.dumps(correction_data_str)
                 
            cursor.execute("""
                INSERT INTO Turbines 
                (manufacturer, model, type, iso_power_kw, iso_heat_rate_kj_kwh, 
                 performance_correction_data, surge_flow, stonewall_flow, max_pressure_ratio,
                 min_flow_kgs, max_flow_kgs, fuel_type)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(manufacturer, model) DO UPDATE SET
                    type = excluded.type,
                    iso_power_kw = excluded.iso_power_kw,
                    iso_heat_rate_kj_kwh = excluded.iso_heat_rate_kj_kwh,
                    performance_correction_data = excluded.performance_correction_data,
                    surge_flow = excluded.surge_flow,
                    stonewall_flow = excluded.stonewall_flow,
                    max_pressure_ratio = excluded.max_pressure_ratio,
                    min_flow_kgs = excluded.min_flow_kgs,
                    max_flow_kgs = excluded.max_flow_kgs,
                    fuel_type = excluded.fuel_type,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                turbine_data['manufacturer'],
                turbine_data['model'],
                turbine_data['type'],
                turbine_data['iso_power_kw'],
                turbine_data['iso_heat_rate_kj_kwh'],
                correction_data_str,
                turbine_data.get('surge_flow', 0),
                turbine_data.get('stonewall_flow', 0),
                turbine_data.get('max_pressure_ratio', 10.0),
                turbine_data.get('min_flow_kgs', 0),
                turbine_data.get('max_flow_kgs', 1000),
                turbine_data.get('fuel_type', 'Natural Gas')
            ))
            
            self.get_connection().commit()
            self.invalidate_catalog_cache()
            self.logger.info(f"Türbin eklendi: {turbine_data['manufacturer']} {turbine_data['model']}")
            return True
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Türbin ekleme hatası: {e}")
            return False
    
    def update_turbine_correction_data(self, turbine_id, correction_data):
        """Türbin düzeltme verilerini güncelle"""
        try:
            cursor = self.get_cursor()
            
            correction_data_str = correction_data
            if isinstance(correction_data_str, dict):
                 correction_data_str = json.dumps(correction_data_str)
                 
            cursor.execute("""
                UPDATE Turbines 
                SET performance_correction_data = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (correction_data_str, turbine_id))
            
            self.get_connection().commit()
            self.invalidate_catalog_cache()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Türbin güncelleme hatası: {e}")
            return False
    
    def delete_turbine(self, turbine_id):
        """Türbin sil"""
        try:
            cursor = self.get_cursor()
            cursor.execute("DELETE FROM Turbines WHERE id = ?", (turbine_id,))
            self.get_connection().commit()
            self.invalidate_catalog_cache()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Türbin silme hatası: {e}")
            return False
    
    def add_compressor(self, compressor_data):
        """Yeni kompresör ekle"""
        try:
            cursor = self.get_cursor()
            
            map_data_str = compressor_data.get('performance_map_data', '{}')
            if isinstance(map_data_str, dict):
                 map_data_str = json.dumps(map_data_str)
                 
            cursor.execute("""
                INSERT INTO Compressors 
                (manufacturer, model, max_pressure_ratio, min_flow_kgs, max_flow_kgs, performance_map_data)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(model) DO UPDATE SET
                    manufacturer = excluded.manufacturer,
                    max_pressure_ratio = excluded.max_pressure_ratio,
                    min_flow_kgs = excluded.min_flow_kgs,
                    max_flow_kgs = excluded.max_flow_kgs,
                    performance_map_data = excluded.performance_map_data
            """, (
                compressor_data['manufacturer'],
                compressor_data['model'],
                compressor_data['max_pressure_ratio'],
                compressor_data['min_flow_kgs'],
                compressor_data['max_flow_kgs'],
                map_data_str
            ))
            
            self.get_connection().commit()
            self.invalidate_catalog_cache()
            return True
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Kompresör ekleme hatası: {e}")
            return False
    
    def delete_compressor(self, compressor_id):
        """Kompresör sil"""
        try:
            cursor = self.get_cursor()
            cursor.execute("DELETE FROM Compressors WHERE id = ?", (compressor_id,))
            self.get_connection().commit()
            self.invalidate_catalog_cache()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Kompresör silme hatası: {e}")
            return False
    
    def save_calculation_history(self, project_name, calculation_type, inputs, results, notes=""):
        """Hesaplama geçmişini kaydet"""
        try:
            cursor = self.get_cursor()
            
            inputs_json = json.dumps(inputs) if isinstance(inputs, dict) else str(inputs)
            results_json = json.dumps(results) if isinstance(results, dict) else str(results)
            
            cursor.execute("""
                INSERT INTO CalculationHistory (project_name, calculation_type, inputs_json, results_json, user_notes)
                VALUES (?, ?, ?, ?, ?)
            """, (project_name, calculation_type, inputs_json, results_json, notes))
            
            self.get_connection().commit()
            return True
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Geçmiş kaydetme hatası: {e}")
            return False
    
    def get_calculation_history(self, limit=50):
        """Hesaplama geçmişini getir"""
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM CalculationHistory ORDER BY calculation_date DESC LIMIT ?", (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append(dict(row))
            return history
        except sqlite3.Error as e:
            self.logger.error(f"Geçmiş getirme hatası: {e}")
            return []

    # ─────────────────────── Kullanıcı Yönetimi ───────────────────────

    def _is_users_table_empty(self):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM Users")
            return cursor.fetchone()[0] == 0
        except sqlite3.OperationalError:
            return True

    def create_default_admin(self, password_hash):
        if not self._is_users_table_empty():
            return
        try:
            cursor = self.get_cursor()
            cursor.execute("""
                INSERT INTO Users (username, password_hash, role, full_name, must_change_password)
                VALUES (?, ?, ?, ?, 1)
            """, ("admin", password_hash, "admin", "System Admin"))
            self.get_connection().commit()
            self.logger.info("Varsayılan admin kullanıcısı oluşturuldu (şifre değiştirme zorunlu).")
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Admin oluşturma hatası: {e}")

    def ensure_default_admin_must_change_password(self, default_password_hash=None):
        """Mevcut admin'in must_change_password=1 olmasi gerekiyorsa ayarlar.

        DEFAULT_PASSWORD kalktigi icin (P4-6), admin varsa ve must_change_password
        henuz ayarlanmamissa, bunu zorunlu hale getirir. Bu, ilk kurulumda
        rastgele olusturulan parolanin degistirilmesini saglar.
        """
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT password_hash, must_change_password FROM Users WHERE username = 'admin'")
            row = cursor.fetchone()
            if not row or row["must_change_password"]:
                return
            # Sabit default parola kalktigi icin (P4-6), her admin icin zorunlu degistirme
            cursor.execute("UPDATE Users SET must_change_password = 1 WHERE username = 'admin'")
            self.get_connection().commit()
            self.logger.info("Mevcut admin kullanıcısı için şifre değiştirme zorunlu hale getirildi (P4-6).")
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Admin şifre politikası güncelleme hatası: {e}")

    def get_user_by_username(self, username):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM Users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı getirme hatası: {e}")
            return None

    def get_all_users(self):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM Users ORDER BY username")
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı listesi hatası: {e}")
            return []

    def create_user(self, username, password_hash, role="user", full_name="", email=""):
        try:
            cursor = self.get_cursor()
            cursor.execute("""
                INSERT INTO Users (username, password_hash, role, full_name, email)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password_hash, role, full_name, email))
            self.get_connection().commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            return None
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Kullanıcı ekleme hatası: {e}")
            return None

    def update_user(self, user_id, **kwargs):
        allowed = {
            "role", "full_name", "email", "is_active", "password_hash",
            "must_change_password", "security_question", "security_answer_hash",
            "recovery_key_hash"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        try:
            cursor = self.get_cursor()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [user_id]
            cursor.execute(f"UPDATE Users SET {set_clause} WHERE id = ?", values)
            self.get_connection().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Kullanıcı güncelleme hatası: {e}")
            return False

    def update_user_login(self, user_id):
        try:
            cursor = self.get_cursor()
            cursor.execute("UPDATE Users SET last_login = datetime('now') WHERE id = ?", (user_id,))
            self.get_connection().commit()
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Login güncelleme hatası: {e}")

    def delete_user(self, user_id):
        try:
            cursor = self.get_cursor()
            cursor.execute("DELETE FROM Users WHERE id = ?", (user_id,))
            self.get_connection().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            try:
                self.get_connection().rollback()
            except sqlite3.Error:
                pass
            self.logger.error(f"Kullanıcı silme hatası: {e}")
            return False
