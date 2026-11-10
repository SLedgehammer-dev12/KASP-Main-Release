import os
import tempfile
import sqlite3
import pytest
from kasp.data.database import UnitDatabase


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = UnitDatabase(db_name=path)
    yield db
    db.close()
    if os.path.exists(path):
        os.remove(path)


def test_foreign_keys_pragma_enabled(temp_db):
    """PRAGMA foreign_keys must be active on every database connection."""
    conn = temp_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    row = cursor.fetchone()
    # row[0] is 1 if ON, 0 if OFF
    assert row is not None and row[0] == 1, f"Expected foreign_keys=1, got {row[0] if row else None}"


def test_catalog_cache_deep_isolation(temp_db):
    """Mutating returned catalog data must not mutate the internal cache."""
    # First fetch populates the cache
    turbines_1 = temp_db.get_all_turbines_full_data()
    assert len(turbines_1) > 0

    first_turbine = turbines_1[0]
    # Ensure performance_correction_data exists
    if "performance_correction_data" not in first_turbine or not isinstance(first_turbine["performance_correction_data"], dict):
        first_turbine["performance_correction_data"] = {}

    # Mutate the nested dictionary in caller's copy
    first_turbine["performance_correction_data"]["__mutated_test_flag__"] = 99999

    # Second fetch must be completely clean and NOT contain __mutated_test_flag__
    turbines_2 = temp_db.get_all_turbines_full_data()
    assert "__mutated_test_flag__" not in turbines_2[0].get("performance_correction_data", {})


def test_compressor_cache_deep_isolation(temp_db):
    """Mutating returned compressor data must not mutate the internal cache."""
    compressors_1 = temp_db.get_all_compressors_full_data()
    assert len(compressors_1) > 0

    first_comp = compressors_1[0]
    if "performance_map_data" not in first_comp or not isinstance(first_comp["performance_map_data"], dict):
        first_comp["performance_map_data"] = {}

    first_comp["performance_map_data"]["__mutated_test_flag__"] = 88888

    compressors_2 = temp_db.get_all_compressors_full_data()
    assert "__mutated_test_flag__" not in compressors_2[0].get("performance_map_data", {})
