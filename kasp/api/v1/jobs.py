"""Jobs & Server-Sent Events (SSE) Streaming Router for KASP Web API v1."""

import asyncio
import json
import logging
import queue
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from kasp.api.auth import get_current_user_optional
from kasp.services.job_manager import ShootoutValidationError, job_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class ShootoutSubmitRequest(BaseModel):
    inputs: Dict[str, Any]
    eos_list: Optional[List[str]] = None
    method_list: Optional[List[str]] = None


@router.post("/shootout")
async def submit_shootout(
    req: ShootoutSubmitRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Mühendislik Shootout (EOS x 6-Metot) arka plan hesaplama işini başlatır."""
    try:
        job = job_manager.create_shootout_job(
            inputs=req.inputs,
            eos_list=req.eos_list,
            method_list=req.method_list,
        )
    except ShootoutValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"errors": exc.errors, "warnings": exc.warnings},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "job_id": job.job_id,
        "total_runs": job.total_runs,
        "status": job.status,
    }


@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    """Hesaplama işinin anlık durumunu, tamamlanan ve sıralanan sonuçları döner."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hesaplama işi bulunamadı.")

    return {
        "job_id": job.job_id,
        "status": job.status,
        "total": job.total_runs,
        "completed": job.completed_runs,
        "progress_pct": round((job.completed_runs / job.total_runs) * 100, 1) if job.total_runs > 0 else 0,
        "results": list(job.results),
        "ranked_results": list(job.ranked_results),
        "summary": dict(job.summary),
        "error": job.error_message,
    }


@router.post("/{job_id}/cancel")
async def cancel_job_route(job_id: str):
    """Çalışan hesaplama işini iptal eder."""
    ok = job_manager.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Hesaplama işi bulunamadı.")
    return {"message": "İşlem iptal edildi."}


@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) ile tekilleştirilmiş hesaplama ilerleme olaylarını aktarır."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hesaplama işi bulunamadı.")

    async def event_generator():
        emitted_steps: set[int] = set()
        terminal_sent = False

        # 1. Emit snapshot of already completed steps once
        initial_snapshot = [dict(r) for r in list(job.results)]
        for r in initial_snapshot:
            step_num = r.get("step")
            if isinstance(step_num, int):
                emitted_steps.add(step_num)
            yield f"data: {json.dumps({'type': 'progress', 'data': r})}\n\n"

        # 2. Drain live queue while skipping any duplicate step already emitted
        while True:
            try:
                item = job.event_queue.get_nowait()
                ev_type = item.get("type")
                if ev_type == "progress":
                    data = item.get("data") or {}
                    step_num = data.get("step")
                    if isinstance(step_num, int):
                        if step_num in emitted_steps:
                            continue
                        emitted_steps.add(step_num)
                    yield f"data: {json.dumps(item)}\n\n"
                elif ev_type in ("completed", "cancelled", "error"):
                    # Ensure any remaining results are flushed before terminal event
                    for r in list(job.results):
                        step_num = r.get("step")
                        if isinstance(step_num, int) and step_num not in emitted_steps:
                            emitted_steps.add(step_num)
                            yield f"data: {json.dumps({'type': 'progress', 'data': dict(r)})}\n\n"
                    yield f"data: {json.dumps(item)}\n\n"
                    terminal_sent = True
                    break
                elif ev_type == "start" and not emitted_steps:
                    yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                if job.status in ("completed", "cancelled", "error") and job.event_queue.empty():
                    for r in list(job.results):
                        step_num = r.get("step")
                        if isinstance(step_num, int) and step_num not in emitted_steps:
                            emitted_steps.add(step_num)
                            yield f"data: {json.dumps({'type': 'progress', 'data': dict(r)})}\n\n"
                    if not terminal_sent:
                        if job.status == "completed":
                            terminal_payload = {
                                "type": "completed",
                                "total": job.total_runs,
                                "results_count": len(job.results),
                                "ranked_results": list(job.ranked_results),
                                "summary": dict(job.summary),
                            }
                        elif job.status == "cancelled":
                            terminal_payload = {"type": "cancelled", "message": "İş kullanıcı tarafından iptal edildi."}
                        else:
                            terminal_payload = {"type": "error", "message": job.error_message or "Bilinmeyen hata."}
                        yield f"data: {json.dumps(terminal_payload)}\n\n"
                    break
                await asyncio.sleep(0.08)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
