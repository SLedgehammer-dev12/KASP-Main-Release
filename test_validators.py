"""Birim testleri: kasp.ui.validators (P4-15).

Girdi dogrulama fonksiyonlarini test eder.
Dönen deger: (is_valid: bool, error_message: str)
"""

import pytest
from kasp.ui.validators import (
    validate_pressure,
    validate_temperature,
    validate_flow,
    ValidationManager,
)


class TestValidators:
    """Dogrulama fonksiyonlari testleri - (bool, str) tuple doner."""

    # --- validate_pressure ---
    def test_validate_pressure_valid_bar(self):
        """Gecerli basinc (bar(a)) - (True, '') donmeli."""
        is_valid, msg = validate_pressure("50.0", {"unit": "bar(a)"})
        assert is_valid is True
        assert msg == ""

    def test_validate_pressure_valid_gauge(self):
        """Gecerli gauge basinc (bar(g))."""
        is_valid, msg = validate_pressure("2.0", {"unit": "bar(g)"})
        assert is_valid is True

    def test_validate_pressure_negative_gauge_allowed(self):
        """Gauge icin negatif degere izin veriliyor (limit -1.0 bar(g))."""
        is_valid, msg = validate_pressure("-0.5", {"unit": "bar(g)"})
        assert is_valid is True

    def test_validate_pressure_too_negative_gauge(self):
        """Gauge limiti altinda (-1.0 bar(g)) hata."""
        is_valid, msg = validate_pressure("-2.0", {"unit": "bar(g)"})
        assert is_valid is False
        assert "düşük" in msg or "min" in msg

    def test_validate_pressure_zero_absolute(self):
        """Mutlak basinca 0 gecersiz."""
        is_valid, msg = validate_pressure("0", {"unit": "bar(a)"})
        assert is_valid is False
        assert "0" in msg or "pozitif" in msg

    def test_validate_pressure_negative_absolute(self):
        """Mutlak basinca negatif gecersiz."""
        is_valid, msg = validate_pressure("-5", {"unit": "kPa"})
        assert is_valid is False

    def test_validate_pressure_empty(self):
        """Bos girdi icin hata."""
        is_valid, msg = validate_pressure("", {"unit": "bar(a)"})
        assert is_valid is False
        assert "zorunlu" in msg

    def test_validate_pressure_nonnumeric(self):
        """Sayisal olmayan girdi icin hata."""
        is_valid, msg = validate_pressure("abc", {"unit": "bar(a)"})
        assert is_valid is False
        assert "format" in msg

    # --- validate_temperature ---
    def test_validate_temperature_valid_celsius(self):
        """Gecerli sicaklik (°C)."""
        is_valid, msg = validate_temperature("30.0", {"unit": "°C"})
        assert is_valid is True
        assert msg == ""

    def test_validate_temperature_valid_kelvin(self):
        """Gecerli sicaklik (K)."""
        is_valid, msg = validate_temperature("303.15", {"unit": "K"})
        assert is_valid is True

    def test_validate_temperature_below_absolute_zero(self):
        """Mutlak sifir altinda hata (-273.15°C)."""
        is_valid, msg = validate_temperature("-300", {"unit": "°C"})
        assert is_valid is False

    def test_validate_temperature_zero_kelvin(self):
        """0 K -> uyarı (100 K altinda uyarı veriyor, hata degil)."""
        is_valid, msg = validate_temperature("0", {"unit": "K"})
        # Implementation: k_val < 100 icin uyarı, < 0 icin hata
        assert is_valid is True  # 0 K < 100 ama >= 0, uyarı ile gecerli
        assert "düşük" in msg

    # --- validate_flow ---
    def test_validate_flow_valid(self):
        """Gecerli debi."""
        is_valid, msg = validate_flow("1000.0", {"unit": "Sm³/h"})
        assert is_valid is True

    def test_validate_flow_negative(self):
        """Negatif debi icin hata."""
        is_valid, msg = validate_flow("-100", {"unit": "kg/h"})
        assert is_valid is False

    def test_validate_flow_zero(self):
        """Sifir debi gecersiz."""
        is_valid, msg = validate_flow("0", {"unit": "Sm³/h"})
        assert is_valid is False

    def test_validate_flow_empty(self):
        """Bos debi hata."""
        is_valid, msg = validate_flow("", {"unit": "kg/h"})
        assert is_valid is False


class TestValidationManager:
    """ValidationManager sinifi testleri."""

    def test_manager_creation(self):
        """Manager olusturma."""
        mgr = ValidationManager()
        assert mgr is not None

    def test_register_and_validate(self):
        """Alan kayit ve dogrulama."""
        mgr = ValidationManager()
        
        # ValidatedLineEdit kullan (mock yerine)
        from kasp.ui.validators import ValidatedLineEdit
        
        # ValidatedLineEdit QApplication gerektirir, bu yüzden test'i skip et
        pytest.skip("ValidatedLineEdit QApplication gerektirir; integration test icin uygun")

    def test_register_invalid_value(self):
        """Gecersiz deger icin hata donmeli."""
        pytest.skip("ValidatedLineEdit QApplication gerektirir; integration test icin uygun")