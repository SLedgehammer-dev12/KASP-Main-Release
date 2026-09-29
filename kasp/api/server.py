"""
KASP V4 API - LEGACY/EXPERIMENTAL

UYARI: Bu sunucu legacy/experimental olarak işaretlenmiştir. Varsayılan olarak
KAPALIDIR; yalnızca KASP_API_ENABLE=1 ve KASP_API_TOKEN ayarlandığında başlar.
Kimlik doğrulama (Bearer token) ve hız sınırlama uygulanır.
"""
import hmac
import os
import sys
import time
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from kasp.core.thermo import ThermoEngine
from kasp.core.properties import COOLPROP_LOADED
from kasp.core.constants import SUPPORTED_GASES, UNIT_OPTIONS, DEFAULT_COMPOSITION


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


API_ENABLED = _env_flag("KASP_API_ENABLE", False)
API_TOKEN = (os.environ.get("KASP_API_TOKEN") or "").strip()
_RAW_ORIGINS = os.environ.get("KASP_API_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _RAW_ORIGINS.split(",") if o.strip()] or [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
try:
    RATE_LIMIT_PER_MIN = max(1, int(os.environ.get("KASP_API_RATE_LIMIT", "60")))
except ValueError:
    RATE_LIMIT_PER_MIN = 60

app = FastAPI(
    title="KASP V4 API",
    description="Legacy/Experimental API - requires Bearer token; not for production use",
    version="0.1.0-legacy"
)

if not API_ENABLED:
    logger.warning("KASP V4 API (LEGACY) devre dışı. Etkinleştirmek için KASP_API_ENABLE=1 ayarlayın.")
else:
    logger.warning("⚠️ KASP V4 API (LEGACY) başlatıldı. Üretim kullanımı için tasarlanmamıştır.")


def require_auth(authorization: Optional[str] = Header(default=None)):
    """Bearer token doğrulaması (sabit-zamanlı karşılaştırma)."""
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="API token yapılandırılmamış (KASP_API_TOKEN).")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Yetkilendirme başlığı gerekli (Bearer).")
    provided = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(provided, API_TOKEN):
        raise HTTPException(status_code=403, detail="Geçersiz API token.")


_rate_buckets: Dict[str, list] = defaultdict(list)


def rate_limit(request: Request):
    """IP bazlı dakikalık sabit pencere hız sınırı."""
    client_host = request.client.host if request.client else "unknown"
    now = time.time()
    # Evict stale IP buckets periodically
    for ip in list(_rate_buckets.keys()):
        _rate_buckets[ip] = [t for t in _rate_buckets[ip] if now - t < 60.0]
        if not _rate_buckets[ip] and ip != client_host:
            del _rate_buckets[ip]
    bucket = _rate_buckets[client_host]
    if len(bucket) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Hız sınırı aşıldı.")
    bucket.append(now)


_PROTECTED = [Depends(require_auth), Depends(rate_limit)]


@app.get("/api/constants")
async def get_constants():
    return {
        "gases": SUPPORTED_GASES,
        "units": UNIT_OPTIONS,
        "default_composition": DEFAULT_COMPOSITION
    }

# Mount Static Files
app.mount("/static", StaticFiles(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), "../web"))), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/index.html")))

# CORS - yalnizca yapilandirilmis origin'ler (varsayilan: yerel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

engine = ThermoEngine()

class DesignInputs(BaseModel):
    project_name: str = "Web Project"
    p_in: float = Field(..., allow_inf_nan=False)
    p_in_unit: str = "bar(a)"
    t_in: float = Field(..., allow_inf_nan=False)
    t_in_unit: str = "°C"
    p_out: float = Field(..., allow_inf_nan=False)
    p_out_unit: str = "bar(a)"
    flow: float = Field(..., gt=0, allow_inf_nan=False)
    flow_unit: str = "kg/s"
    gas_comp: Dict[str, float]
    eos_method: str = "coolprop"
    method: str = "Metot 1: Ortalama Özellikler"
    poly_eff: float = Field(..., gt=0, le=100, allow_inf_nan=False)
    mech_eff: float = Field(default=98.0, gt=0, le=100, allow_inf_nan=False)
    therm_eff: float = Field(default=35.0, gt=0, le=100, allow_inf_nan=False)
    num_units: int = Field(default=1, ge=1, le=100)
    num_stages: int = Field(default=1, ge=1, le=20)
    intercooler_t: float = Field(default=40.0, allow_inf_nan=False)
    intercooler_dp_pct: float = Field(default=2.0, ge=0, lt=100, allow_inf_nan=False)
    consistency_check: bool = True

@app.post("/api/calculate/design", dependencies=_PROTECTED)
async def calculate_design(inputs: DesignInputs):
    try:
        # Convert Pydantic model to dict
        input_data = inputs.model_dump() if hasattr(inputs, "model_dump") else inputs.dict()
        # Tutarlilik modu secimi calculate_design_performance_with_mode ile uygulanir (P1)
        input_data["use_consistency_iteration"] = bool(inputs.consistency_check)
        results = engine.calculate_design_performance_with_mode(input_data)
        return results
    except Exception as e:
        logger.error("API calculation error: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail="Hesaplama sırasında bir hata oluştu. Lütfen girdi parametrelerini kontrol edin.")

@app.post("/api/calculate/benchmark", dependencies=_PROTECTED)
async def calculate_benchmark(inputs: DesignInputs):
    results = []
    base_data = inputs.model_dump() if hasattr(inputs, "model_dump") else inputs.dict()
    
    eos_options = ['coolprop', 'pr', 'srk']
    method_options = ['Metot 1: Ortalama Özellikler', 'Metot 2: Endpoint Yaklaşımı', 'Metot 3: Artımlı Basınç']
    
    for eos in eos_options:
        for method in method_options:
            run_data = base_data.copy()
            run_data['eos_method'] = eos
            run_data['method'] = method
            
            try:
                res = engine.calculate_design_performance(run_data)
                
                # Extract simplified metrics
                power_kw = res.get('power_shaft_total_kw', 0)
                t_out = res.get('t_out', 0)
                eff = res.get('actual_poly_efficiency', 0)
                
                # Try to get head (sum of stages)
                head_kj_kg = 0
                if 'stages' in res:
                    head_kj_kg = sum(s.get('head_kj_kg', 0) for s in res['stages'])
                
                results.append({
                    "eos": eos,
                    "method": method,
                    "power_kw": power_kw,
                    "t_out": t_out,
                    "head_kj_kg": head_kj_kg,
                    "eff": eff,
                    "status": "success",
                    "engine_version": res.get('engine_version', 'legacy')
                })
            except Exception as e:
                logger.error("API benchmark calculation error (%s / %s): %s", eos, method, e, exc_info=True)
                results.append({
                    "eos": eos,
                    "method": method,
                    "status": "error",
                    "error": "Hesaplama hatası oluştu."
                })
                
    return results

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "api_enabled": API_ENABLED,
        "coolprop_loaded": bool(COOLPROP_LOADED),
    }

if __name__ == "__main__":
    if not API_ENABLED:
        logger.warning(
            "KASP API devre dışı. Etkinleştirmek için KASP_API_ENABLE=1 ve KASP_API_TOKEN ayarlayın."
        )
        raise SystemExit(0)
    if not API_TOKEN:
        logger.error("KASP_API_TOKEN ayarlı değil; API başlatılmıyor (güvenlik).")
        raise SystemExit(1)
    host = os.environ.get("KASP_API_HOST", "127.0.0.1")
    port = int(os.environ.get("KASP_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
