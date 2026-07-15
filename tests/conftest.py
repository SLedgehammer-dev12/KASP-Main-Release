"""
KASP Test Suite (v2.1)

Shared fixtures and configuration for all test categories.

Usage:
    pytest tests/ -v                          # all tests
    pytest tests/unit/ -v                     # unit tests only
    pytest tests/ -v -m "not slow"            # skip slow tests
    pytest tests/validation/ -v -m validation # validation only
"""

import os
import sys
import tempfile
import pytest

# Add project root to Python path for test discovery
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ── Session fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def methane_inputs():
    """Standard methane design inputs for integration tests."""
    return {
        'project_name': 'Test Methane',
        'p_in': 1.0, 'p_in_unit': 'bar(a)',
        't_in': 25.0, 't_in_unit': 'Â°C',
        'p_out': 3.0, 'p_out_unit': 'bar(a)',
        'flow': 10.0, 'flow_unit': 'kg/s',
        'gas_comp': {'METHANE': 100.0},
        'eos_method': 'coolprop',
        'method': 'Metot 3: ArtÄ±mlÄ± BasÄ±nÃ§',
        'poly_eff': 82.0, 'mech_eff': 98.0, 'therm_eff': 35.0,
        'num_units': 1, 'num_stages': 1,
        'intercooler_t': 40.0, 'intercooler_dp_pct': 2.0,
        'consistency_check': False,
    }


@pytest.fixture(scope="session")
def thermo_engine():
    from kasp.core.thermo import ThermoEngine
    return ThermoEngine()


# ── Function fixtures ────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    """Temporary database for each test."""
    import uuid
    db_name = f"test_kasp_{uuid.uuid4().hex[:8]}.db"
    db_path = os.path.join(os.getcwd(), db_name)
    from kasp.data.database import UnitDatabase
    db = UnitDatabase(db_path)
    yield db
    db.close()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture
def methane_coolprop_str():
    from kasp.core.mixture import GasMixtureBuilder
    builder = GasMixtureBuilder()
    normalized = builder.validate_and_normalize({'METHANE': 100.0})
    return builder.build_coolprop_string(normalized)


@pytest.fixture
def methane_gas_data():
    from kasp.core.mixture import GasMixtureBuilder
    builder = GasMixtureBuilder()
    normalized = builder.validate_and_normalize({'METHANE': 100.0})
    return builder.build_thermo_data(normalized)


# ── pytest configuration ─────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with -m 'not slow')")
    config.addinivalue_line("markers", "validation: thermodynamic validation tests")
    config.addinivalue_line("markers", "security: security-specific tests")
    config.addinivalue_line("markers", "e2e: end-to-end integration tests")


collect_ignore = []
