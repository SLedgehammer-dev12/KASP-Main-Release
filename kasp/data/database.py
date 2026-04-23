import sqlite3
import json
import threading
import logging
import os

COMPRESSOR_FLOW_DISPLAY_FACTOR = 3600.0


def compressor_flow_kgh_to_kgs(value):
    """Convert compressor library flow values from kg/h to kg/s for storage."""
    return float(value) / COMPRESSOR_FLOW_DISPLAY_FACTOR


def compressor_flow_kgs_to_kgh(value):
    """Convert compressor library flow values from stored kg/s to UI-friendly kg/h."""
    return float(value) * COMPRESSOR_FLOW_DISPLAY_FACTOR

class UnitDatabase:
    def __init__(self, db_name="kasp_database.db"):
        self.db_name = db_name
        self._local = threading.local()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.create_tables()
        self._migrate_database_schema()
        # Only insert sample data if tables are empty (avoid redundant I/O on every startup)
        if self._is_turbine_table_empty():
            self.insert_sample_data()
    
    def get_connection(self):
        """Thread-safe bağlantı oluştur"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def get_cursor(self):
        """Thread-safe cursor döndür"""
        conn = self.get_connection()
        return conn.cursor()
    
    def _is_turbine_table_empty(self):
        """Check if turbines table exists and has data"""
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM Turbines")
            count = cursor.fetchone()[0]
            return count == 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return True
    
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
            
            self.get_connection().commit()
            self.logger.info("Veritabanı tabloları başarıyla oluşturuldu.")
            
        except sqlite3.Error as e:
            self.logger.error(f"Tablo oluşturma hatası: {e}", exc_info=True)
            raise

    def _add_column_if_not_exists(self, table_name, column_name, column_type):
        """Eksik kolonu tabloya ekler"""
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
        
        self.logger.info("VT Şema Güncellemesi Tamamlandı.")
    
    def insert_sample_data(self):
        """JSON dosyalarından örnek verileri yükle"""
        try:
            cursor = self.get_cursor()
            
            # Turbines
            turbines_path = os.path.join(os.path.dirname(__file__), 'turbines.json')
            if os.path.exists(turbines_path):
                with open(turbines_path, 'r', encoding='utf-8') as f:
                    turbines = json.load(f)
                
                for t in turbines:
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
                with open(compressors_path, 'r', encoding='utf-8') as f:
                    compressors = json.load(f)
                
                for c in compressors:
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
            self.logger.info("Örnek veriler veritabanına yüklendi.")
            
        except Exception as e:
            self.logger.error(f"Örnek veri ekleme hatası: {e}", exc_info=True)
    
    def get_all_turbines_full_data(self):
        """Tüm türbin verilerini getir"""
        try:
            cursor = self.get_cursor()
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
    
    def get_all_compressors_full_data(self):
        """Tüm kompresör verilerini getir"""
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
            
            return compressors
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
                    turbine['performance_correction_data'] = json.loads(turbine['performance_correction_data'])
                
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
                INSERT OR REPLACE INTO Turbines 
                (manufacturer, model, type, iso_power_kw, iso_heat_rate_kj_kwh, 
                 performance_correction_data, surge_flow, stonewall_flow, max_pressure_ratio,
                 min_flow_kgs, max_flow_kgs, fuel_type)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
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
            self.logger.info(f"Türbin eklendi: {turbine_data['manufacturer']} {turbine_data['model']}")
            return True
        except sqlite3.Error as e:
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
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Türbin güncelleme hatası: {e}")
            return False
    
    def delete_turbine(self, turbine_id):
        """Türbin sil"""
        try:
            cursor = self.get_cursor()
            cursor.execute("DELETE FROM Turbines WHERE id = ?", (turbine_id,))
            self.get_connection().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
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
                INSERT OR REPLACE INTO Compressors 
                (manufacturer, model, max_pressure_ratio, min_flow_kgs, max_flow_kgs, performance_map_data)
                VALUES(?,?,?,?,?,?)
            """, (
                compressor_data['manufacturer'],
                compressor_data['model'],
                compressor_data['max_pressure_ratio'],
                compressor_data['min_flow_kgs'],
                compressor_data['max_flow_kgs'],
                map_data_str
            ))
            
            self.get_connection().commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Kompresör ekleme hatası: {e}")
            return False
    
    def delete_compressor(self, compressor_id):
        """Kompresör sil"""
        try:
            cursor = self.get_cursor()
            cursor.execute("DELETE FROM Compressors WHERE id = ?", (compressor_id,))
            self.get_connection().commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
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
