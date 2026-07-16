"""
KASP Database — Repository Pattern (v2.1 refactor)

Bu modül UnitDatabase sınıfını ve onun alt repository'lerini içerir:
  - TurbineRepository: Türbin CRUD işlemleri
  - CompressorRepository: Kompresör CRUD işlemleri
  - UserRepository: Kullanıcı CRUD işlemleri
  - CalculationHistoryRepository: Hesaplama geçmişi
  - DatabaseMigrator: Şema migrasyonu

UnitDatabase, geriye dönük uyumluluk için tüm eski metod adlarını
__getattr__ ile repository'lere delege eder.
"""

import sqlite3
import json
import shutil
import sys
import threading
import logging
import os
from typing import Any, Dict, List, Optional

ALLOWED_TABLES = {"Turbines", "Compressors", "CalculationHistory", "Users"}
ALLOWED_COLUMN_TYPES = {
    "REAL DEFAULT 0", "REAL DEFAULT 10.0", "REAL DEFAULT 1000",
    "TEXT DEFAULT 'Natural Gas'", 'TEXT DEFAULT "Natural Gas"',
    "INTEGER DEFAULT 0",
    "TEXT DEFAULT ''", "TEXT",
}


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


class _BaseRepository:
    def __init__(self, db: "UnitDatabase"):
        self._db = db
        self.logger = logging.getLogger(self.__class__.__name__)

    def _cursor(self):
        return self._db.get_cursor()

    def _conn(self):
        return self._db.get_connection()


class TurbineRepository(_BaseRepository):
    def get_all_full_data(self) -> List[Dict[str, Any]]:
        try:
            cursor = self._cursor()
            cursor.execute("""
                SELECT *, 
                       json_extract(performance_correction_data, '$.temperature_correction') as temp_correction,
                       json_extract(performance_correction_data, '$.altitude_correction') as alt_correction
                FROM Turbines 
                ORDER BY manufacturer, iso_power_kw
            """)
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
            return turbines
        except sqlite3.Error as e:
            self.logger.error(f"Türbin verileri getirme hatası: {e}")
            return []

    def get_by_id(self, turbine_id: int) -> Optional[Dict[str, Any]]:
        try:
            cursor = self._cursor()
            cursor.execute("SELECT * FROM Turbines WHERE id = ?", (turbine_id,))
            row = cursor.fetchone()
            if row:
                turbine = dict(row)
                if turbine['performance_correction_data']:
                    turbine['performance_correction_data'] = json.loads(turbine['performance_correction_data'])
                turbine.pop('temp_correction', None)
                turbine.pop('alt_correction', None)
                return turbine
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Türbin getirme hatası: {e}")
            return None

    def add(self, turbine_data: Dict[str, Any]) -> bool:
        try:
            cursor = self._cursor()
            correction_data_str = turbine_data.get('performance_correction_data', '{}')
            if isinstance(correction_data_str, dict):
                correction_data_str = json.dumps(correction_data_str)
            cursor.execute("""
                INSERT OR REPLACE INTO Turbines 
                (manufacturer, model, type, iso_power_kw, iso_heat_rate_kj_kwh, 
                 performance_correction_data, surge_flow, stonewall_flow, max_pressure_ratio,
                 min_flow_kgs, max_flow_kgs, fuel_type)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                turbine_data['manufacturer'], turbine_data['model'], turbine_data['type'],
                turbine_data['iso_power_kw'], turbine_data['iso_heat_rate_kj_kwh'],
                correction_data_str, turbine_data.get('surge_flow', 0),
                turbine_data.get('stonewall_flow', 0), turbine_data.get('max_pressure_ratio', 10.0),
                turbine_data.get('min_flow_kgs', 0), turbine_data.get('max_flow_kgs', 1000),
                turbine_data.get('fuel_type', 'Natural Gas')
            ))
            self._conn().commit()
            self.logger.info(f"Türbin eklendi: {turbine_data['manufacturer']} {turbine_data['model']}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Türbin ekleme hatası: {e}")
            return False

    def update_correction_data(self, turbine_id: int, correction_data) -> bool:
        try:
            cursor = self._cursor()
            if isinstance(correction_data, dict):
                correction_data = json.dumps(correction_data)
            cursor.execute("""
                UPDATE Turbines SET performance_correction_data = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (correction_data, turbine_id))
            self._conn().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Türbin güncelleme hatası: {e}")
            return False

    def delete(self, turbine_id: int) -> bool:
        try:
            cursor = self._cursor()
            cursor.execute("DELETE FROM Turbines WHERE id = ?", (turbine_id,))
            self._conn().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Türbin silme hatası: {e}")
            return False

    def is_empty(self) -> bool:
        try:
            cursor = self._cursor()
            cursor.execute("SELECT COUNT(*) FROM Turbines")
            return cursor.fetchone()[0] == 0
        except sqlite3.OperationalError:
            return True

    def insert_sample_data(self, data_dir: str):
        turbines_path = os.path.join(data_dir, 'turbines.json')
        if not os.path.exists(turbines_path):
            self.logger.warning(f"Türbin veri dosyası bulunamadı: {turbines_path}")
            return
        with open(turbines_path, 'r', encoding='utf-8') as f:
            turbines = json.load(f)
        for t in turbines:
            self.add(t)


class CompressorRepository(_BaseRepository):
    def get_all_full_data(self) -> List[Dict[str, Any]]:
        try:
            cursor = self._cursor()
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
            return compressors
        except sqlite3.Error as e:
            self.logger.error(f"Kompresör verileri getirme hatası: {e}")
            return []

    def add(self, compressor_data: Dict[str, Any]) -> bool:
        try:
            cursor = self._cursor()
            map_data_str = compressor_data.get('performance_map_data', '{}')
            if isinstance(map_data_str, dict):
                map_data_str = json.dumps(map_data_str)
            cursor.execute("""
                INSERT OR REPLACE INTO Compressors 
                (manufacturer, model, max_pressure_ratio, min_flow_kgs, max_flow_kgs, performance_map_data)
                VALUES(?,?,?,?,?,?)
            """, (
                compressor_data['manufacturer'], compressor_data['model'],
                compressor_data['max_pressure_ratio'], compressor_data['min_flow_kgs'],
                compressor_data['max_flow_kgs'], map_data_str
            ))
            self._conn().commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Kompresör ekleme hatası: {e}")
            return False

    def delete(self, compressor_id: int) -> bool:
        try:
            cursor = self._cursor()
            cursor.execute("DELETE FROM Compressors WHERE id = ?", (compressor_id,))
            self._conn().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Kompresör silme hatası: {e}")
            return False

    def insert_sample_data(self, data_dir: str):
        compressors_path = os.path.join(data_dir, 'compressors.json')
        if not os.path.exists(compressors_path):
            self.logger.warning(f"Kompresör veri dosyası bulunamadı: {compressors_path}")
            return
        with open(compressors_path, 'r', encoding='utf-8') as f:
            compressors = json.load(f)
        for c in compressors:
            self.add(c)


class UserRepository(_BaseRepository):
    def is_empty(self) -> bool:
        try:
            cursor = self._cursor()
            cursor.execute("SELECT COUNT(*) FROM Users")
            return cursor.fetchone()[0] == 0
        except sqlite3.OperationalError:
            return True

    def create_default_admin(self, password_hash: str):
        if not self.is_empty():
            return
        try:
            cursor = self._cursor()
            cursor.execute("""
                INSERT INTO Users (username, password_hash, role, full_name)
                VALUES (?, ?, ?, ?)
            """, ("admin", password_hash, "admin", "System Admin"))
            self._conn().commit()
            self.logger.info("Varsayılan admin kullanıcısı oluşturuldu.")
        except sqlite3.Error as e:
            self.logger.error(f"Admin oluşturma hatası: {e}")

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = self._cursor()
            cursor.execute("SELECT * FROM Users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı getirme hatası: {e}")
            return None

    def get_all(self) -> List[Dict[str, Any]]:
        try:
            cursor = self._cursor()
            cursor.execute("SELECT * FROM Users ORDER BY username")
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı listesi hatası: {e}")
            return []

    def create(self, username: str, password_hash: str, role: str = "user",
               full_name: str = "", email: str = "") -> Optional[int]:
        try:
            cursor = self._cursor()
            cursor.execute("""
                INSERT INTO Users (username, password_hash, role, full_name, email)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password_hash, role, full_name, email))
            self._conn().commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı ekleme hatası: {e}")
            return None

    def update(self, user_id: int, **kwargs) -> bool:
        allowed = {"role", "full_name", "email", "is_active", "password_hash",
                    "must_change_password", "security_question", "security_answer_hash"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        try:
            cursor = self._cursor()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [user_id]
            cursor.execute(f"UPDATE Users SET {set_clause} WHERE id = ?", values)
            self._conn().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı güncelleme hatası: {e}")
            return False

    def update_login_time(self, user_id: int):
        try:
            cursor = self._cursor()
            cursor.execute("UPDATE Users SET last_login = datetime('now') WHERE id = ?", (user_id,))
            self._conn().commit()
        except sqlite3.Error as e:
            self.logger.error(f"Login güncelleme hatası: {e}")

    def delete(self, user_id: int) -> bool:
        try:
            cursor = self._cursor()
            cursor.execute("DELETE FROM Users WHERE id = ?", (user_id,))
            self._conn().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Kullanıcı silme hatası: {e}")
            return False


class CalculationHistoryRepository(_BaseRepository):
    @staticmethod
    def _serialize(value):
        if isinstance(value, dict):
            return {k: CalculationHistoryRepository._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [CalculationHistoryRepository._serialize(v) for v in value]
        if hasattr(value, '__dataclass_fields__'):
            return {
                k: CalculationHistoryRepository._serialize(v)
                for k, v in value.__dict__.items()
            }
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)

    def save(self, project_name: str, calculation_type: str,
             inputs, results, notes: str = "") -> bool:
        try:
            cursor = self._cursor()
            inputs_json = json.dumps(
                self._serialize(inputs) if isinstance(inputs, dict) else str(inputs)
            )
            results_json = json.dumps(
                self._serialize(results) if isinstance(results, dict) else str(results)
            )
            cursor.execute("""
                INSERT INTO CalculationHistory (project_name, calculation_type, inputs_json, results_json, user_notes)
                VALUES (?, ?, ?, ?, ?)
            """, (project_name, calculation_type, inputs_json, results_json, notes))
            self._conn().commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Geçmiş kaydetme hatası: {e}")
            return False

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            cursor = self._cursor()
            cursor.execute("SELECT * FROM CalculationHistory ORDER BY calculation_date DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Geçmiş getirme hatası: {e}")
            return []


class DatabaseMigrator:
    def __init__(self, db: "UnitDatabase"):
        self._db = db
        self.logger = logging.getLogger(self.__class__.__name__)

    def _add_column_if_not_exists(self, table_name: str, column_name: str, column_type: str) -> bool:
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Geçersiz tablo adı: {table_name}")
        if column_type not in ALLOWED_COLUMN_TYPES:
            raise ValueError(f"Geçersiz kolon tipi: {column_type}")
        cursor = self._db.get_cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            if column_name not in columns:
                self.logger.warning(
                    f"VT Şema Güncellemesi: {table_name}.{column_name} ekleniyor."
                )
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                self._db.get_connection().commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Kolon ekleme hatası ({table_name}.{column_name}): {e}")
            return False

    def run(self):
        self.logger.info("VT Şema Güncellemesi Başlatıldı...")
        self._add_column_if_not_exists('Turbines', 'surge_flow', 'REAL DEFAULT 0')
        self._add_column_if_not_exists('Turbines', 'stonewall_flow', 'REAL DEFAULT 0')
        self._add_column_if_not_exists('Turbines', 'max_pressure_ratio', 'REAL DEFAULT 10.0')
        self._add_column_if_not_exists('Turbines', 'min_flow_kgs', 'REAL DEFAULT 0')
        self._add_column_if_not_exists('Turbines', 'max_flow_kgs', 'REAL DEFAULT 1000')
        self._add_column_if_not_exists('Turbines', 'fuel_type', 'TEXT DEFAULT "Natural Gas"')
        self._add_column_if_not_exists('Users', 'must_change_password', 'INTEGER DEFAULT 0')
        self._add_column_if_not_exists('Users', 'security_question', "TEXT DEFAULT ''")
        self._add_column_if_not_exists('Users', 'security_answer_hash', "TEXT DEFAULT ''")
        self.logger.info("VT Şema Güncellemesi Tamamlandı.")


# ── UnitDatabase: Ana veritabanı sınıfı ──────────────────────────────────

class UnitDatabase:
    def __init__(self, db_name=None):
        self.db_name = db_name or _resolve_db_path()
        self._local = threading.local()
        self._closed = False
        self.logger = logging.getLogger(self.__class__.__name__)

        conn = self.get_connection()
        self._configure_performance(conn)
        self.create_tables()

        self.turbines = TurbineRepository(self)
        self.compressors = CompressorRepository(self)
        self.users = UserRepository(self)
        self.history = CalculationHistoryRepository(self)
        self.migrator = DatabaseMigrator(self)

        self.migrator.run()

        if self.turbines.is_empty():
            data_dir = os.path.dirname(__file__)
            self.turbines.insert_sample_data(data_dir)
            self.compressors.insert_sample_data(data_dir)
            self.logger.info("Örnek veriler veritabanına yüklendi.")

    def _configure_performance(self, conn):
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA cache_size=-10000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            self.logger.info("Veritabanı optimizasyonu uygulandı.")
        except sqlite3.Error as exc:
            self.logger.warning(f"DB optimizasyonu başarısız: {exc}")

    def close(self):
        if not self._closed and hasattr(self._local, 'conn'):
            try:
                self._local.conn.close()
                self._closed = True
            except sqlite3.Error:
                pass

    def get_connection(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_name, timeout=10)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def get_cursor(self):
        return self.get_connection().cursor()

    def create_tables(self):
        try:
            cursor = self.get_cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Turbines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer TEXT NOT NULL, model TEXT NOT NULL,
                    type TEXT NOT NULL, iso_power_kw REAL NOT NULL,
                    iso_heat_rate_kj_kwh REAL NOT NULL,
                    performance_correction_data TEXT,
                    surge_flow REAL DEFAULT 0, stonewall_flow REAL DEFAULT 0,
                    max_pressure_ratio REAL DEFAULT 10.0,
                    min_flow_kgs REAL DEFAULT 0, max_flow_kgs REAL DEFAULT 1000,
                    fuel_type TEXT DEFAULT 'Natural Gas',
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(manufacturer, model)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Compressors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer TEXT NOT NULL, model TEXT NOT NULL UNIQUE,
                    max_pressure_ratio REAL NOT NULL,
                    min_flow_kgs REAL NOT NULL, max_flow_kgs REAL NOT NULL,
                    performance_map_data TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CalculationHistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT, calculation_type TEXT,
                    inputs_json TEXT, results_json TEXT,
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    full_name TEXT DEFAULT '', email TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    must_change_password INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login TEXT
                )
            """)
            self.get_connection().commit()
            self.logger.info("Veritabanı tabloları başarıyla oluşturuldu.")
        except sqlite3.Error as e:
            self.logger.error(f"Tablo oluşturma hatası: {e}", exc_info=True)
            raise

    # ── Geriye dönük uyumluluk: eski metod adları ─────────────────────

    def _migrate_database_schema(self):
        self.migrator.run()

    def insert_sample_data(self):
        data_dir = os.path.dirname(__file__)
        self.turbines.insert_sample_data(data_dir)
        self.compressors.insert_sample_data(data_dir)

    def _is_turbine_table_empty(self):
        return self.turbines.is_empty()

    def _is_users_table_empty(self):
        return self.users.is_empty()

    def create_default_admin(self, password_hash):
        self.users.create_default_admin(password_hash)

    def get_user_by_username(self, username):
        return self.users.get_by_username(username)

    def get_all_users(self):
        return self.users.get_all()

    def create_user(self, username, password_hash, role="user", full_name="", email=""):
        return self.users.create(username, password_hash, role, full_name, email)

    def update_user(self, user_id, **kwargs):
        return self.users.update(user_id, **kwargs)

    def update_user_login(self, user_id):
        self.users.update_login_time(user_id)

    def delete_user(self, user_id):
        return self.users.delete(user_id)

    def get_all_turbines_full_data(self):
        return self.turbines.get_all_full_data()

    def get_all_compressors_full_data(self):
        return self.compressors.get_all_full_data()

    def get_turbine_by_id(self, turbine_id):
        return self.turbines.get_by_id(turbine_id)

    def add_turbine(self, turbine_data):
        return self.turbines.add(turbine_data)

    def update_turbine_correction_data(self, turbine_id, correction_data):
        return self.turbines.update_correction_data(turbine_id, correction_data)

    def delete_turbine(self, turbine_id):
        return self.turbines.delete(turbine_id)

    def add_compressor(self, compressor_data):
        return self.compressors.add(compressor_data)

    def delete_compressor(self, compressor_id):
        return self.compressors.delete(compressor_id)

    def save_calculation_history(self, project_name, calculation_type, inputs, results, notes=""):
        return self.history.save(project_name, calculation_type, inputs, results, notes)

    def get_calculation_history(self, limit=50):
        return self.history.get_recent(limit)
