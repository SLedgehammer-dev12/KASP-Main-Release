import os
import json
import tempfile
import math
import numpy as np
import pytest

from kasp.utils.project_manager import ProjectManager


def test_save_project_sanitizes_nan_and_inf_to_valid_json():
    """ProjectManager.save_project must serialize NaN/Inf to valid RFC 8259 JSON (null)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProjectManager()
        filepath = os.path.join(tmpdir, "test_nan.kasp")

        inputs = {
            "project_name": "Test Nan Project",
            "p_in": float("nan"),
            "poly_eff": float("inf"),
            "intercooler_t": float("-inf"),
        }
        results = {
            "eff": np.nan,
            "head": [100.0, float("nan"), float("inf")],
            "nested": {
                "metric": float("nan"),
                "clean": 42.0,
            },
        }

        ok, out_path = pm.save_project(filepath, inputs, results)
        assert ok, f"Save failed: {out_path}"

        # Read raw text: must NOT contain bare NaN, Infinity or -Infinity
        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        assert "NaN" not in raw_text, "Found unquoted NaN in serialized JSON"
        assert "Infinity" not in raw_text, "Found unquoted Infinity in serialized JSON"

        # Loading with parse_constant that rejects non-standard JSON tokens
        def fail_constant(c):
            raise ValueError(f"Non-RFC JSON constant found: {c}")

        loaded_data = json.loads(raw_text, parse_constant=fail_constant)
        assert loaded_data["inputs"]["p_in"] is None
        assert loaded_data["inputs"]["poly_eff"] is None
        assert loaded_data["inputs"]["intercooler_t"] is None
        assert loaded_data["results"]["eff"] is None
        assert loaded_data["results"]["head"] == [100.0, None, None]
        assert loaded_data["results"]["nested"]["metric"] is None
        assert loaded_data["results"]["nested"]["clean"] == 42.0


def test_api_export_kasp_handles_numpy_and_nan():
    """export_kasp logic in projects router must not crash on NumPy types or produce invalid JSON."""
    from kasp.utils.project_manager import sanitize_json_payload

    payload = {
        "np_int": np.int64(42),
        "np_float": np.float64(3.14),
        "np_nan": np.nan,
        "np_array": np.array([1, 2, 3]),
        "py_nan": float("nan"),
    }

    sanitized = sanitize_json_payload(payload)
    # Must be safely serializable with standard json.dumps without error and without NaN
    raw_json = json.dumps(sanitized, ensure_ascii=False)
    assert "NaN" not in raw_json
    parsed = json.loads(raw_json)
    assert parsed["np_int"] == 42
    assert parsed["np_float"] == pytest.approx(3.14)
    assert parsed["np_nan"] is None
    assert parsed["np_array"] == [1, 2, 3]
    assert parsed["py_nan"] is None
