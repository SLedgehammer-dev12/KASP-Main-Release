"""Asynchronous Job Manager for KASP Web API.

Manages background engineering shootout calculations (9-EOS x 6-Method)
with input normalization, real-time SSE progress streaming, cooperative
calculation cancellation, reference deviation mapping, and ranking.
"""

from __future__ import annotations

import logging
import math
import queue
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from kasp.core.aerodynamics import (
    begin_calculation_run,
    end_calculation_run,
    request_calculation_cancel,
)
from kasp.core.contracts import normalize_design_inputs
from kasp.core.exceptions import CalculationCancelled
from kasp.core.thermo import ThermoEngine
from kasp.core.thermo_design_support import select_design_method_key
from kasp.services.calculation_service import (
    resolve_supported_eos,
    resolve_supported_method,
)
from kasp.services.validation_service import validate_design_inputs

logger = logging.getLogger(__name__)

DEFAULT_SHOOTOUT_EOS = [
    "coolprop",
    "pr",
    "srk",
    "gerg2008",
    "aga8",
    "thermopack",
    "neqsim",
    "ccp",
    "dwsim",
]

SHOOTOUT_EOS_LABELS = {
    "coolprop": "CoolProp (HEOS Ref.)",
    "pr": "Peng-Robinson (Kübik)",
    "srk": "Soave-Redlich-Kwong (SRK)",
    "gerg2008": "GERG-2008 Doğalgaz",
    "aga8": "AGA8-DC92 Doğalgaz",
    "thermopack": "SINTEF ThermoPack",
    "neqsim": "Equinor NeqSim (CPA/SRK)",
    "ccp": "Petrobras CCP",
    "dwsim": "DWSIM Termodinamik",
}

DEFAULT_SHOOTOUT_METHODS = [
    "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    "Metot 5: Huntington-RK45 Diferansiyel",
    "Metot 4: Doğrudan H-S",
    "Metot 3: Artımlı Basınç",
    "Metot 2: Endpoint Yaklaşımı",
    "Metot 1: Ortalama Özellikler",
]

_METHOD_RIGOR_ORDER = {
    "schultz_3exp": 0,
    "huntington_rk45": 1,
    "direct_hs": 2,
    "incremental": 3,
    "endpoint": 4,
    "average": 5,
}

_EOS_RIGOR_ORDER = {
    "coolprop": 0,
    "gerg2008": 1,
    "aga8": 2,
    "thermopack": 3,
    "neqsim": 4,
    "srk": 5,
    "pr": 6,
    "ccp": 7,
    "dwsim": 8,
}


class ShootoutValidationError(ValueError):
    """Raised when shootout design inputs fail physics/domain validation."""

    def __init__(self, errors: List[Dict[str, Any]], warnings: Optional[List[Dict[str, Any]]] = None):
        self.errors = list(errors or [])
        self.warnings = list(warnings or [])
        msg = "; ".join(str(e.get("message", "")) for e in self.errors if e.get("message"))
        super().__init__(msg or "Geçersiz shootout tasarım girdileri.")


def _select_reference_row(successful: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not successful:
        return None

    # 1. Native CoolProp + ASME PTC-10 / API 617 rigorous path (Metot 6 or Metot 5)
    for pref_m in ("schultz_3exp", "huntington_rk45", "direct_hs"):
        for r in successful:
            if (
                r.get("requested_eos") == "coolprop"
                and not r.get("fallback_used")
                and r.get("method_key") == pref_m
            ):
                return r

    # 2. Any native CoolProp run
    for r in successful:
        if r.get("requested_eos") == "coolprop" and not r.get("fallback_used"):
            return r

    # 3. Native GERG-2008 or AGA8 run
    for r in successful:
        if r.get("effective_eos") in ("coolprop", "gerg2008", "aga8") and not r.get("fallback_used"):
            return r

    # 4. First non-fallback successful run, else first successful run
    for r in successful:
        if not r.get("fallback_used"):
            return r
    return successful[0]


def rank_shootout_results(results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Compute reference deviations, engineering rank (1..N), best flag, and summary."""
    successful = [
        r for r in results
        if r.get("status") == "success" and isinstance(r.get("power_kw"), (int, float)) and r["power_kw"] > 0
    ]
    ref = _select_reference_row(successful)

    ref_power = float(ref["power_kw"]) if ref and ref.get("power_kw") else 0.0
    ref_head = float(ref["head_kj_kg"]) if ref and ref.get("head_kj_kg") else 0.0
    ref_t_out = float(ref["t_out_c"]) if ref and ref.get("t_out_c") is not None else 0.0

    for r in results:
        r["is_best"] = False
        if r.get("status") == "success" and ref is not None:
            p_kw = float(r.get("power_kw") or 0.0)
            h_kj = float(r.get("head_kj_kg") or 0.0)
            t_c = float(r.get("t_out_c") or 0.0)
            r["is_reference"] = bool(r.get("step") == ref.get("step"))
            r["power_diff_pct"] = round(((p_kw - ref_power) / ref_power) * 100.0, 3) if ref_power > 0 else 0.0
            r["head_diff_pct"] = round(((h_kj - ref_head) / ref_head) * 100.0, 3) if ref_head > 0 else 0.0
            r["t_out_diff_c"] = round(t_c - ref_t_out, 2)
        else:
            r["is_reference"] = False
            r["power_diff_pct"] = None
            r["head_diff_pct"] = None
            r["t_out_diff_c"] = None

    def _sort_key(item: Dict[str, Any]):
        if item.get("status") != "success":
            return (9, 1e9, 99, 99, float(item.get("step") or 999))
        eb_ok = bool(item.get("energy_balance_ok", True))
        conv = bool(item.get("method_converged", True))
        fb = bool(item.get("fallback_used", False))
        if eb_ok and conv and not fb:
            tier = 0
        elif eb_ok and conv and fb:
            tier = 1
        elif eb_ok:
            tier = 2
        else:
            tier = 3

        dev_score = round(
            abs(float(item.get("power_diff_pct") or 0.0))
            + 0.5 * abs(float(item.get("head_diff_pct") or 0.0)),
            4,
        )
        m_order = _METHOD_RIGOR_ORDER.get(str(item.get("method_key") or ""), 9)
        e_order = _EOS_RIGOR_ORDER.get(str(item.get("effective_eos") or ""), 9)
        dur = float(item.get("duration_ms") or 0.0)
        return (tier, dev_score, m_order, e_order, dur)

    sorted_rows = sorted(results, key=_sort_key)
    for idx, row in enumerate(sorted_rows, start=1):
        row["rank"] = idx
        row["is_best"] = bool(idx == 1 and row.get("status") == "success")

    ranked_copy = [dict(r) for r in sorted_rows]
    best_row = next((r for r in ranked_copy if r.get("is_best")), None)

    powers = [float(r["power_kw"]) for r in successful]
    durations = [float(r.get("duration_ms") or 0.0) for r in results if r.get("duration_ms") is not None]
    min_p = min(powers) if powers else 0.0
    max_p = max(powers) if powers else 0.0
    spread_kw = round(max_p - min_p, 2) if powers else 0.0
    spread_pct = round(((max_p - min_p) / ref_power) * 100.0, 2) if (powers and ref_power > 0) else 0.0

    summary: Dict[str, Any] = {
        "total_runs": len(results),
        "success_count": len(successful),
        "error_count": sum(1 for r in results if r.get("status") == "error"),
        "fallback_count": sum(1 for r in successful if r.get("fallback_used")),
        "reference_step": ref.get("step") if ref else None,
        "reference_eos": ref.get("eos") if ref else None,
        "reference_eos_label": ref.get("eos_label") if ref else None,
        "reference_method": ref.get("method") if ref else None,
        "reference_power_kw": round(ref_power, 2) if ref else None,
        "reference_head_kj_kg": round(ref_head, 2) if ref else None,
        "reference_t_out_c": round(ref_t_out, 2) if ref else None,
        "best_step": best_row.get("step") if best_row else None,
        "best_eos": best_row.get("eos") if best_row else None,
        "best_eos_label": best_row.get("eos_label") if best_row else None,
        "best_method": best_row.get("method") if best_row else None,
        "best_power_kw": best_row.get("power_kw") if best_row else None,
        "best_eff_pct": best_row.get("eff_pct") if best_row else None,
        "min_power_kw": round(min_p, 2) if powers else None,
        "max_power_kw": round(max_p, 2) if powers else None,
        "power_spread_kw": spread_kw,
        "power_spread_pct": spread_pct,
        "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0.0,
    }
    return ranked_copy, summary


class ShootoutJob:
    """Tekil bir Shootout işinin durumunu, sıralamasını ve olay kuyruğunu tutar."""

    def __init__(self, job_id: str, inputs: Dict[str, Any], eos_list: List[str], method_list: List[str]):
        self.job_id = job_id
        self.inputs = inputs
        self.eos_list = eos_list
        self.method_list = method_list
        self.total_runs = len(eos_list) * len(method_list)
        self.completed_runs = 0
        self.status = "queued"  # queued, running, completed, cancelled, error
        self.cancelled = False
        self.results: List[Dict[str, Any]] = []
        self.ranked_results: List[Dict[str, Any]] = []
        self.summary: Dict[str, Any] = {}
        self.event_queue: queue.Queue = queue.Queue()
        self.error_message: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None


class JobManager:
    """Çoklu iş parçacıklı hesaplama ve SSE akış yöneticisi."""

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kasp_job")
        self._jobs: Dict[str, ShootoutJob] = {}
        self._lock = threading.Lock()

    def create_shootout_job(
        self,
        inputs: Dict[str, Any],
        eos_list: Optional[List[str]] = None,
        method_list: Optional[List[str]] = None,
    ) -> ShootoutJob:
        """Girdileri doğrular, normalize eder ve yeni bir shootout işi başlatır."""
        norm_inputs = normalize_design_inputs(inputs)
        val_report = validate_design_inputs(norm_inputs)
        if not val_report["is_valid"]:
            raise ShootoutValidationError(val_report["errors"], val_report.get("warnings", []))

        norm_inputs["enable_uncertainty"] = False

        selected_eos = list(DEFAULT_SHOOTOUT_EOS) if eos_list is None else [str(x).strip() for x in eos_list if str(x).strip()]
        selected_methods = (
            list(DEFAULT_SHOOTOUT_METHODS)
            if method_list is None
            else [str(m).strip() for m in method_list if str(m).strip()]
        )
        if not selected_eos or not selected_methods:
            raise ShootoutValidationError(
                [{"field": "eos_list", "message": "En az bir EOS modeli ve bir politropik metot seçilmelidir."}]
            )

        job_id = f"job_{secrets.token_hex(8)}"
        job = ShootoutJob(job_id, norm_inputs, selected_eos, selected_methods)
        with self._lock:
            now = time.time()
            stale = [jid for jid, j in self._jobs.items() if now - j.created_at > 7200]
            for jid in stale:
                del self._jobs[jid]
            self._jobs[job_id] = job

        self._executor.submit(self._run_shootout, job)
        return job

    def get_job(self, job_id: str) -> Optional[ShootoutJob]:
        """İş nesnesini döner."""
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Çalışan işi işbirlikçi (cooperative) olarak iptal eder."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            # A completed/errored job must never be relabelled as cancelled.
            if job.status in ("completed", "error"):
                return False
            was_already_cancelled = job.cancelled
            job.cancelled = True
            job.status = "cancelled"
            job.completed_at = job.completed_at or time.time()

        if was_already_cancelled:
            return True
        request_calculation_cancel(job_id)
        job.event_queue.put({"type": "cancelled", "message": "İş kullanıcı tarafından iptal edildi."})
        return True

    def _run_shootout(self, job: ShootoutJob):
        """Arka plan thread'inde izole ThermoEngine ile çalışan shootout döngüsü."""
        # Cancel may arrive between create_shootout_job() and the worker picking up the
        # job. Check under the lock and never overwrite the terminal "cancelled" state.
        with self._lock:
            if job.cancelled:
                job.status = "cancelled"
                job.completed_at = job.completed_at or time.time()
                cancelled_before_start = True
            else:
                job.status = "running"
                cancelled_before_start = False
        if cancelled_before_start:
            job.event_queue.put({"type": "cancelled", "message": "İş başlamadan iptal edildi."})
            return

        begin_calculation_run(job.job_id)
        engine = ThermoEngine()

        job.event_queue.put({
            "type": "start",
            "job_id": job.job_id,
            "total": job.total_runs,
        })

        step_idx = 0
        base_inputs = dict(job.inputs)

        try:
            for raw_eos in job.eos_list:
                for raw_method in job.method_list:
                    if job.cancelled:
                        break

                    step_idx += 1
                    requested_eos, target_eos, eos_aliased = resolve_supported_eos(raw_eos)
                    canonical_method = resolve_supported_method(raw_method)
                    method_key = select_design_method_key(canonical_method)

                    run_data = dict(base_inputs)
                    run_data["eos_method"] = target_eos
                    run_data["eos_model"] = target_eos
                    run_data["method"] = canonical_method
                    run_data["calc_method"] = canonical_method
                    run_data["run_id"] = job.job_id

                    start_t = time.perf_counter()
                    item_res: Dict[str, Any] = {
                        "step": step_idx,
                        "total": job.total_runs,
                        "eos": requested_eos,
                        "eos_label": SHOOTOUT_EOS_LABELS.get(requested_eos, requested_eos.upper()),
                        "requested_eos": requested_eos,
                        "target_eos": target_eos,
                        "method": canonical_method,
                        "requested_method": raw_method,
                        "method_key": method_key,
                        "status": "pending",
                    }

                    try:
                        res = engine.calculate_design_performance(run_data)
                        duration_ms = round((time.perf_counter() - start_t) * 1000.0, 1)

                        power_kw = float(res.get("power_shaft_total_kw", 0.0) or 0.0)
                        gas_power_kw = float(res.get("power_gas_total_kw", 0.0) or 0.0)
                        t_out_c = float(res.get("t_out", 0.0) or 0.0)
                        raw_eff = float(res.get("actual_poly_efficiency", 0.0) or 0.0)
                        eff_pct = raw_eff * 100.0 if raw_eff <= 1.5 else raw_eff
                        head_kj_kg = float(
                            res.get("head_kj_kg")
                            if res.get("head_kj_kg") is not None
                            else sum(float(s.get("head_kj_kg", 0.0) or 0.0) for s in res.get("stages", []))
                        )
                        pr = float(res.get("compression_ratio") or res.get("pr") or 0.0)
                        effective_eos = str(res.get("effective_eos") or res.get("_effective_eos") or target_eos).lower()
                        fallback_used = bool(
                            res.get("fallback_used", False)
                            or (effective_eos != target_eos)
                            or eos_aliased
                        )

                        run_warnings = list(res.get("warnings") or [])
                        if eos_aliased:
                            run_warnings.insert(
                                0,
                                f"Eski EOS '{requested_eos}' -> '{target_eos.upper()}' olarak eşlendi.",
                            )

                        item_res.update({
                            "status": "success",
                            "power_kw": round(power_kw, 2) if math.isfinite(power_kw) else 0.0,
                            "gas_power_kw": round(gas_power_kw, 2) if math.isfinite(gas_power_kw) else 0.0,
                            "t_out_c": round(t_out_c, 2) if math.isfinite(t_out_c) else 0.0,
                            "eff_pct": round(eff_pct, 2) if math.isfinite(eff_pct) else 0.0,
                            "head_kj_kg": round(head_kj_kg, 2) if math.isfinite(head_kj_kg) else 0.0,
                            "pressure_ratio": round(pr, 3) if math.isfinite(pr) else 0.0,
                            "effective_eos": effective_eos,
                            "fallback_used": fallback_used,
                            "method_converged": bool(res.get("method_converged", True)),
                            "energy_balance_ok": bool(res.get("energy_balance_ok", True)),
                            "duration_ms": duration_ms,
                            "warnings": run_warnings,
                        })

                    except CalculationCancelled:
                        job.cancelled = True
                        break
                    except Exception as err:
                        duration_ms = round((time.perf_counter() - start_t) * 1000.0, 1)
                        item_res.update({
                            "status": "error",
                            "error": str(err),
                            "effective_eos": target_eos,
                            "fallback_used": eos_aliased,
                            "method_converged": False,
                            "energy_balance_ok": False,
                            "duration_ms": duration_ms,
                        })

                    with self._lock:
                        job.results.append(item_res)
                        job.completed_runs = len(job.results)
                        job.ranked_results, job.summary = rank_shootout_results(job.results)
                        snapshot_item = dict(item_res)

                    job.event_queue.put({"type": "progress", "data": snapshot_item})

                if job.cancelled:
                    break

            with self._lock:
                job.ranked_results, job.summary = rank_shootout_results(job.results)

            if not job.cancelled:
                job.status = "completed"
                job.completed_at = time.time()
                job.event_queue.put({
                    "type": "completed",
                    "total": job.total_runs,
                    "results_count": len(job.results),
                    "ranked_results": job.ranked_results,
                    "summary": job.summary,
                })
            else:
                job.status = "cancelled"
                job.completed_at = job.completed_at or time.time()

        except Exception as e:
            job.status = "error"
            job.error_message = str(e)
            job.event_queue.put({"type": "error", "message": str(e)})

        finally:
            end_calculation_run(job.job_id)


# Global singleton job manager
job_manager = JobManager(max_workers=2)
