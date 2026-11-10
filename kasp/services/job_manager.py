"""Asynchronous Job Manager for KASP Web API.

Manages background engineering shootout calculations with real-time SSE progress
streaming and cooperative calculation cancellation.
"""

import asyncio
import json
import logging
import queue
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from kasp.core.thermo import ThermoEngine
from kasp.core.aerodynamics import (
    begin_calculation_run,
    end_calculation_run,
    request_calculation_cancel,
)

logger = logging.getLogger(__name__)

DEFAULT_SHOOTOUT_EOS = [
    "coolprop",
    "pr",
    "srk",
    "rk",
    "vdw",
    "bwrs",
    "gerg2008",
]

DEFAULT_SHOOTOUT_METHODS = [
    "Metot 1: Ortalama Özellikler",
    "Metot 2: Endpoint Yaklaşımı",
    "Metot 3: Artımlı Basınç",
    "Metot 4: Artımlı Entalpi",
    "Metot 5: Schultz 2-Üslü",
    "Metot 6: Schultz 3-Üslü Gerçek Gaz",
]


class ShootoutJob:
    """Tekil bir Shootout işinin durumunu ve olay kuyruğunu tutar."""

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
        self._engine: Optional[ThermoEngine] = None

    def _get_engine(self) -> ThermoEngine:
        if self._engine is None:
            self._engine = ThermoEngine()
        return self._engine

    def create_shootout_job(
        self,
        inputs: Dict[str, Any],
        eos_list: Optional[List[str]] = None,
        method_list: Optional[List[str]] = None,
    ) -> ShootoutJob:
        """Yeni bir shootout işi oluşturur ve kuyruğa ekler."""
        job_id = f"job_{secrets.token_hex(8)}"
        selected_eos = eos_list or DEFAULT_SHOOTOUT_EOS
        selected_methods = method_list or DEFAULT_SHOOTOUT_METHODS

        job = ShootoutJob(job_id, inputs, selected_eos, selected_methods)
        with self._lock:
            # Stale jobs cleanup (> 2 saat)
            now = time.time()
            stale = [jid for jid, j in self._jobs.items() if now - j.created_at > 7200]
            for jid in stale:
                del self._jobs[jid]

            self._jobs[job_id] = job

        # ThreadPool'da başlat
        self._executor.submit(self._run_shootout, job)
        return job

    def get_job(self, job_id: str) -> Optional[ShootoutJob]:
        """İş nesnesini döner."""
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Çalışan işi iptal eder."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.cancelled = True
            job.status = "cancelled"

        request_calculation_cancel(job_id)
        job.event_queue.put({"type": "cancelled", "message": "İş kullanıcı tarafından iptal edildi."})
        return True

    def _run_shootout(self, job: ShootoutJob):
        """Arka plan thread'inde çalışan shootout döngüsü."""
        job.status = "running"
        begin_calculation_run(job.job_id)
        engine = self._get_engine()

        job.event_queue.put({
            "type": "start",
            "job_id": job.job_id,
            "total": job.total_runs,
        })

        step_idx = 0
        base_inputs = dict(job.inputs)

        try:
            for eos in job.eos_list:
                for method in job.method_list:
                    if job.cancelled:
                        break

                    step_idx += 1
                    run_data = dict(base_inputs)
                    run_data["eos_method"] = eos
                    run_data["method"] = method

                    start_t = time.perf_counter()
                    item_res: Dict[str, Any] = {
                        "step": step_idx,
                        "total": job.total_runs,
                        "eos": eos,
                        "method": method,
                        "status": "pending",
                    }

                    try:
                        res = engine.calculate_design_performance(run_data)
                        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)

                        power_kw = res.get("power_shaft_total_kw", 0.0)
                        t_out = res.get("t_out", 0.0)
                        eff = res.get("actual_poly_efficiency", 0.0)
                        head_kj_kg = sum(s.get("head_kj_kg", 0.0) for s in res.get("stages", []))
                        pr = res.get("pr", 0.0)

                        item_res.update({
                            "status": "success",
                            "power_kw": round(power_kw, 2),
                            "t_out_c": round(t_out, 2),
                            "eff_pct": round(eff, 2),
                            "head_kj_kg": round(head_kj_kg, 2),
                            "pressure_ratio": round(pr, 3),
                            "duration_ms": duration_ms,
                            "warnings": res.get("warnings", []),
                        })

                    except Exception as err:
                        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)
                        item_res.update({
                            "status": "error",
                            "error": str(err),
                            "duration_ms": duration_ms,
                        })

                    job.results.append(item_res)
                    job.completed_runs = step_idx
                    job.event_queue.put({"type": "progress", "data": item_res})

                if job.cancelled:
                    break

            if not job.cancelled:
                job.status = "completed"
                job.completed_at = time.time()
                job.event_queue.put({
                    "type": "completed",
                    "total": job.total_runs,
                    "results_count": len(job.results),
                })

        except Exception as e:
            job.status = "error"
            job.error_message = str(e)
            job.event_queue.put({"type": "error", "message": str(e)})

        finally:
            end_calculation_run(job.job_id)


# Global singleton job manager
job_manager = JobManager(max_workers=2)
