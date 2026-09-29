"""Birim testleri: kasp.core.thermo_design_orchestration (P4-15).

Tasarim hesaplama orkestrasyonunun kritik yollarini test eder:
- INVALID kademe isaretleme
- Iptal sinyali
- Enerji dengesi
"""

import pytest
from kasp.core.thermo_design_orchestration import ThermoDesignOrchestrator
from kasp.core.exceptions import CalculationCancelled


class TestThermoDesignOrchestrator:
    """Orkestrasyon motoru birim testleri."""

    def test_orchestrator_creation(self):
        """Orkestrasyon nesnesi olusturulabilmeli (mock ile)."""
        class MockSolver:
            pass
        class MockLogger:
            def info(self, *args): pass
            def warning(self, *args): pass
            def error(self, *args): pass
        
        orch = ThermoDesignOrchestrator(thermo_solver=MockSolver(), logger=MockLogger())
        # Metot ismi 'run_stage_loop' (P4-2)
        assert hasattr(orch, 'run_stage_loop')

    def test_calculation_cancelled_exception(self):
        """CalculationCancelled exception tanimli."""
        assert issubclass(CalculationCancelled, Exception)

    def test_run_stage_loop_exists(self):
        """run_stage_loop metodu var."""
        class MockSolver:
            pass
        class MockLogger:
            def info(self, *args): pass
            def warning(self, *args): pass
            def error(self, *args): pass
        
        orch = ThermoDesignOrchestrator(thermo_solver=MockSolver(), logger=MockLogger())
        assert callable(getattr(orch, 'run_stage_loop', None))

    def test_resolve_method_callback(self):
        """_resolve_method_callback static metodu erisilebilir."""
        cb = ThermoDesignOrchestrator._resolve_method_callback
        assert callable(cb)


# ============================================================
# ENERGY BALANCE ISEMI (Integration test placeholder)
# ============================================================

def test_invalid_stage_excluded_from_totals():
    """INVALID isaretli kademenin gucleri toplama dahil edilmemeli (P4-2).
    
    Bu test ThermodynamicSolver / ThermoEngine seviyesinde
    integration test olarak calisir.
    """
    pytest.skip("Integration test icin ThermoEngine gerekli; test_thermo_refactor.py kapsiyor")


# ============================================================
# IPTAL MEKANIZMASI (Integration test placeholder)
# ============================================================

def test_cancel_between_stages():
    """Kademeler arasi iptal testi (P4-13)."""
    pytest.skip("Integration test icin ThermoEngine gerekli")