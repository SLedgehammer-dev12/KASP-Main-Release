import pytest
from kasp.i18n import tr, set_language
from kasp.utils.workers import CalculationWorker

class _MockEngine:
    def calculate_design_performance_with_mode(self, inputs):
        return {"power_motor_per_unit_kw": 1000.0}
    def select_units(self, power, site, data, limit=5):
        return []

def test_progress_messages_localized_turkish():
    set_language("tr")
    worker = CalculationWorker(_MockEngine(), {}, [])
    captured = []
    worker.progress_detailed.connect(lambda pct, msg: captured.append((pct, msg)))

    worker._run_body()

    assert len(captured) >= 10
    for pct, msg in captured:
        # Must not contain untranslated English progress strings
        assert "Validating inputs" not in msg, f"Untranslated English found in TR mode: {msg}"
        assert "Calculating power" not in msg, f"Untranslated English found in TR mode: {msg}"
        assert "Calculation complete" not in msg, f"Untranslated English found in TR mode: {msg}"

def test_progress_messages_localized_english():
    set_language("en")
    worker = CalculationWorker(_MockEngine(), {}, [])
    captured = []
    worker.progress_detailed.connect(lambda pct, msg: captured.append((pct, msg)))

    worker._run_body()

    assert len(captured) >= 10
    for pct, msg in captured:
        # Must not contain untranslated Turkish progress strings
        assert "Hesaplamalar başlıyor" not in msg, f"Untranslated Turkish found in EN mode: {msg}"
        assert "özellikler hesaplanıyor" not in msg, f"Untranslated Turkish found in EN mode: {msg}"
        assert "motoru çalıştırılıyor" not in msg, f"Untranslated Turkish found in EN mode: {msg}"
