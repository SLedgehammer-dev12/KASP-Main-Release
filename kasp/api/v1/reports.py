"""Reports & PDF Streaming Router for KASP Web API v1.

Generates comprehensive in-memory engineering PDF reports using ReportLab
and streams them directly to the client with zero temporary disk I/O.
"""

import io
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kasp.api.auth import get_current_user, get_current_user_optional
from kasp.api.v1.calculations import get_thermo_engine
from kasp.core.thermo import ThermoEngine
from kasp.utils.reporting import REPORTLAB_LOADED, ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


class PdfReportRequest(BaseModel):
    inputs: Dict[str, Any]
    results: Dict[str, Any]
    selected_units: Optional[List[Dict[str, Any]]] = None
    report_units: Optional[Dict[str, str]] = None
    modules: Optional[Dict[str, Any]] = None
    station_data: Optional[Dict[str, Any]] = None
    filename: Optional[str] = "kasp_tasarim_raporu.pdf"


class PerformancePdfRequest(BaseModel):
    inputs: Dict[str, Any]
    results: Dict[str, Any]
    filename: Optional[str] = "asme_ptc10_performans_raporu.pdf"


class ModuleExcelRequest(BaseModel):
    inputs: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    selected_units: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[Any]] = None
    modules: Optional[Dict[str, Any]] = None
    station_data: Optional[Dict[str, Any]] = None
    filename: Optional[str] = "kasp_modul_raporu.xlsx"


@router.post("/pdf")
async def generate_pdf_report(
    req: PdfReportRequest,
    engine: ThermoEngine = Depends(get_thermo_engine),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """Hesaplama ve seçim sonuçlarını içeren kapsamlı PDF raporu oluşturup akış (stream) olarak döner."""
    if not REPORTLAB_LOADED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sunucuda ReportLab kütüphanesi yüklü değil.",
        )

    try:
        # Bellek içi BytesIO akışı
        pdf_stream = io.BytesIO()
        generator = ReportGenerator(pdf_stream, engine)

        report_results = dict(req.results or {})
        if req.modules:
            report_results["module_results"] = req.modules
        if req.station_data:
            report_results["station_data"] = req.station_data

        generator.generate_design_report(
            inputs=req.inputs,
            results=report_results,
            selected_units=req.selected_units or [],
            report_units=req.report_units,
        )

        pdf_stream.seek(0)
        filename = req.filename or "kasp_tasarim_raporu.pdf"
        if not filename.endswith(".pdf"):
            filename += ".pdf"

        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    except Exception as e:
        logger.error(f"PDF rapor oluşturma hatası: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF raporu oluşturulamadı: {str(e)}",
        )


@router.post("/modules-excel")
async def generate_module_excel_report(
    req: ModuleExcelRequest,
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """Tasarım + entegrasyon modülleri + istasyon sonuçlarını XLSX olarak döner."""
    try:
        from kasp.services.module_report_service import build_module_workbook

        workbook = build_module_workbook(
            inputs=req.inputs,
            results=req.results,
            modules=req.modules,
            station_data=req.station_data,
            selected_units=req.selected_units,
            warnings=req.warnings,
        )
        filename = req.filename or "kasp_modul_raporu.xlsx"
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
        return StreamingResponse(
            workbook,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    except Exception as e:
        logger.error(f"Excel modül raporu oluşturma hatası: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Excel raporu oluşturulamadı: {str(e)}",
        )


@router.post("/performance-pdf")
async def generate_performance_pdf_report(
    req: PerformancePdfRequest,
    engine: ThermoEngine = Depends(get_thermo_engine),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """ASME PTC-10 Saha Performans ve Sapma Doğrulama PDF raporunu akış olarak döner."""
    if not REPORTLAB_LOADED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sunucuda ReportLab kütüphanesi yüklü değil.",
        )

    try:
        pdf_stream = io.BytesIO()
        generator = ReportGenerator(pdf_stream, engine)
        generator.generate_performance_report(
            inputs=req.inputs,
            results=req.results,
        )
        pdf_stream.seek(0)
        filename = req.filename or "asme_ptc10_performans_raporu.pdf"
        if not filename.endswith(".pdf"):
            filename += ".pdf"

        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    except Exception as e:
        logger.error(f"PTC-10 PDF rapor oluşturma hatası: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performans PDF raporu oluşturulamadı: {str(e)}",
        )
