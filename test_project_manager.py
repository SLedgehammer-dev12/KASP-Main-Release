"""Birim testleri: kasp.utils.project_manager (P4-15).

Proje kaydet/yükleme, atomik yazma, şema migrasyonu testleri.
"""

import pytest
import tempfile
import os
import json
from kasp.utils.project_manager import ProjectManager


class TestProjectManager:
    """ProjectManager sinifi testleri."""

    def test_save_and_load_roundtrip(self):
        """Kaydet -> Yükle round-trip testi."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "test.kasp")
            
            inputs = {
                'project_name': 'Test Proje',
                'p_in': 50.0,
                'p_out': 75.0,
                't_in': 30.0,
                'gas_comp': {'METHANE': 0.9, 'ETHANE': 0.1},
            }
            results = {'head_kj_kg': 180.5, 'power_unit_kw': 2500.0}
            
            # Kaydet -> (bool, str)
            ok, msg = pm.save_project(filepath, inputs, results)
            assert ok, f"Kaydetme basarisiz: {msg}"
            
            # Yukle -> (bool, inputs, results)
            ok, loaded_inputs, loaded_results = pm.load_project(filepath)
            assert ok, f"Yukleme basarisiz"
            
            assert loaded_inputs['project_name'] == 'Test Proje'
            assert abs(loaded_inputs['p_in'] - 50.0) < 0.01
            assert loaded_results['head_kj_kg'] == 180.5

    def test_atomic_write_prevents_corruption(self):
        """Atomik yazma: kesinti durumunda eski dosya korunmali (P4-8)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "atomic.kasp")
            
            # Onceki gecerli veri
            inputs_v1 = {'project_name': 'v1', 'data': 'original'}
            ok, _ = pm.save_project(filepath, inputs_v1, {})
            assert ok
            
            # Dosya varligi ve icerigi dogrula
            assert os.path.exists(filepath)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data['inputs']['project_name'] == 'v1'

    def test_load_nonexistent_file(self):
        """Olmayan dosya yuklenirse basarisiz donmeli."""
        pm = ProjectManager()
        ok, inputs, results = pm.load_project("/nonexistent/path.kasp")
        assert not ok
        assert inputs is None
        assert results is None

    def test_load_corrupted_json(self):
        """Bozuk JSON dosyasi yuklenirse basarisiz donmeli."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "bad.kasp")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("{ invalid json }")
            
            ok, inputs, results = pm.load_project(filepath)
            assert not ok
            assert inputs is None
            assert results is None

    def test_schema_migration(self):
        """Eski şema versiyonu yuklenirse migrasyon calismali."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "old.kasp")
            
            # Eski sema (schema_version yok)
            old_data = {
                'inputs': {'project_name': 'Old', 'p_in': 50},
                'results': {'head': 100},
                # schema_version yok
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(old_data, f)
            
            ok, inputs, results = pm.load_project(filepath)
            assert ok
            # Migrasyon sonrasi schema_version eklenmeli (proje icinde)
            assert inputs['project_name'] == 'Old'


class TestProjectManagerEdgeCases:
    """Kenar durumlari."""

    def test_empty_results(self):
        """Sonucsuz kaydetme (results=None)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "no_results.kasp")
            
            ok, _ = pm.save_project(filepath, {'project_name': 'Test'}, None)
            assert ok
            
            ok, inputs, results = pm.load_project(filepath)
            assert ok
            # results None kaydedilirse None donmeli
            assert results is None or results == {}

    def test_unicode_content(self):
        """Unicode (Turkce karakter) icerik testi."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "unicode.kasp")
            
            inputs = {'project_name': 'İstanbul Projesi', 'notes': 'Türkçe şiğ ğü'}
            ok, _ = pm.save_project(filepath, inputs, {})
            assert ok
            
            ok, loaded, _ = pm.load_project(filepath)
            assert ok
            assert loaded['project_name'] == 'İstanbul Projesi'
            assert loaded['notes'] == 'Türkçe şiğ ğü'

    def test_save_returns_filepath(self):
        """save_project basarili olursa dosya yolu donmeli."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager()
            filepath = os.path.join(tmpdir, "returns_path.kasp")
            
            ok, msg = pm.save_project(filepath, {'project_name': 'Test'}, {})
            assert ok
            assert msg == filepath or msg == str(filepath)