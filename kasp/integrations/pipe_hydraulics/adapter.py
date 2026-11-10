"""Natural-gas hydraulic line sizing adapter.

Uses KASP's embedded Natural Gas Flow Calc engine (ASME B36.10M / API 5L /
API RP 14E / Churchill) and, when a composition is supplied, real-gas density,
viscosity and Z from the KASP thermodynamic solver (GERG-2008 by default).
"""

from __future__ import annotations

from typing import Any, Dict, List

from kasp.core.constants import MOLAR_MASSES, normalize_component
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.pipe_sizing import size_single_pipe
from kasp.core.properties import ThermodynamicSolver
from kasp.integrations.base import ModuleManifest, module_response


def _f(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mw_from_composition(composition: Dict[str, Any]) -> float:
    total = sum(max(0.0, _f(v, 0.0) or 0.0) for v in composition.values())
    if total <= 0:
        return 18.2
    mw = 0.0
    for name, value in composition.items():
        fraction = max(0.0, _f(value, 0.0) or 0.0) / total
        key = normalize_component(name)
        mw += fraction * MOLAR_MASSES.get(key, 16.04)
    return mw or 18.2


class PipeHydraulicsAdapter:
    manifest = ModuleManifest(
        id="pipe_hydraulics",
        name="Natural Gas Line Hydraulics",
        version="1.0.0",
        description="Velocity, minimum commercial diameter, Barlow thickness, erosion check and total pressure drop for station/process lines.",
        standards=["ASME B36.10M", "ASME B31.8", "API 5L", "API RP 14E", "Churchill (1977)"],
        source="KASP embedded Natural Gas Flow Calc engine",
        capabilities=["minimum_diameter", "velocity", "erosion", "barlow", "pressure_drop", "fittings", "elevation"],
    )

    def input_schema(self) -> Dict[str, Any]:
        return {
            "flow_kgs": "Mass flow, kg/s",
            "pressure_bar": "Operating pressure, bar(a)",
            "temp_c": "Operating temperature, °C",
            "composition": "Optional KASP gas composition, mol%",
            "mw": "Optional molecular weight, g/mol (if no composition)",
            "length_m": "Line length, m (default 100)",
            "fitting_k_total": "Sum of fitting K values (default 0)",
            "elevation_m": "Positive elevation rise, m (default 0)",
            "max_velocity_ms": "Design velocity limit, m/s (default 16)",
            "p_design_bar": "Barlow design pressure, bar(a)",
            "material": "API 5L grade (default API 5L X70)",
            "design_factor_F": "ASME B31.8 design factor (default 0.50)",
            "preferred_nominal": "Optional preferred NPS (e.g. '48')",
        }

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        flow_kgs = _f(payload.get("flow_kgs"), 0.0) or 0.0
        pressure_bar = _f(payload.get("pressure_bar"), 20.0)
        temp_c = _f(payload.get("temp_c"), 15.0)
        composition = payload.get("composition") or {}
        mw = _f(payload.get("mw"), _mw_from_composition(composition) if composition else 18.2)

        density = _f(payload.get("density_kgm3"))
        viscosity = _f(payload.get("viscosity_pa_s"))
        z_factor = _f(payload.get("z_factor"))
        warnings: List[str] = []

        if composition:
            try:
                solver = ThermodynamicSolver()
                gas_obj = GasMixtureBuilder.build_thermo_data(composition)
                eos = str(payload.get("eos", "gerg2008"))
                state = solver.get_properties(pressure_bar * 1e5, temp_c + 273.15, gas_obj, eos)
                density = state.density
                z_factor = state.Z
                mw = state.MW
                viscosity = state.raw_props.get("mu") or viscosity
            except Exception as exc:
                warnings.append(f"Gerçek gaz özellikleri alınamadı, yaklaşık korelasyona düşüldü: {exc}")

        result = size_single_pipe(
            flow_kgs=max(0.0001, flow_kgs),
            p_bar=pressure_bar,
            t_c=temp_c,
            mw=mw,
            max_velocity_ms=_f(payload.get("max_velocity_ms"), 16.0),
            p_design_bar=_f(payload.get("p_design_bar")),
            material=str(payload.get("material", "API 5L X70")),
            design_factor_F=_f(payload.get("design_factor_F"), 0.50),
            preferred_nominal=payload.get("preferred_nominal"),
            density_kgm3=density,
            viscosity_pa_s=viscosity,
            z_factor=z_factor,
            length_m=_f(payload.get("length_m"), 100.0),
            fitting_k_total=_f(payload.get("fitting_k_total"), 0.0),
            elevation_m=_f(payload.get("elevation_m"), 0.0),
        )

        recommendation = {
            "nominal_size_in": result.get("nominal_size_in"),
            "schedule": result.get("schedule"),
            "od_mm": result.get("od_mm"),
            "id_mm": result.get("id_mm"),
            "wall_thickness_mm": result.get("wall_thickness_mm"),
            "required_thickness_mm": result.get("min_required_thickness_mm"),
            "velocity_ms": result.get("actual_velocity_ms"),
            "erosion_ratio_pct": result.get("erosion_ratio_pct"),
            "pressure_drop_bar_total": result.get("pressure_drop_bar_total"),
            "outlet_pressure_bar": result.get("outlet_pressure_bar"),
            "velocity_status": result.get("velocity_status"),
            "standard": result.get("design_standard"),
        }
        if result.get("velocity_status") and not str(result["velocity_status"]).startswith("Optimum"):
            warnings.append(str(result["velocity_status"]))

        return module_response(
            self,
            {"recommendation": recommendation, "detail": result},
            warnings=warnings,
            provenance={
                "standard": "ASME B36.10M / ASME B31.8 / API RP 14E / Churchill (1977)",
                "source": "KASP core.pipe_sizing (embedded Natural Gas Flow Calc)",
                "gas_properties": "KASP GERG-2008" if composition else "approximate Lee-Gonzalez-Eakin",
            },
        )
