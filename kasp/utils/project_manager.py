"""
KASP V4 - Project Manager
Proje kaydetme ve yükleme işlevleri
"""

import json
import datetime
import logging
from pathlib import Path

class ProjectManager:
    """Proje dosyalarını kaydetme ve yükleme yöneticisi"""
    
    VERSION = "4.0"
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def save_project(self, filepath, inputs, results=None):
        """
        Projeyi JSON formatında kaydeder
        
        Args:
            filepath: Kayıt dosya yolu (.kasp)
            inputs: Kullanıcı girdileri dictionary
            results: Hesaplama sonuçları (opsiyonel)
        """
        try:
            project_data = {
                'version': self.VERSION,
                'timestamp': datetime.datetime.now().isoformat(),
                'inputs': {
                    # Proje bilgileri
                    'project_name': inputs.get('project_name', ''),
                    'notes': inputs.get('notes', ''),
                    
                    # Proses koşulları
                    'p_in': inputs.get('p_in', ''),
                    'p_in_unit': inputs.get('p_in_unit', 'bar(g)'),
                    't_in': inputs.get('t_in', ''),
                    't_in_unit': inputs.get('t_in_unit', '°C'),
                    'p_out': inputs.get('p_out', ''),
                    'p_out_unit': inputs.get('p_out_unit', 'bar(a)'),
                    'flow': inputs.get('flow', ''),
                    'flow_unit': inputs.get('flow_unit', 'Sm³/h'),
                    'num_units': inputs.get('num_units', 1),
                    
                    # Gaz kompozisyonu
                    'gas_comp': inputs.get('gas_comp', {}),
                    
                    # Hesaplama parametreleri
                    'eos_method': inputs.get('eos_method', 'coolprop'),
                    'method': inputs.get('method', 'Metot 1: Ortalama Özellikler'),
                    'poly_eff': inputs.get('poly_eff', 90.0),
                    'therm_eff': inputs.get('therm_eff', 35.0),
                    'mech_eff': inputs.get('mech_eff', 98.0),
                    
                    # Tutarlılık modu ayarları
                    'use_consistency_iteration': inputs.get('use_consistency_iteration', False),
                    'max_consistency_iter': inputs.get('max_consistency_iter', 20),
                    'consistency_tolerance': inputs.get('consistency_tolerance', 0.1),
                    
                    # Site koşulları
                    'ambient_temp': inputs.get('ambient_temp', 15.0),
                    'ambient_press': inputs.get('ambient_press', 1013),
                    'altitude': inputs.get('altitude', 0),
                    'humidity': inputs.get('humidity', 60)
                },
                'results': results if results else None
            }
            
            # JSON olarak kaydet
            filepath = Path(filepath)
            if not filepath.suffix:
                filepath = filepath.with_suffix('.kasp')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Proje kaydedildi: {filepath}")
            return True, str(filepath)
            
        except Exception as e:
            self.logger.error(f"Proje kaydetme hatası: {e}", exc_info=True)
            return False, str(e)
    
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
            
            # Versiyon kontrolü
            if project_data.get('version') != self.VERSION:
                self.logger.warning(
                    f"Farklı versiyon: {project_data.get('version')} "
                    f"(Mevcut: {self.VERSION})"
                )
            
            inputs = project_data.get('inputs', {})
            results = project_data.get('results')
            
            self.logger.info(f"Proje yüklendi: {filepath}")
            return True, inputs, results
            
        except Exception as e:
            self.logger.error(f"Proje yükleme hatası: {e}", exc_info=True)
            return False, None, None
