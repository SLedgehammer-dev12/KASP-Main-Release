import pytest
import math
import numpy as np
import json
from kasp.ui.document_workflows import (
    sanitize_project_basename,
    default_design_report_filename,
    default_results_export_filename,
    build_results_export_payload,
)


def test_sanitize_project_basename_strips_forbidden_filesystem_chars():
    """sanitize_project_basename must strip / \\ : * ? " < > | and control chars."""
    raw_name = "Project: Alpha / Test * 1 <Beta> ? | \"Unit\""
    sanitized = sanitize_project_basename(raw_name, "Fallback")

    # None of the forbidden chars should appear
    for forbidden in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        assert forbidden not in sanitized

    assert sanitized == "Project_Alpha_Test_1_Beta_Unit"


def test_sanitize_project_basename_empty_or_whitespace():
    """Empty, None, or only-forbidden chars must safely revert to fallback."""
    assert sanitize_project_basename("", "Default") == "Default"
    assert sanitize_project_basename(None, "Default") == "Default"
    assert sanitize_project_basename("   ", "Default") == "Default"
    assert sanitize_project_basename("///:::***", "Default") == "Default"


def test_build_results_export_payload_sanitizes_nan_inf_and_numpy():
    """Exported results payload must sanitize NaN/Inf to None (RFC 8259 compliant JSON)."""
    inputs = {"p_in": 50.0}
    results = {
        "eff": float("nan"),
        "head": np.nan,
        "powers": [100.0, float("inf"), float("-inf")],
        "np_val": np.int64(42),
    }
    selected_units = []

    payload = build_results_export_payload(inputs, results, selected_units)
    raw_json = json.dumps(payload, indent=2, ensure_ascii=False)

    assert "NaN" not in raw_json
    assert "Infinity" not in raw_json

    parsed = json.loads(raw_json)
    assert parsed["results"]["eff"] is None
    assert parsed["results"]["head"] is None
    assert parsed["results"]["powers"] == [100.0, None, None]
    assert parsed["results"]["np_val"] == 42
