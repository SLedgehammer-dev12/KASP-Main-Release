"""Metadata, Thermo Constants & Gas / kij Matrix Router for KASP Web API v1.
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kasp.api.auth import get_current_user_optional
from kasp.core.constants import DEFAULT_COMPOSITION, SUPPORTED_GASES, UNIT_OPTIONS
from kasp.services.design_input_service import get_design_presets
from kasp.services.gas_service import (
    GAS_CATALOG,
    get_kij_matrix_data,
    get_smart_eos_recommendation,
    get_smart_method_recommendation,
    normalize_gas_composition,
)
from release_metadata import APP_VERSION

router = APIRouter(tags=["metadata"])


class GasRecommendationRequest(BaseModel):
    gas_comp: Dict[str, float]
    pressure_ratio: float = 1.0
    calc_method: Optional[str] = None


class KijMatrixRequest(BaseModel):
    gas_comp: Dict[str, float]
    custom_kij: Optional[Dict[str, float]] = None


@router.get("/meta/constants")
async def get_constants():
    """Genel sistem sabitleri, desteklenen gazlar ve birim seçenekleri."""
    return {
        "version": APP_VERSION,
        "gases": SUPPORTED_GASES,
        "units": UNIT_OPTIONS,
        "default_composition": DEFAULT_COMPOSITION,
    }


@router.get("/meta/presets")
async def get_presets():
    """Hazır 4 mühendislik önayarı (Doğalgaz, LNG, CO2, H2)."""
    return get_design_presets()


@router.get("/thermo/gases")
async def get_gases():
    """19 standart gazın fiziksel özellikleri ve katalog bilgileri."""
    return GAS_CATALOG


@router.post("/thermo/recommendations")
async def get_recommendations(req: GasRecommendationRequest):
    """Aktif gaz karışımı ve basınç oranına göre akıllı EOS ve Metot önerisi döner."""
    try:
        norm_comp = normalize_gas_composition(req.gas_comp)
        eos_rec = get_smart_eos_recommendation(norm_comp)
        method_rec = get_smart_method_recommendation(
            gas_comp=norm_comp,
            pr=req.pressure_ratio,
        )
        return {
            "recommended_eos": eos_rec.get("recommended_eos", "coolprop"),
            "recommended_method": method_rec.get("recommended_method", "Metot 1: Ortalama Özellikler"),
            "eos_reason": eos_rec.get("message", ""),
            "method_reason": method_rec.get("message", ""),
            "reason": f"{eos_rec.get('title', '')} - {method_rec.get('title', '')}",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Öneri hesaplanamadı: {str(e)}")


@router.post("/thermo/kij-matrix")
async def get_kij_matrix(req: KijMatrixRequest):
    """Aktif gaz karışımı için N x N ikili etkileşim katsayısı (k_ij) matrisini üretir."""
    try:
        matrix_data = get_kij_matrix_data(req.gas_comp, req.custom_kij)
        return matrix_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"k_ij matrisi oluşturulamadı: {str(e)}")
