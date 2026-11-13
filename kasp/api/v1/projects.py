"""Projects & Calculation History Router for KASP Web API v1.

Endpoints for managing calculation history, and importing/exporting .kasp project files
with strict 2MB payload guard and schema migration.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from kasp.api.auth import get_current_user, get_db, require_permission
from kasp.data.database import UnitDatabase
from kasp.utils.project_manager import (
    ProjectManager,
    normalize_project_inputs_cross_platform,
    sanitize_json_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])

MAX_KASP_FILE_SIZE = 2 * 1024 * 1024  # 2 MB güvenlik sınırı


def _merge_module_payload(
    results,
    modules,
    station_data,
    selected_units=None,
    charts=None,
    warnings=None,
):
    """Attach integration module, station, turbine, chart, and warning payloads to results."""
    payload = dict(results or {})
    if modules:
        payload["module_results"] = modules
    if station_data:
        payload["station_data"] = station_data
    if selected_units is not None:
        payload["selected_units"] = selected_units
    if charts is not None:
        payload["charts"] = charts
    if warnings is not None:
        payload["warnings"] = warnings
    return payload or None


def _hydrate_project_record(record: dict) -> dict:
    """Parse JSON columns and expose top-level selected_units, charts, warnings, modules, station_data."""
    item = dict(record)
    if isinstance(item.get("inputs_json"), str):
        try:
            raw_inputs = json.loads(item["inputs_json"])
            item["inputs"] = normalize_project_inputs_cross_platform(raw_inputs)
        except Exception:
            item["inputs"] = {}
    elif isinstance(item.get("inputs"), dict):
        item["inputs"] = normalize_project_inputs_cross_platform(item["inputs"])

    if isinstance(item.get("results_json"), str):
        try:
            item["results"] = json.loads(item["results_json"])
        except Exception:
            item["results"] = None

    res_dict = item.get("results") if isinstance(item.get("results"), dict) else {}
    item["modules"] = item.get("modules") or res_dict.get("module_results") or {}
    item["station_data"] = item.get("station_data") or res_dict.get("station_data") or None
    item["selected_units"] = (
        item["selected_units"]
        if item.get("selected_units") is not None
        else (res_dict.get("selected_units") or [])
    )
    item["charts"] = (
        item["charts"]
        if item.get("charts") is not None
        else res_dict.get("charts")
    )
    item["warnings"] = (
        item["warnings"]
        if item.get("warnings") is not None
        else (res_dict.get("warnings") or [])
    )
    return item


class SaveProjectRequest(BaseModel):
    project_name: str = "Yeni Proje"
    calculation_type: str = "Design"
    inputs: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    selected_units: Optional[list] = None
    charts: Optional[Dict[str, Any]] = None
    warnings: Optional[list] = None
    modules: Optional[Dict[str, Any]] = None
    station_data: Optional[Dict[str, Any]] = None
    notes: str = ""


class ExportKaspRequest(BaseModel):
    project_name: str = "kasp_project"
    inputs: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    selected_units: Optional[list] = None
    charts: Optional[Dict[str, Any]] = None
    warnings: Optional[list] = None
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
    include_results: bool = False,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Kayıtlı hesaplama geçmişini listeler.

    Normal kullanıcılar kendi hesaplamalarını, yöneticiler ise tümünü görür.
    Ağır sonuç gövdesi varsayılan olarak dışarıda bırakılır; tek kayıt
    GET /projects/{id} ile tam yüklenir.
    """
    user_id = None if user.get("role") == "admin" else user.get("id")
    history = db.get_calculation_history(limit=limit, user_id=user_id)
    items = []
    for record in history:
        item = _hydrate_project_record(record)
        if not include_results:
            # Keep list responses lightweight; the project modal loads the
            # selected record's full results through the detail endpoint.
            item.pop("results_json", None)
            item["results"] = None
        items.append(item)
    return items


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
    return _hydrate_project_record(record)


@router.post("")
async def save_project(
    req: SaveProjectRequest,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """Hesaplama sonucunu veritabanı geçmişine kaydeder."""
    normalized_inputs = normalize_project_inputs_cross_platform(req.inputs)
    history_id = db.save_calculation_history(
        project_name=req.project_name,
        calculation_type=req.calculation_type,
        inputs=normalized_inputs,
        results=_merge_module_payload(
            req.results,
            req.modules,
            req.station_data,
            selected_units=req.selected_units,
            charts=req.charts,
            warnings=req.warnings,
        ),
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


def _safe_download_filename(name: str, suffix: str, fallback: str = "kasp_project") -> str:
    """Strip path separators, quotes and control characters from a download name."""
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "").strip()).strip("._")
    return f"{base or fallback}{suffix}"


@router.post("/export-kasp")
async def export_kasp(
    req: ExportKaspRequest,
    user: dict = Depends(require_permission("export")),
):
    """Mevcut girdi ve sonuçları .kasp dosya formatında dışa aktarır."""
    import datetime
    pm = ProjectManager()
    normalized_inputs = normalize_project_inputs_cross_platform(req.inputs)
    project_data = {
        "schema_version": pm.VERSION,
        "timestamp": datetime.datetime.now().isoformat(),
        "inputs": normalized_inputs,
        "results": req.results,
        "selected_units": req.selected_units,
        "charts": req.charts,
        "warnings": req.warnings,
        "modules": req.modules or {},
        "station_data": req.station_data,
    }
    filename = _safe_download_filename(req.project_name, ".kasp")
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
    user: dict = Depends(require_permission("export")),
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
    filename = _safe_download_filename(req.project_name, "_Sonuclar.json")
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
    user: dict = Depends(require_permission("write")),
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
    res_dict = migrated_data.get("results") if isinstance(migrated_data.get("results"), dict) else {}

    return {
        "success": True,
        "schema_version": migrated_data.get("schema_version"),
        "timestamp": migrated_data.get("timestamp"),
        "inputs": migrated_data.get("inputs", {}),
        "results": migrated_data.get("results"),
        "selected_units": (
            migrated_data["selected_units"]
            if migrated_data.get("selected_units") is not None
            else (res_dict.get("selected_units") or [])
        ),
        "charts": (
            migrated_data["charts"]
            if migrated_data.get("charts") is not None
            else res_dict.get("charts")
        ),
        "warnings": (
            migrated_data["warnings"]
            if migrated_data.get("warnings") is not None
            else (res_dict.get("warnings") or [])
        ),
        "modules": migrated_data.get("modules") or res_dict.get("module_results") or {},
        "station_data": migrated_data.get("station_data") or res_dict.get("station_data"),
    }
