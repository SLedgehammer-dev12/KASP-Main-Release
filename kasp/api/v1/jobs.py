"""Jobs & Server-Sent Events (SSE) Streaming Router for KASP Web API v1.
"""

import asyncio
import json
import logging
import queue
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kasp.api.auth import get_current_user_optional
from kasp.services.job_manager import job_manager

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
    """Mühendislik Shootout (8-EOS x 6-Metot) arka plan hesaplama işini başlatır."""
    job = job_manager.create_shootout_job(
        inputs=req.inputs,
        eos_list=req.eos_list,
        method_list=req.method_list,
    )
    return {
        "job_id": job.job_id,
        "total_runs": job.total_runs,
        "status": job.status,
    }


@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    """Hesaplama işinin anlık durumunu ve tamamlanan sonuçları döner."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hesaplama işi bulunamadı.")

    return {
        "job_id": job.job_id,
        "status": job.status,
        "total": job.total_runs,
        "completed": job.completed_runs,
        "progress_pct": round((job.completed_runs / job.total_runs) * 100, 1) if job.total_runs > 0 else 0,
        "results": job.results,
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
    """Server-Sent Events (SSE) ile anlık hesaplama ilerleme olaylarını istemciye aktarır."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hesaplama işi bulunamadı.")

    async def event_generator():
        # First send historical results if any
        for r in job.results:
            yield f"data: {json.dumps({'type': 'progress', 'data': r})}\n\n"

        while True:
            try:
                # Polling queue with small timeout
                item = job.event_queue.get_nowait()
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("type") in ("completed", "cancelled", "error"):
                    break
            except queue.Empty:
                if job.status in ("completed", "cancelled", "error") and job.event_queue.empty():
                    break
                await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
