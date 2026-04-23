"""
KASP V4 - Project Manager
Proje kaydetme ve yükleme işlevleri
"""

import json
import logging
from pathlib import Path

from kasp.core.contracts import build_project_payload, normalize_design_inputs


class ProjectManager:
    """Proje dosyalarını kaydetme ve yükleme yöneticisi"""

    VERSION = "4.6"

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
            project_data = build_project_payload(inputs, results, version=self.VERSION)

            filepath = Path(filepath)
            if not filepath.suffix:
                filepath = filepath.with_suffix(".kasp")

            with open(filepath, "w", encoding="utf-8") as handle:
                json.dump(project_data, handle, indent=2, ensure_ascii=False)

            self.logger.info("Proje kaydedildi: %s", filepath)
            return True, str(filepath)

        except Exception as e:
            self.logger.error("Proje kaydetme hatası: %s", e, exc_info=True)
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

            with open(filepath, "r", encoding="utf-8") as handle:
                project_data = json.load(handle)

            if project_data.get("version") != self.VERSION:
                self.logger.warning(
                    "Farklı versiyon: %s (Mevcut: %s)",
                    project_data.get("version"),
                    self.VERSION,
                )

            inputs = normalize_design_inputs(project_data.get("inputs", {}))
            results = project_data.get("results")

            self.logger.info("Proje yüklendi: %s", filepath)
            return True, inputs, results

        except Exception as e:
            self.logger.error("Proje yükleme hatası: %s", e, exc_info=True)
            return False, str(e), None
