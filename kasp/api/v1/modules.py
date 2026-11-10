"""Integration modules router for KASP Web API v1."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from kasp.api.auth import get_current_user_optional
from kasp.integrations.registry import calculate_module, get_adapter, list_modules

router = APIRouter(prefix="/modules", tags=["modules"])


class ModuleCalculationRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def get_modules(current_user: Dict[str, Any] | None = Depends(get_current_user_optional)):
    """Kayıtlı entegrasyon modüllerini listeler."""
    return {"modules": list_modules()}


@router.get("/{module_id}/schema")
async def get_module_schema(
    module_id: str,
    current_user: Dict[str, Any] | None = Depends(get_current_user_optional),
):
    adapter = get_adapter(module_id)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modül bulunamadı.")
    return {
        "module": adapter.manifest.to_dict(),
        "input_schema": adapter.input_schema(),
    }


@router.post("/{module_id}/calculate")
async def run_module_calculation(
    module_id: str,
    req: ModuleCalculationRequest,
    current_user: Dict[str, Any] | None = Depends(get_current_user_optional),
):
    adapter = get_adapter(module_id)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modül bulunamadı.")
    try:
        return calculate_module(module_id, req.payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Modül hesaplama hatası: {exc}",
        )
