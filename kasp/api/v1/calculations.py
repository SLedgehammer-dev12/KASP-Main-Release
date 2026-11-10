"""Calculation Router for KASP Web API v1.

Endpoints for Design Calculation (2-stage compression + 146+ turbine selection + charts)
and ASME PTC-10 Off-Design Performance Evaluation.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from kasp.api.auth import get_current_user_optional, require_permission
from kasp.core.thermo import ThermoEngine
from kasp.services.calculation_service import execute_design_calculation
from kasp.services.chart_data_builder import build_all_chart_payloads
from kasp.services.performance_service import evaluate_ptc10_performance
from kasp.services.validation_service import validate_design_inputs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calculations", tags=["calculations"])

# Shared engine instance
_engine: Optional[ThermoEngine] = None


def get_thermo_engine() -> ThermoEngine:
    global _engine
    if _engine is None:
        _engine = ThermoEngine()
    return _engine


class DesignCalculationRequest(BaseModel):
    project_name: str = "Yeni Proje"
    p_in: float
    p_in_unit: str = "bar(a)"
    p_out: float
    p_out_unit: str = "bar(a)"
    t_in: float
    t_in_unit: str = "°C"
    flow: float = Field(..., gt=0)
    flow_unit: str = "kg/s"
    gas_comp: Dict[str, float]
    eos_model: str = "pr"
    calc_method: str = "Metot 6: Schultz 3-Üslü Gerçek Gaz"
    poly_eff: float = Field(default=80.0, gt=0, le=100)
    mech_eff: float = Field(default=98.0, gt=0, le=100)
    therm_eff: float = Field(default=35.0, gt=0, le=100)
    num_units: int = Field(default=1, ge=1, le=100)
    num_stages: int = Field(default=1, ge=1, le=20)
    intercooler_t: float = 35.0
    intercooler_dp_pct: float = 2.0
    theme: str = "light"
    custom_kij: Optional[Dict[str, float]] = None
    enable_uncertainty: bool = False


class PerformanceCalculationRequest(BaseModel):
    field_data: Dict[str, Any]
    design_point: Optional[Dict[str, Any]] = None


@router.post("/design")
async def calculate_design(
    req: DesignCalculationRequest,
    engine: ThermoEngine = Depends(get_thermo_engine),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Kapsamlı kompresör tasarım hesaplamasını yürütür.

    2 kademe termodinamik sonuçları, API 617 1.04 marjlı türbin seçimi
    ve 8 adet interaktif Plotly.js grafik verisini tek seferde döner.
    FastAPI event loop'u bloke etmemek için hesaplamayı worker thread'de çalıştırır.
    """
    input_dict = req.dict() if hasattr(req, "dict") else req.model_dump()

    # Doğrulama
    val_res = validate_design_inputs(input_dict)
    if not val_res["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": val_res["errors"], "warnings": val_res["warnings"]},
        )

    try:
        results = await asyncio.to_thread(execute_design_calculation, input_dict, engine=engine)
        selected_units = results.get("selected_units", [])

        # Plotly grafik serileri ve SVG mimari diyagramı oluştur
        charts = await asyncio.to_thread(
            build_all_chart_payloads,
            inputs=input_dict,
            results=results,
            selected_units=selected_units,
            engine=engine,
            theme_name=req.theme or "light",
        )

        return {
            "success": True,
            "warnings": val_res["warnings"],
            "inputs": input_dict,
            "results": results,
            "selected_units": selected_units,
            "charts": charts,
        }

    except Exception as e:
        logger.error(f"Design calculation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hesaplama hatası: {str(e)}",
        )


@router.post("/performance")
async def calculate_performance(
    req: PerformanceCalculationRequest,
    engine: ThermoEngine = Depends(get_thermo_engine),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Saha test verilerini ASME PTC-10 standartlarına göre tasarım noktasıyla kıyaslar."""
    try:
        ptc10_results = await asyncio.to_thread(
            evaluate_ptc10_performance,
            test_data=req.field_data,
            design_point=req.design_point,
            engine=engine,
        )
        return ptc10_results
    except Exception as e:
        logger.error(f"Performance calculation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performans değerlendirme hatası: {str(e)}",
        )


class StationCalculationRequest(BaseModel):
    inputs: Dict[str, Any]
    design_results: Optional[Dict[str, Any]] = None


@router.post("/station")
async def calculate_station_model(
    req: StationCalculationRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Kompresör istasyonu boru içi akış, siklon seperatör, filtre, ünite binası, anti-surge, hava soğutucu ve pigging modellemesi."""
    try:
        from kasp.services.station_service import calculate_station_process_model
        return await asyncio.to_thread(
            calculate_station_process_model,
            inputs=req.inputs,
            design_results=req.design_results,
        )
    except Exception as e:
        logger.error(f"Station calculation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"İstasyon modelleme hatası: {str(e)}",
        )


class PipeSizingRequest(BaseModel):
    flow: float
    flow_unit: str = "kg/s"
    pressure_bar: float
    temp_c: float = 20.0
    gas_mw: float = 18.2
    max_velocity_ms: float = 16.0
    design_pressure_bar: Optional[float] = None
    pipe_material: str = "API 5L X70"
    design_factor_F: float = 0.50
    preferred_nominal: Optional[str] = None


@router.post("/pipe-sizing")
async def calculate_pipe_sizing(
    req: PipeSizingRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Natural Gas Flow Calc ASME B36.10M / API 5L boru boyutlandırma ve erozyon hızı analizi."""
    try:
        from kasp.core.pipe_sizing import size_single_pipe
        flow_kgs = float(req.flow)
        if req.flow_unit == "MMSCMD":
            R_gas = 8314.462 / req.gas_mw
            rho_std = 1.01325e5 / (R_gas * 288.15)
            flow_kgs = (req.flow * 1e6 * rho_std) / 86400.0
        elif req.flow_unit == "t/h":
            flow_kgs = (req.flow * 1000.0) / 3600.0

        return await asyncio.to_thread(
            size_single_pipe,
            flow_kgs=flow_kgs,
            p_bar=req.pressure_bar,
            t_c=req.temp_c,
            mw=req.gas_mw,
            max_velocity_ms=req.max_velocity_ms,
            p_design_bar=req.design_pressure_bar,
            material=req.pipe_material,
            design_factor_F=req.design_factor_F,
            preferred_nominal=req.preferred_nominal,
        )
    except Exception as e:
        logger.error(f"Pipe sizing calculation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Boru boyutlandırma hatası: {str(e)}",
        )
