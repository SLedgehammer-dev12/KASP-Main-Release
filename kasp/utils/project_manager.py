"""
KASP V4 - Project Manager
Proje kaydetme ve yükleme işlevleri
"""

import json
import datetime
import logging
import os
import tempfile
import math
from pathlib import Path


def sanitize_json_payload(obj):
    """Recursively convert NaN/Inf to None, numpy types to Python primitives, dates to ISO strings."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): sanitize_json_payload(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json_payload(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return [sanitize_json_payload(v) for v in obj]
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return sanitize_json_payload(obj.item())
        except (TypeError, ValueError):
            pass
    if hasattr(obj, "tolist") and callable(obj.tolist):
        try:
            return sanitize_json_payload(obj.tolist())
        except (TypeError, ValueError):
            pass
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def _json_default_serializer(obj):
    """Serialize numpy types, dates, sets, and arbitrary objects to JSON-friendly primitives."""
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    return str(obj)


_LEGACY_EOS_MIGRATION = {
    "rk": "srk",
    "redlich-kwong": "srk",
    "vdw": "pr",
    "van_der_waals": "pr",
    "bwrs": "gerg2008",
    "peng-robinson": "pr",
    "gerg-2008": "gerg2008",
    "aga8-dc92": "aga8",
    "heos": "coolprop",
}


def normalize_project_inputs_cross_platform(inputs: dict | None) -> dict:
    """Masaüstü (eos_method, method, ambient_temp) ve Web (eos_model, calc_method, t_amb)
    girdi anahtarlarını çift yönlü senkronize eder ve eski EOS kısaltmalarını günceller."""
    if not isinstance(inputs, dict):
        return {}
    synced = dict(inputs)

    raw_eos = synced.get("eos_method") or synced.get("eos_model")
    if raw_eos:
        eos_clean = str(raw_eos).strip().lower()
        eos_norm = _LEGACY_EOS_MIGRATION.get(eos_clean, eos_clean)
        synced["eos_method"] = eos_norm
        synced["eos_model"] = eos_norm

    raw_method = synced.get("method") or synced.get("calc_method")
    if raw_method:
        method_str = str(raw_method).strip()
        synced["method"] = method_str
        synced["calc_method"] = method_str

    if synced.get("ambient_temp") is None and synced.get("t_amb") is not None:
        synced["ambient_temp"] = synced["t_amb"]

    return synced


class ProjectManager:
    """Proje dosyalarını kaydetme ve yükleme yöneticisi"""
    
    VERSION = "4.1"
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_error = None
    
    def save_project(
        self,
        filepath,
        inputs,
        results=None,
        modules=None,
        station_data=None,
        selected_units=None,
        charts=None,
        warnings=None,
    ):
        """
        Projeyi JSON formatında kaydeder
        
        Args:
            filepath: Kayıt dosya yolu (.kasp)
            inputs: Kullanıcı girdileri dictionary
            results: Hesaplama sonuçları (opsiyonel)
            modules: Entegrasyon modülü sonuçları (opsiyonel)
            station_data: İstasyon modeli sonuçları (opsiyonel)
            selected_units: Eşleşen türbin modelleri listesi (opsiyonel)
            charts: Plotly grafik verileri (opsiyonel)
            warnings: Hesaplama ve doğrulama uyarıları (opsiyonel)
        """
        try:
            src_inp = normalize_project_inputs_cross_platform(inputs or {})
            eos_val = src_inp.get('eos_method') or src_inp.get('eos_model') or 'coolprop'
            method_val = src_inp.get('method') or src_inp.get('calc_method') or 'Metot 1: Ortalama Özellikler'
            amb_temp_val = src_inp.get('ambient_temp', src_inp.get('t_amb', 15.0))

            merged_inputs = dict(src_inp)
            merged_inputs.update({
                # Proje bilgileri
                'project_name': src_inp.get('project_name', ''),
                'notes': src_inp.get('notes', ''),
                
                # Proses koşulları
                'p_in': src_inp.get('p_in', ''),
                'p_in_unit': src_inp.get('p_in_unit', 'bar(g)'),
                't_in': src_inp.get('t_in', ''),
                't_in_unit': src_inp.get('t_in_unit', '°C'),
                'p_out': src_inp.get('p_out', ''),
                'p_out_unit': src_inp.get('p_out_unit', 'bar(a)'),
                'flow': src_inp.get('flow', ''),
                'flow_unit': src_inp.get('flow_unit', 'Sm³/h'),
                'num_units': src_inp.get('num_units', 1),
                'num_stages': src_inp.get('num_stages', 1),
                
                # Gaz kompozisyonu ve ikili etkileşim
                'gas_comp': src_inp.get('gas_comp', {}),
                'fuel_gas_comp': src_inp.get('fuel_gas_comp', {}),
                'custom_kij': src_inp.get('custom_kij', {}),
                
                # Hesaplama parametreleri (Masaüstü + Web ortak anahtarlar)
                'eos_method': eos_val,
                'eos_model': eos_val,
                'solver_method': src_inp.get('solver_method', 'auto'),
                'method': method_val,
                'calc_method': method_val,
                'poly_eff': src_inp.get('poly_eff', 90.0),
                'therm_eff': src_inp.get('therm_eff', 35.0),
                'mech_eff': src_inp.get('mech_eff', 98.0),
                'lhv_source': src_inp.get('lhv_source', 'kasp'),
                
                # Tutarlılık modu ayarları
                'use_consistency_iteration': src_inp.get('use_consistency_iteration', False),
                'max_consistency_iter': src_inp.get('max_consistency_iter', 20),
                'consistency_tolerance': src_inp.get('consistency_tolerance', 0.1),
                
                # Ara soğutucu
                'intercooler_t': src_inp.get('intercooler_t', 40.0),
                'intercooler_dp_pct': src_inp.get('intercooler_dp_pct', 2.0),
                
                # Site düzeltmeleri ve saha koşulları
                'site_correction_inputs': src_inp.get('site_correction_inputs', {}),
                'ambient_temp': amb_temp_val,
                'ambient_pressure': src_inp.get('ambient_pressure', 101.325),
                'ambient_press': src_inp.get('ambient_press', 1013),
                'altitude': src_inp.get('altitude', 0),
                'humidity': src_inp.get('humidity', 60),
            })

            project_data = {
                'schema_version': self.VERSION,
                'timestamp': datetime.datetime.now().isoformat(),
                'inputs': merged_inputs,
                'results': results if results else None,
                'modules': modules or {},
                'station_data': station_data,
                'selected_units': selected_units,
                'charts': charts,
                'warnings': warnings,
            }
            
            # JSON olarak atomik kaydet
            project_data = sanitize_json_payload(project_data)
            filepath = Path(filepath)
            if not filepath.suffix:
                filepath = filepath.with_suffix('.kasp')
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    dir=str(filepath.parent),
                    prefix=filepath.stem + '_',
                    suffix='.tmp',
                    delete=False,
                ) as f:
                    tmp_path = f.name
                    json.dump(project_data, f, indent=2, ensure_ascii=False, default=_json_default_serializer)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, str(filepath))
            except Exception:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                raise
            
            self.last_error = None
            self.logger.info(f"Proje kaydedildi: {filepath}")
            return True, str(filepath)
            
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"Proje kaydetme hatası: {e}", exc_info=True)
            return False, str(e)
    
    def _migrate_project_schema(self, project_data: dict) -> dict:
        """Eski şema sürümlerini güncel sürüme yükseltir."""
        schema_version = str(project_data.get('schema_version', project_data.get('version', '1.0')))
        
        if schema_version != self.VERSION:
            try:
                major = int(schema_version.split('.')[0])
                curr_major = int(self.VERSION.split('.')[0])
            except ValueError:
                major, curr_major = 1, 4
            if major > curr_major:
                self.logger.warning(
                    f"Proje şeması mevcut sürümden daha yeni ({schema_version} > {self.VERSION}); "
                    "bazı alanlar tam desteklenmeyebilir."
                )
                return project_data

            # Schema version 1.x / 2.x / 3.x / 4.0 -> 4.1 migration
            self.logger.info(f"Proje şeması yükseltiliyor: {schema_version} -> {self.VERSION}")
            inputs = project_data.setdefault('inputs', {})
            
            # Eksik alanları varsayılanlarla doldur
            defaults = {
                'num_stages': 1,
                'intercooler_t': 40.0,
                'intercooler_dp_pct': 2.0,
                'lhv_source': 'kasp',
                'fuel_gas_comp': {},
                'site_correction_inputs': {},
                'ambient_pressure': 101.325,
                'solver_method': 'auto',
            }
            for key, default_val in defaults.items():
                if key not in inputs:
                    inputs[key] = default_val
            
            project_data['schema_version'] = self.VERSION

        if isinstance(project_data.get('inputs'), dict):
            project_data['inputs'] = normalize_project_inputs_cross_platform(project_data['inputs'])

        # Integration module schemas are versioned independently from the
        # project schema, so migrate them even when the project is current.
        try:
            from kasp.integrations.schema import migrate_modules_payload, migrate_results_payload

            if isinstance(project_data.get("modules"), dict):
                project_data["modules"] = migrate_modules_payload(project_data.get("modules"))
            if isinstance(project_data.get("results"), dict):
                project_data["results"] = migrate_results_payload(project_data.get("results"))
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warning("Modül şema migrasyonu atlandı: %s", exc)

        return project_data
    
    def load_project(self, filepath):
        """
        Proje dosyasını yükler
        
        Args:
            filepath: Proje dosya yolu (.kasp)
            
        Returns:
            (success, inputs, results) tuple
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                raise FileNotFoundError(f"Dosya bulunamadı: {filepath}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Şema migrasyonu
            project_data = self._migrate_project_schema(project_data)
            
            inputs = project_data.get('inputs', {})
            results = project_data.get('results')
            modules = project_data.get('modules')
            station_data = project_data.get('station_data')
            selected_units = project_data.get('selected_units')
            charts = project_data.get('charts')
            warnings = project_data.get('warnings')
            if modules or station_data or selected_units or charts or warnings:
                results = dict(results or {})
                if modules:
                    results.setdefault('module_results', modules)
                if station_data:
                    results.setdefault('station_data', station_data)
                if selected_units is not None:
                    results.setdefault('selected_units', selected_units)
                if charts is not None:
                    results.setdefault('charts', charts)
                if warnings is not None:
                    results.setdefault('warnings', warnings)
            
            self.last_error = None
            self.logger.info(f"Proje yüklendi: {filepath}")
            return True, inputs, results
            
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"Proje yükleme hatası: {e}", exc_info=True)
            return False, None, None
