"""Equipment Catalog (Turbines & Compressors) Router for KASP Web API v1.

Provides full CRUD operations matching desktop database functionality.
Protected by RBAC ('read', 'write', 'delete').
"""

import csv
import io
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from kasp.api.auth import get_db, require_permission
from kasp.data.database import UnitDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipment", tags=["equipment"])


class TurbineCreateRequest(BaseModel):
    manufacturer: str
    model: str
    type: str = "Industrial"
    iso_power_kw: float = Field(..., gt=0)
    iso_heat_rate_kj_kwh: float = Field(..., gt=0)
    surge_flow: float = 0.0
    stonewall_flow: float = 0.0
    max_pressure_ratio: float = 10.0
    min_flow_kgs: float = 0.0
    max_flow_kgs: float = 1000.0
    fuel_type: str = "Natural Gas"
    performance_correction_data: Optional[Dict[str, Any]] = None


class TurbineUpdateRequest(BaseModel):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    type: Optional[str] = None
    iso_power_kw: Optional[float] = None
    iso_heat_rate_kj_kwh: Optional[float] = None
    surge_flow: Optional[float] = None
    stonewall_flow: Optional[float] = None
    max_pressure_ratio: Optional[float] = None
    min_flow_kgs: Optional[float] = None
    max_flow_kgs: Optional[float] = None
    fuel_type: Optional[str] = None
    performance_correction_data: Optional[Dict[str, Any]] = None


class CompressorCreateRequest(BaseModel):
    manufacturer: str
    model: str
    max_pressure_ratio: float = Field(..., gt=1.0)
    min_flow_kgs: float = Field(..., ge=0)
    max_flow_kgs: float = Field(..., gt=0)
    performance_map_data: Optional[Dict[str, Any]] = None


class CompressorUpdateRequest(BaseModel):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    max_pressure_ratio: Optional[float] = None
    min_flow_kgs: Optional[float] = None
    max_flow_kgs: Optional[float] = None
    performance_map_data: Optional[Dict[str, Any]] = None


# ────────────────────────────────── Turbines ──────────────────────────────────

@router.get("/turbines")
async def get_all_turbines(db: UnitDatabase = Depends(get_db)):
    """Tüm türbin kataloğunu (146+ model) listeler."""
    return db.get_all_turbines_full_data()


@router.get("/turbines/{turbine_id}")
async def get_turbine(turbine_id: int, db: UnitDatabase = Depends(get_db)):
    """Belirtilen ID'ye sahip türbini getirir."""
    t = db.get_turbine_by_id(turbine_id)
    if not t:
        raise HTTPException(status_code=404, detail="Türbin bulunamadı.")
    return t


@router.post("/turbines")
async def add_turbine(
    req: TurbineCreateRequest,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """Kataloğa yeni türbin ekler."""
    data = req.dict() if hasattr(req, "dict") else req.model_dump()
    ok = db.add_turbine(data)
    if not ok:
        raise HTTPException(status_code=400, detail="Türbin eklenemedi (üretici ve model benzersiz olmalıdır).")
    return {"message": f"Türbin '{req.model}' başarıyla eklendi."}


@router.put("/turbines/{turbine_id}")
async def update_turbine(
    turbine_id: int,
    req: TurbineUpdateRequest,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """Türbin verilerini günceller."""
    data = {k: v for k, v in (req.dict() if hasattr(req, "dict") else req.model_dump()).items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi.")
    ok = db.update_turbine(turbine_id, data)
    if not ok:
        raise HTTPException(status_code=400, detail="Türbin güncellenemedi veya bulunamadı.")
    return {"message": "Türbin başarıyla güncellendi."}


@router.delete("/turbines/{turbine_id}")
async def delete_turbine(
    turbine_id: int,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("delete")),
):
    """Türbini katalogdan siler."""
    ok = db.delete_turbine(turbine_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Türbin silinemedi veya bulunamadı.")
    return {"message": "Türbin başarıyla silindi."}


@router.post("/turbines/import-csv")
async def import_turbines_csv(
    file: UploadFile = File(...),
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """CSV dosyasından türbin verilerini toplu olarak içe aktarır."""
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except Exception:
        text = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    errors = []

    for idx, row in enumerate(reader, start=2):
        try:
            mfg = row.get("manufacturer") or row.get("Manufacturer") or "Bilinmeyen"
            model = row.get("model") or row.get("Model")
            if not model:
                continue
            iso_power = float(row.get("iso_power_kw") or row.get("power") or row.get("Power_kW") or 5000.0)
            heat_rate = float(row.get("iso_heat_rate_kj_kwh") or row.get("heat_rate") or 10000.0)
            data = {
                "manufacturer": mfg.strip(),
                "model": model.strip(),
                "type": (row.get("type") or "Industrial").strip(),
                "iso_power_kw": iso_power,
                "iso_heat_rate_kj_kwh": heat_rate,
                "surge_flow": float(row.get("surge_flow") or 0.0),
                "stonewall_flow": float(row.get("stonewall_flow") or 0.0),
                "max_pressure_ratio": float(row.get("max_pressure_ratio") or 10.0),
                "min_flow_kgs": float(row.get("min_flow_kgs") or 0.0),
                "max_flow_kgs": float(row.get("max_flow_kgs") or 1000.0),
                "fuel_type": (row.get("fuel_type") or "Natural Gas").strip(),
            }
            if db.add_turbine(data):
                imported += 1
        except Exception as e:
            errors.append(f"Satır {idx}: {str(e)}")

    return {
        "success": True,
        "imported_count": imported,
        "errors": errors[:10],
    }


# ───────────────────────────────── Compressors ─────────────────────────────────

@router.get("/compressors")
async def get_all_compressors(db: UnitDatabase = Depends(get_db)):
    """Tüm kompresör kataloğunu listeler."""
    return db.get_all_compressors_full_data()


@router.post("/compressors")
async def add_compressor(
    req: CompressorCreateRequest,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """Kataloğa yeni kompresör ekler."""
    data = req.dict() if hasattr(req, "dict") else req.model_dump()
    ok = db.add_compressor(data)
    if not ok:
        raise HTTPException(status_code=400, detail="Kompresör eklenemedi (model benzersiz olmalıdır).")
    return {"message": f"Kompresör '{req.model}' başarıyla eklendi."}


@router.put("/compressors/{compressor_id}")
async def update_compressor(
    compressor_id: int,
    req: CompressorUpdateRequest,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("write")),
):
    """Kompresör verilerini günceller."""
    data = {k: v for k, v in (req.dict() if hasattr(req, "dict") else req.model_dump()).items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi.")
    ok = db.update_compressor(compressor_id, data)
    if not ok:
        raise HTTPException(status_code=400, detail="Kompresör güncellenemedi veya bulunamadı.")
    return {"message": "Kompresör başarıyla güncellendi."}


@router.delete("/compressors/{compressor_id}")
async def delete_compressor(
    compressor_id: int,
    db: UnitDatabase = Depends(get_db),
    user: dict = Depends(require_permission("delete")),
):
    """Kompresörü katalogdan siler."""
    ok = db.delete_compressor(compressor_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Kompresör silinemedi veya bulunamadı.")
    return {"message": "Kompresör başarıyla silindi."}
