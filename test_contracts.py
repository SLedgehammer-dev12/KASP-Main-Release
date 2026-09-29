"""Birim testleri: kasp.core.contracts (P4-15).

Girdi/çıktı sözleşmeleri ve normalize fonksiyonlarini test eder.
"""

import pytest
from kasp.core.contracts import (
    normalize_design_inputs,
    get_design_input_defaults,
    build_project_payload,
)


class TestContracts:
    """Sözleşme fonksiyonlari testleri."""

    def test_normalize_design_inputs_none(self):
        """None girdisi icin varsayilanlari dondurmeli."""
        result = normalize_design_inputs(None)
        assert isinstance(result, dict)
        # Varsayilan anahtarlar
        assert 'ambient_temp' in result
        assert 'ambient_pressure' in result or 'ambient_press' in result

    def test_normalize_design_inputs_empty(self):
        """Bos dict icin varsayilanlari doldurmali."""
        result = normalize_design_inputs({})
        assert isinstance(result, dict)
        assert result.get('ambient_temp') is not None

    def test_normalize_mbar_to_kpa(self):
        """Legacy 'ambient_press' (mbar) -> 'ambient_pressure' (kPa) donusumu.
        
        normalize_design_inputs: ambient_press > 200 ise /10 yapar (mbar->kPa).
        """
        inputs = {'ambient_press': 1013.25}  # mbar cinsinden
        result = normalize_design_inputs(inputs)
        # ambient_press -> ambient_pressure donusumu, 1013.25/10 = 101.325
        assert 'ambient_pressure' in result
        assert abs(result['ambient_pressure'] - 101.325) < 0.1

    def test_normalize_preserves_kpa(self):
        """Zaten kPa olan 'ambient_pressure' korunmali."""
        inputs = {'ambient_pressure': 101.325}  # kPa
        result = normalize_design_inputs(inputs)
        assert abs(result['ambient_pressure'] - 101.325) < 0.01

    def test_get_design_input_defaults_structure(self):
        """Varsayilan girdi yapisi dogru olmali."""
        defaults = get_design_input_defaults()
        assert isinstance(defaults, dict)
        # Temel anahtarlar
        required = ['project_name', 'ambient_temp', 'ambient_pressure', 'p_in', 'p_out', 'flow']
        for key in required:
            assert key in defaults, f"Eksik anahtar: {key}"

    def test_build_project_payload(self):
        """Proje payload olusturma testi (version + timestamp gerekli)."""
        inputs = {'project_name': 'Test Proje', 'ambient_temp': 25.0}
        results = {'head_kj_kg': 180.0}
        payload = build_project_payload(inputs, results, version="1.0")
        
        assert 'version' in payload
        assert 'timestamp' in payload
        assert 'inputs' in payload
        assert 'results' in payload
        assert payload['inputs']['project_name'] == 'Test Proje'
        assert payload['results']['head_kj_kg'] == 180.0

    def test_normalize_unknown_keys_preserved(self):
        """Bilinmeyen anahtarlar korunmali (ileri uyumluluk)."""
        inputs = {'custom_field': 'test_value', 'p_in': 50}
        result = normalize_design_inputs(inputs)
        assert result.get('custom_field') == 'test_value'

    def test_normalize_none_values_dropped(self):
        """None degerli alanlar atlanmali."""
        inputs = {'p_in': 50, 'p_out': None}
        result = normalize_design_inputs(inputs)
        # p_out None oldugu icin varsayilan kullanilmali
        assert 'p_out' in result