"""Regression tests for the Müdür audit findings.

Covers:
- C1: intercooled multi-stage whole-train ASME PTC-10 guard
- C2: shootout cancellation vs. terminal job state race
- H4: m³/h (ACMH) is not aliased to standard Sm³/h
- H5: legacy BWRS alias resolves consistently to GERG-2008
- H8: NaN/Inf are sanitized before calculation-history persistence
- M1: project export/import require an authenticated, authorized session
- M8: report optional numerics never raise on None/NaN
"""

import json
import math

import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.core.thermo import ThermoEngine
from kasp.data.database import UnitDatabase
from kasp.services.calculation_service import execute_design_calculation, resolve_supported_eos
from kasp.services.performance_service import evaluate_field_performance


@pytest.fixture(scope="module")
def engine():
    return ThermoEngine()


def _intercooled_design(engine: ThermoEngine) -> dict:
    return execute_design_calculation(
        {
            "p_in": 20.0,
            "p_in_unit": "bar(a)",
            "p_out": 60.0,
            "p_out_unit": "bar(a)",
            "t_in": 25.0,
            "t_in_unit": "°C",
            "flow": 12.0,
            "flow_unit": "kg/s",
            "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
            "poly_eff": 80.0,
            "mech_eff": 98.0,
            "therm_eff": 35.0,
            "num_stages": 2,
            "intercooler_t": 35.0,
            "eos_model": "pr",
            "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
        },
        engine=engine,
    )


def test_intercooled_whole_train_requires_stage_index(engine):
    """C1: collapsing an intercooled train into one PTC-10 section must be rejected."""
    design = _intercooled_design(engine)
    stages = design.get("stages") or []
    assert len(stages) >= 2

    field = {
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "t_out": design["t_out_c"],
        "t_out_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 10.0},
        "eos_model": "pr",
    }

    with pytest.raises(ValueError, match="stage_index"):
        evaluate_field_performance(field, design, engine=engine)


def test_cancel_before_worker_start_survives_job_start():
    """C2: a queued job cancelled before the worker starts must stay cancelled."""
    from kasp.services.job_manager import JobManager, ShootoutJob

    manager = JobManager(max_workers=1)
    try:
        job = ShootoutJob(
            "job_test_cancel_before_start",
            {"p_in": 20.0, "p_out": 60.0, "gas_comp": {"METHANE": 100.0}},
            ["coolprop"],
            ["Metot 1: Ortalama Özellikler"],
        )
        manager._jobs[job.job_id] = job

        assert manager.cancel_job(job.job_id) is True
        assert job.status == "cancelled"

        manager._run_shootout(job)
        assert job.status == "cancelled"
        assert job.cancelled is True
        assert job.results == []
    finally:
        manager._executor.shutdown(wait=False)


def test_cancel_cannot_overwrite_completed_or_error_job():
    """C2: cancel_job must not relabel a terminal job as cancelled."""
    from kasp.services.job_manager import JobManager, ShootoutJob

    manager = JobManager(max_workers=1)
    try:
        for terminal in ("completed", "error"):
            job = ShootoutJob(
                f"job_test_terminal_{terminal}",
                {"p_in": 20.0},
                ["coolprop"],
                ["Metot 1: Ortalama Özellikler"],
            )
            job.status = terminal
            manager._jobs[job.job_id] = job

            assert manager.cancel_job(job.job_id) is False
            assert job.status == terminal
            assert job.cancelled is False
    finally:
        manager._executor.shutdown(wait=False)


def test_actual_m3h_is_not_standard_flow():
    """H4: m³/h stays ACMH and uses inlet density instead of ISO standard density."""
    from kasp.services.station_service import _actual_m3h_to_kgs, _canonical_flow_unit

    assert _canonical_flow_unit("m3/h") == "m³/h"
    assert _canonical_flow_unit("m³/h") == "m³/h"
    assert _canonical_flow_unit("Sm³/h") == "Sm³/h"

    engine = ThermoEngine()
    gas_obj = engine._create_gas_object({"METHANE": 100.0}, "pr")
    kgs = _actual_m3h_to_kgs(
        3600.0,
        {"p_in": 30.0, "p_in_unit": "bar(a)", "t_in": 25.0, "t_in_unit": "°C"},
        engine,
        gas_obj,
        "pr",
        16.043,
    )
    # 30 bar(a), 25°C methane is ~20-23 kg/m³ → 1 m³/s ≈ 20-23 kg/s
    assert 18.0 < kgs < 26.0


def test_bwrs_alias_is_consistent_across_services():
    """H5: every legacy alias map must resolve BWRS to the same EOS."""
    from kasp.integrations.control_valve.adapter import _EOS_ALIASES
    from kasp.services.performance_service import _PERF_EOS_ALIASES
    from kasp.services.pipe_sizing_service import _normalize_pipe_eos
    from kasp.services.station_service import _normalize_station_eos
    from kasp.utils.project_manager import normalize_project_inputs_cross_platform

    assert resolve_supported_eos("bwrs")[1] == "gerg2008"
    assert _normalize_station_eos("bwrs") == "gerg2008"
    assert _normalize_pipe_eos("bwrs") == "gerg2008"
    assert _PERF_EOS_ALIASES["bwrs"] == "gerg2008"
    assert _EOS_ALIASES["bwrs"] == "gerg2008"
    migrated = normalize_project_inputs_cross_platform({"eos_model": "bwrs"})
    assert migrated["eos_model"] == "gerg2008"


def test_history_persistence_sanitizes_nan_and_inf(tmp_path):
    """H8: calculation history must store strict JSON (no NaN/Infinity tokens)."""
    db = UnitDatabase(db_name=str(tmp_path / "kasp_nan.db"))
    history_id = db.save_calculation_history(
        project_name="NaN testi",
        calculation_type="Design",
        inputs={"p_in": 20.0, "p_out": 60.0},
        results={
            "power_total_kw": float("nan"),
            "head_kj_kg": float("inf"),
            "nested": {"values": [1.0, float("-inf")]},
        },
    )
    assert history_id

    record = db.get_calculation_history_by_id(history_id)
    assert record is not None
    for column in ("inputs_json", "results_json"):
        raw = record[column]
        assert "NaN" not in raw
        assert "Infinity" not in raw
        json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))

    parsed = json.loads(record["results_json"])
    assert parsed["power_total_kw"] is None
    assert parsed["head_kj_kg"] is None
    assert parsed["nested"]["values"][1] is None


def test_project_export_import_require_authentication():
    """M1: anonymous .kasp export/import must be rejected."""
    client = TestClient(app)
    payload = {
        "project_name": "anon",
        "inputs": {"p_in": 20.0, "p_out": 60.0, "gas_comp": {"METHANE": 100.0}},
        "results": {},
    }
    export_resp = client.post("/api/v1/projects/export-kasp", json=payload)
    assert export_resp.status_code == 401

    import_resp = client.post(
        "/api/v1/projects/import-kasp",
        files={"file": ("anon.kasp", b"{}", "application/json")},
    )
    assert import_resp.status_code == 401


def test_report_safe_float_handles_optional_none():
    """M8: report numeric coercion tolerates None/NaN/empty values."""
    from kasp.utils.reporting import _safe_float

    assert _safe_float(None, 15.0) == 15.0
    assert _safe_float("", 101.325) == 101.325
    assert _safe_float(float("nan"), 0.0) == 0.0
    assert _safe_float(float("inf"), 0.0) == 0.0
    assert math.isclose(_safe_float("42.5", 0.0), 42.5)
