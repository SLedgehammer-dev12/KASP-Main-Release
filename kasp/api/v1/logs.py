"""Logs Router for KASP Web API v1.

Provides REST and SSE log streaming directly from the thread-safe MemoryRingLogHandler.
"""

import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from kasp.api.auth import get_current_user_optional
from kasp.utils.logging_handler import get_memory_log_handler

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def get_recent_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    level: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Bellek içi ring buffer'dan son N log kaydını döner."""
    handler = get_memory_log_handler()
    return handler.get_logs(limit=limit, level=level)


@router.delete("")
async def clear_logs(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Log tamponunu temizler."""
    handler = get_memory_log_handler()
    handler.clear()
    return {"message": "Log kayıtları temizlendi."}


@router.get("/stream")
async def stream_logs(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Server-Sent Events (SSE) ile anlık log akışı sağlar."""
    handler = get_memory_log_handler()

    async def event_generator():
        last_idx = len(handler.get_logs(limit=1000))
        while True:
            all_logs = handler.get_logs(limit=1000)
            curr_len = len(all_logs)
            if curr_len > last_idx:
                new_logs = all_logs[last_idx:]
                for log_entry in new_logs:
                    yield f"data: {json.dumps(log_entry)}\n\n"
                last_idx = curr_len
            elif curr_len < last_idx:
                # Buffer wrapped or cleared
                last_idx = curr_len
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
