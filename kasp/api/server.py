import os
import sys
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from kasp.core.constants import DEFAULT_COMPOSITION, SUPPORTED_GASES, UNIT_OPTIONS
from kasp.core.contracts import DESIGN_INPUT_DEFAULTS, normalize_design_inputs
from kasp.core.properties import COOLPROP_LOADED, THERMO_LOADED
from kasp.core.thermo import ThermoEngine

app = FastAPI(title="KASP V4 API")


def _model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


@app.get("/api/constants")
async def get_constants():
    return {
        "gases": SUPPORTED_GASES,
        "units": UNIT_OPTIONS,
        "default_composition": DEFAULT_COMPOSITION,
    }


app.mount(
    "/static",
    StaticFiles(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), "../web"))),
    name="static",
)


@app.get("/")
async def read_index():
    return FileResponse(os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/index.html")))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ThermoEngine()


class DesignInputs(BaseModel):
    project_name: str = DESIGN_INPUT_DEFAULTS["project_name"]
    notes: str = DESIGN_INPUT_DEFAULTS["notes"]
    p_in: float
    p_in_unit: str = DESIGN_INPUT_DEFAULTS["p_in_unit"]
    t_in: float
    t_in_unit: str = DESIGN_INPUT_DEFAULTS["t_in_unit"]
    p_out: float
    p_out_unit: str = DESIGN_INPUT_DEFAULTS["p_out_unit"]
    flow: float
    flow_unit: str = DESIGN_INPUT_DEFAULTS["flow_unit"]
    gas_comp: Dict[str, float]
    eos_method: str = DESIGN_INPUT_DEFAULTS["eos_method"]
    method: str = DESIGN_INPUT_DEFAULTS["method"]
    poly_eff: float
    mech_eff: float = DESIGN_INPUT_DEFAULTS["mech_eff"]
    therm_eff: float = DESIGN_INPUT_DEFAULTS["therm_eff"]
    lhv_source: str = DESIGN_INPUT_DEFAULTS["lhv_source"]
    num_units: int = DESIGN_INPUT_DEFAULTS["num_units"]
    num_stages: int = DESIGN_INPUT_DEFAULTS["num_stages"]
    intercooler_t: float = DESIGN_INPUT_DEFAULTS["intercooler_t"]
    intercooler_dp_pct: float = DESIGN_INPUT_DEFAULTS["intercooler_dp_pct"]
    use_consistency_iteration: bool = DESIGN_INPUT_DEFAULTS["use_consistency_iteration"]
    consistency_check: Optional[bool] = None
    max_consistency_iter: int = DESIGN_INPUT_DEFAULTS["max_consistency_iter"]
    consistency_tolerance: float = DESIGN_INPUT_DEFAULTS["consistency_tolerance"]
    ambient_temp: float = DESIGN_INPUT_DEFAULTS["ambient_temp"]
    ambient_pressure: float = DESIGN_INPUT_DEFAULTS["ambient_pressure"]
    altitude: float = DESIGN_INPUT_DEFAULTS["altitude"]
    humidity: float = DESIGN_INPUT_DEFAULTS["humidity"]


@app.post("/api/calculate/design")
async def calculate_design(inputs: DesignInputs):
    try:
        input_data = normalize_design_inputs(_model_to_dict(inputs))
        results = engine.calculate_design_performance_with_mode(input_data)
        return results
    except Exception as e:
        import traceback

        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/calculate/benchmark")
async def calculate_benchmark(inputs: DesignInputs):
    results = []
    base_data = normalize_design_inputs(_model_to_dict(inputs))

    eos_options = ["coolprop", "pr", "srk"]
    method_options = [
        "Metot 1: Ortalama Özellikler",
        "Metot 2: Endpoint Yaklaşımı",
        "Metot 3: Artımlı Basınç",
    ]

    for eos in eos_options:
        for method in method_options:
            run_data = base_data.copy()
            run_data["eos_method"] = eos
            run_data["method"] = method

            try:
                res = engine.calculate_design_performance_with_mode(run_data)

                power_kw = res.get("power_shaft_total_kw", 0)
                t_out = res.get("t_out", 0)
                eff = res.get("actual_poly_efficiency", 0)

                head_kj_kg = 0
                if "stages" in res:
                    head_kj_kg = sum(stage.get("head_kj_kg", 0) for stage in res["stages"])

                results.append(
                    {
                        "eos": eos,
                        "method": method,
                        "power_kw": power_kw,
                        "t_out": t_out,
                        "head_kj_kg": head_kj_kg,
                        "eff": eff,
                        "status": "success",
                        "engine_version": res.get("engine_version", "legacy"),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "eos": eos,
                        "method": method,
                        "status": "error",
                        "error": str(e),
                    }
                )

    return results


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "coolprop_loaded": COOLPROP_LOADED,
        "thermo_loaded": THERMO_LOADED,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
