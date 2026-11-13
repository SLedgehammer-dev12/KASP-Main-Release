"""KASP Web Update & Release Download Manager API Router."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from kasp.services import update_service

router = APIRouter(prefix="/updates", tags=["Updates"])


class UpdateDownloadRequest(BaseModel):
    tag_name: str = Field(..., min_length=1, max_length=80)
    asset_name: str = Field(..., min_length=1, max_length=200)


@router.get("/check")
async def check_updates(
    force: bool = Query(default=False, description="Bypass release cache and query GitHub directly"),
    include_prereleases: bool = Query(default=False),
):
    return await asyncio.to_thread(
        update_service.check_web_updates,
        force=force,
        include_prereleases=include_prereleases,
    )


@router.post("/download")
async def start_update_download(req: UpdateDownloadRequest):
    try:
        return await asyncio.to_thread(update_service.start_download, req.tag_name, req.asset_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/downloads")
async def list_update_downloads():
    return {"downloads": update_service.list_downloads()}


@router.get("/downloads/{job_id}")
async def get_update_download_status(job_id: str):
    item = update_service.get_download(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="İndirme işi bulunamadı.")
    return item


@router.post("/downloads/{job_id}/cancel")
async def cancel_update_download(job_id: str):
    item = update_service.cancel_download(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="İndirme işi bulunamadı.")
    return item


@router.get("/downloads/{job_id}/file")
async def download_completed_asset(job_id: str):
    path = update_service.get_downloaded_file_path(job_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Tamamlanmış indirme dosyası bulunamadı.")
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
