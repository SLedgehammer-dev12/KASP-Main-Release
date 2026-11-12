"""Konu #3 TDD Suite: Engineering Shootout (F04) Cross-Layer Coupling & SSE Integrity."""

import json
import time
import pytest
from fastapi.testclient import TestClient

from kasp.api.server import app
from kasp.core.thermo_design_support import select_design_method_key
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.job_manager import (
    DEFAULT_SHOOTOUT_EOS,
    DEFAULT_SHOOTOUT_METHODS,
    JobManager,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _wait_for_job(mgr_or_client, job_id: str, timeout_s: float = 20.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if isinstance(mgr_or_client, JobManager):
            job = mgr_or_client.get_job(job_id)
            assert job is not None
            if job.status in ("completed", "cancelled", "error"):
                return {
                    "job_id": job.job_id,
                    "status": job.status,
                    "results": job.results,
                    "ranked_results": getattr(job, "ranked_results", []),
                    "summary": getattr(job, "summary", {}),
                }
        else:
            resp = mgr_or_client.get(f"/api/v1/jobs/{job_id}/status")
            assert resp.status_code == 200
            payload = resp.json()
            if payload["status"] in ("completed", "cancelled", "error"):
                return payload
        time.sleep(0.05)
    pytest.fail(f"Shootout job {job_id} did not finish within {timeout_s}s")


def test_shootout_default_eos_and_methods_match_supported_core():
    """Default EOS and 6-method lists must match real core solvers without broken IDs."""
    forbidden_broken_eos = {"rk", "vdw", "bwrs"}
    assert forbidden_broken_eos.isdisjoint(set(DEFAULT_SHOOTOUT_EOS))
    for required_eos in ("coolprop", "pr", "srk", "gerg2008", "aga8", "thermopack", "neqsim"):
        assert required_eos in DEFAULT_SHOOTOUT_EOS

    assert len(DEFAULT_SHOOTOUT_METHODS) == 6
    method_keys = {select_design_method_key(m) for m in DEFAULT_SHOOTOUT_METHODS}
    assert method_keys == {
        "average",
        "endpoint",
        "incremental",
        "direct_hs",
        "huntington_rk45",
        "schultz_3exp",
    }


def test_shootout_legacy_eos_and_method_aliases_execute_without_error():
    """Legacy UI EOS IDs (rk/vdw/bwrs) and old method labels must map cleanly, never crash."""
    mgr = JobManager(max_workers=1)
    inputs = {
        "p_in": 20.0,
        "p_in_unit": "bar(a)",
        "p_out": 45.0,
        "p_out_unit": "bar(a)",
        "t_in": 20.0,
        "t_in_unit": "°C",
        "flow": 12.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 94.0, "ETHANE": 4.0, "NITROGEN": 2.0},
        "poly_eff": 84.0,
    }
    job = mgr.create_shootout_job(
        inputs=inputs,
        eos_list=["rk", "vdw", "bwrs"],
        method_list=["Metot 4: Artımlı Entalpi", "Metot 5: Schultz 2-Üslü"],
    )
    done = _wait_for_job(mgr, job.job_id)
    assert done["status"] == "completed"
    assert len(done["results"]) == 6
    for row in done["results"]:
        assert row["status"] == "success", f"Unexpected error in legacy alias run: {row}"
        assert row["power_kw"] > 0
        assert 70.0 <= row["eff_pct"] <= 99.0
        assert row.get("effective_eos") in ("srk", "pr", "gerg2008", "aga8", "coolprop", "thermopack")

    m4_rows = [r for r in done["results"] if "Metot 4" in r["method"]]
    assert len(m4_rows) == 3
    for r in m4_rows:
        assert r.get("method_key") == "direct_hs"


def test_calculation_service_legacy_eos_aliases_do_not_crash_500(client):
    """Design calculation with legacy eos_model='rk' or 'bwrs' must succeed with warning."""
    payload = {
        "p_in": 30.0,
        "p_in_unit": "bar(a)",
        "p_out": 60.0,
        "p_out_unit": "bar(a)",
        "t_in": 22.0,
        "t_in_unit": "°C",
        "flow": 20.0,
        "flow_unit": "kg/s",
        "gas_comp": {"METHANE": 92.0, "ETHANE": 6.0, "PROPANE": 2.0},
        "poly_eff": 85.0,
        "eos_model": "rk",
        "calc_method": "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    }
    out = execute_design_calculation(payload)
    assert out["power_shaft_total_kw"] > 0
    assert any("rk" in w.lower() for w in out.get("warnings", []))

    resp = client.post("/api/v1/calculations/design", json={**payload, "eos_model": "bwrs"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["results"]["power_shaft_total_kw"] > 0


def test_shootout_web_units_efficiency_pct_pr_and_ranking(client):
    """Web inputs (bar(g), Sm³/h) must yield real % efficiency, PR > 1, deviations & #1 best rank."""
    payload = {
        "inputs": {
            "project_name": "BOTAŞ Shootout Test",
            "p_in": "49.65",
            "p_in_unit": "bar(g)",
            "p_out": "75",
            "p_out_unit": "bar(a)",
            "t_in": "19",
            "t_in_unit": "°C",
            "flow": "1985000",
            "flow_unit": "Sm³/h",
            "gas_comp": {
                "METHANE": 92.0,
                "ETHANE": 5.0,
                "PROPANE": 2.0,
                "NITROGEN": 1.0,
            },
            "poly_eff": 90.0,
            "num_units": 2,
            "num_stages": 1,
        },
        "eos_list": ["coolprop", "pr", "srk"],
        "method_list": [
            "Metot 6: Schultz 3-Üslü Gerçek Gaz",
            "Metot 1: Ortalama Özellikler",
        ],
    }
    init_resp = client.post("/api/v1/jobs/shootout", json=payload)
    assert init_resp.status_code == 200
    job_id = init_resp.json()["job_id"]

    status_data = _wait_for_job(client, job_id)
    assert status_data["status"] == "completed"
    results = status_data["results"]
    assert len(results) == 6

    for r in results:
        assert r["status"] == "success"
        assert 70.0 <= r["eff_pct"] <= 99.0, f"Efficiency must be in %, got {r['eff_pct']}"
        assert r["pressure_ratio"] == pytest.approx(75.0 / (49.65 + 1.01325), rel=1e-2)
        assert "effective_eos" in r
        assert "fallback_used" in r
        assert r.get("power_diff_pct") is not None
        assert r.get("head_diff_pct") is not None
        assert r.get("t_out_diff_c") is not None
        assert r.get("rank") in {1, 2, 3, 4, 5, 6}

    ranked = status_data.get("ranked_results") or []
    assert len(ranked) == 6
    assert [r["rank"] for r in ranked] == [1, 2, 3, 4, 5, 6]
    best_rows = [r for r in ranked if r.get("is_best") is True]
    assert len(best_rows) == 1
    assert best_rows[0]["rank"] == 1

    summary = status_data.get("summary") or {}
    assert summary.get("best_eos") == best_rows[0]["eos"]
    assert summary.get("reference_eos") == "coolprop"
    assert summary.get("power_spread_kw") >= 0.0


def test_shootout_sse_stream_deduplicates_completed_steps_and_validates_inputs(client):
    """SSE stream connected after job completion must emit each step once, and invalid inputs -> 422."""
    bad_resp = client.post(
        "/api/v1/jobs/shootout",
        json={
            "inputs": {
                "p_in": 80.0,
                "p_in_unit": "bar(a)",
                "p_out": 40.0,
                "p_out_unit": "bar(a)",
                "t_in": 20.0,
                "t_in_unit": "°C",
                "flow": 10.0,
                "flow_unit": "kg/s",
                "gas_comp": {"METHANE": 100.0},
            },
            "eos_list": ["pr"],
            "method_list": ["Metot 1: Ortalama Özellikler"],
        },
    )
    assert bad_resp.status_code == 422

    good_resp = client.post(
        "/api/v1/jobs/shootout",
        json={
            "inputs": {
                "p_in": 25.0,
                "p_in_unit": "bar(a)",
                "p_out": 50.0,
                "p_out_unit": "bar(a)",
                "t_in": 20.0,
                "t_in_unit": "°C",
                "flow": 15.0,
                "flow_unit": "kg/s",
                "gas_comp": {"METHANE": 95.0, "ETHANE": 5.0},
                "poly_eff": 85.0,
            },
            "eos_list": ["coolprop", "pr"],
            "method_list": [
                "Metot 6: Schultz 3-Üslü Gerçek Gaz",
                "Metot 4: Doğrudan H-S",
            ],
        },
    )
    assert good_resp.status_code == 200
    job_id = good_resp.json()["job_id"]

    # Wait until job finishes so both job.results and job.event_queue hold items
    _wait_for_job(client, job_id)

    with client.stream("GET", f"/api/v1/jobs/{job_id}/stream") as stream_resp:
        assert stream_resp.status_code == 200
        events = []
        for raw_line in stream_resp.iter_lines():
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    progress_events = [e for e in events if e.get("type") == "progress"]
    completed_events = [e for e in events if e.get("type") == "completed"]

    assert [e["data"]["step"] for e in progress_events] == [1, 2, 3, 4]
    assert len(completed_events) == 1
    assert len(completed_events[0].get("ranked_results", [])) == 4
    assert "summary" in completed_events[0]
