from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from kasp.core.thermo import ThermoEngine
from kasp.core.constants import SUPPORTED_GASES, UNIT_OPTIONS, DEFAULT_COMPOSITION

app = FastAPI(title="KASP V4 API")

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

# Enable CORS for React frontend (just in case they install node later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ThermoEngine()

class DesignInputs(BaseModel):
    project_name: str = "Web Project"
    p_in: float
    p_in_unit: str = "bar(a)"
    t_in: float
    t_in_unit: str = "°C"
    p_out: float
    p_out_unit: str = "bar(a)"
    flow: float
    flow_unit: str = "kg/s"
    gas_comp: Dict[str, float]
    eos_method: str = "coolprop"
    method: str = "Metot 1: Ortalama Özellikler"
    poly_eff: float
    mech_eff: float = 98.0
    therm_eff: float = 35.0
    num_units: int = 1
    num_stages: int = 1
    intercooler_t: float = 40.0
    intercooler_dp_pct: float = 2.0
    consistency_check: bool = True

@app.post("/api/calculate/design")
async def calculate_design(inputs: DesignInputs):
    try:
        # Convert Pydantic model to dict
        input_data = inputs.dict()
        results = engine.calculate_design_performance(input_data)
        return results
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/calculate/benchmark")
async def calculate_benchmark(inputs: DesignInputs):
    results = []
    base_data = inputs.dict()
    
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
                results.append({
                    "eos": eos,
                    "method": method,
                    "status": "error",
                    "error": str(e)
                })
                
    return results

@app.get("/api/health")
async def health():
    return {"status": "healthy", "coolprop_loaded": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
