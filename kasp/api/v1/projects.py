"""Projects & Calculation History Router for KASP Web API v1.

Endpoints for managing calculation history, and importing/exporting .kasp project files
with strict 2MB payload guard and schema migration.
"""

import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from kasp.api.auth import get_current_user, get_db, require_permission
from kasp.data.database import UnitDatabase
from kasp.utils.project_manager import ProjectManager, sanitize_json_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])

MAX_KASP_FILE_SIZE = 2 * 1024 * 1024  # 2 MB güvenlik sınırı


def _merge_module_payload(results, modules, station_data):
    """Attach integration module/station results to the persisted result payload."""
    payload = dict(results or {})
    if modules:
        payload["module_results"] = modules
    if station_data:
        payload["station_data"] = station_data
    return payload or None


class SaveProjectRequest(BaseModel):
    project_name: str = "Yeni Proje"
    calculation_type: str = "Design"
    inputs: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    modules: Optional[Dict[str, Any]] = None
    station_data: Optional[Dict[str, Any]] = None
    notes: str = ""


class ExportKaspRequest(BaseModel):
    project_name: str = "kasp_project"
    inputs: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    modules: Optional[Dict[str, Any]] = None
    station_data: Optional[Dict[str, Any]] = None


class ExportResultsJsonRequest(BaseModel):
    project_name: str = "kasp_project"
    inputs: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    selected_units: Optional[list] = None
    modules: Optional[Dict[str, Any]] = None
    station_data: Optional[Dict[str, Any]] = None


@router.get("")
async def list_projects(
    limit: int = 50,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Kayıtlı hesaplama geçmişini listeler.

    Normal kullanıcılar kendi hesaplamalarını, yöneticiler ise tümünü görür.
    """
    user_id = None if user.get("role") == "admin" else user.get("id")
    history = db.get_calculation_history(limit=limit, user_id=user_id)
    # Parse json strings for client
    parsed = []
    for h in history:
        item = dict(h)
        if isinstance(item.get("inputs_json"), str):
            try:
                item["inputs"] = json.loads(item["inputs_json"])
            except Exception:
                item["inputs"] = {}
        if isinstance(item.get("results_json"), str):
            try:
                item["results"] = json.loads(item["results_json"])
            except Exception:
                item["results"] = None
        parsed.append(item)
    return parsed


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Belirtilen ID'ye sahip geçmiş hesaplamayı getirir."""
    user_id = None if user.get("role") == "admin" else user.get("id")
    record = db.get_calculation_history_by_id(project_id, user_id=user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Proje kaydı bulunamadı.")
    
    item = dict(record)
    if isinstance(item.get("inputs_json"), str):
        try:
            item["inputs"] = json.loads(item["inputs_json"])
        except Exception:
            item["inputs"] = {}
    if isinstance(item.get("results_json"), str):
        try:
            item["results"] = json.loads(item["results_json"])
        except Exception:
            item["results"] = None
    return item


@router.post("")
async def save_project(
    req: SaveProjectRequest,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """Hesaplama sonucunu veritabanı geçmişine kaydeder."""
    history_id = db.save_calculation_history(
        project_name=req.project_name,
        calculation_type=req.calculation_type,
        inputs=req.inputs,
        results=_merge_module_payload(req.results, req.modules, req.station_data),
        notes=req.notes,
        user_id=user.get("id"),
    )
    if not history_id:
        raise HTTPException(status_code=500, detail="Proje kaydedilemedi.")
    return {"message": "Proje geçmişe kaydedildi.", "id": history_id}


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("delete")),
):
    """Hesaplama geçmişi kaydını siler."""
    user_id = None if user.get("role") == "admin" else user.get("id")
    ok = db.delete_calculation_history(project_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Proje silinemedi veya yetkiniz yok.")
    return {"message": "Proje geçmişten silindi."}


@router.post("/export-kasp")
async def export_kasp(
    req: ExportKaspRequest,
    user: dict = Depends(get_current_user),
):
    """Mevcut girdi ve sonuçları .kasp dosya formatında dışa aktarır."""
    import datetime
    pm = ProjectManager()
    project_data = {
        "schema_version": pm.VERSION,
        "timestamp": datetime.datetime.now().isoformat(),
        "inputs": req.inputs,
        "results": req.results,
        "modules": req.modules or {},
        "station_data": req.station_data,
    }
    filename = f"{req.project_name.strip() or 'kasp_project'}.kasp"
    sanitized_data = sanitize_json_payload(project_data)
    json_bytes = json.dumps(sanitized_data, indent=2, ensure_ascii=False).encode("utf-8")
    
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/export-results-json")
async def export_results_json(
    req: ExportResultsJsonRequest,
    user: dict = Depends(get_current_user),
):
    """Hesaplama sonuçlarını salt _Sonuclar.json formatında dışa aktarır."""
    import datetime
    from kasp.ui.document_workflows import build_results_export_payload
    payload = build_results_export_payload(
        inputs=req.inputs,
        results=req.results,
        selected_units=req.selected_units or [],
        exported_at=datetime.datetime.now().isoformat(),
    )
    if req.modules:
        payload["modules"] = req.modules
    if req.station_data:
        payload["station_data"] = req.station_data
    safe_name = (req.project_name.strip() or 'kasp_project').replace(' ', '_')
    filename = f"{safe_name}_Sonuclar.json"
    sanitized_payload = sanitize_json_payload(payload)
    json_bytes = json.dumps(sanitized_payload, indent=4, ensure_ascii=False).encode("utf-8")
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/import-kasp")
async def import_kasp(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Yüklenen .kasp dosyasını doğrular, şema migrasyonunu yapar ve girdi/sonuçları döner."""
    contents = await file.read()
    if len(contents) > MAX_KASP_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya boyutu çok büyük (Maksimum: {MAX_KASP_FILE_SIZE // (1024*1024)} MB).",
        )

    try:
        data = json.loads(contents.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geçersiz KASP JSON formatı: {str(e)}",
        )

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Geçersiz proje içeriği.")

    pm = ProjectManager()
    migrated_data = pm._migrate_project_schema(data)

    return {
        "success": True,
        "schema_version": migrated_data.get("schema_version"),
        "timestamp": migrated_data.get("timestamp"),
        "inputs": migrated_data.get("inputs", {}),
        "results": migrated_data.get("results"),
        "modules": migrated_data.get("modules", {}),
        "station_data": migrated_data.get("station_data"),
    }
