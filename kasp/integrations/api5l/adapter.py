"""API 5L / BOTAŞ pipe wall-thickness integration adapter.

Vendored engine: API 5L Pipe core (MIT).
Accepts SI inputs and returns a normalized recommendation plus the upstream
calculation detail (required thickness, selected schedule, BOTAŞ nominal
thickness, negative tolerance rule, sufficiency).
"""

from __future__ import annotations

from typing import Any, Dict, List

from kasp.integrations.api5l.vendor.wall_thickness_engine import WallThicknessEngine
from kasp.integrations.base import ModuleManifest, module_response

STANDARD_ALIASES = {
    "botas": "BOTAŞ",
    "botaş": "BOTAŞ",
    "api5l": "ASME B31.8 / ASME B31.4",
    "api 5l": "ASME B31.8 / ASME B31.4",
    "b318": "ASME B31.8 / ASME B31.4",
    "b31.8": "ASME B31.8 / ASME B31.4",
    "b313": "ASME B31.3",
    "b31.3": "ASME B31.3",
}

LOCATION_ALIASES = {
    "pipeline": "Pipeline",
    "hat": "Pipeline",
    "station": "Station",
    "istasyon": "Station",
    "pig": "Pig or Valve Station",
    "pig or valve station": "Pig or Valve Station",
    "vana": "Pig or Valve Station",
}


def _normalize_standard(value: Any) -> str:
    key = str(value or "BOTAŞ").strip().lower()
    return STANDARD_ALIASES.get(key, str(value or "BOTAŞ"))


def _normalize_location(value: Any) -> str:
    key = str(value or "Station").strip().lower()
    return LOCATION_ALIASES.get(key, str(value or "Station"))


def _f(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class API5LAdapter:
    manifest = ModuleManifest(
        id="api5l",
        name="API 5L / BOTAŞ Pipe Wall Thickness",
        version="1.0.0",
        description="Barlow wall thickness, ASME B36.10M schedule selection and BOTAŞ 5120_R7 / API 5L PSL2 comparison.",
        standards=["API Spec 5L (47th ed.)", "BOTAŞ 5120_R7", "ASME B31.8", "ASME B31.4", "ASME B31.3", "ASME B36.10M"],
        source="API 5L Pipe core (MIT)",
        capabilities=["barlow", "schedule_selection", "botas_matrix", "api5l_tolerance", "psl1_psl2"],
    )

    def input_schema(self) -> Dict[str, Any]:
        return {
            "diameter_in": "Nominal pipe size, inch (e.g. 48 or '48\"')",
            "material_grade": "API 5L grade (X42, X52, X60, X65, X70, ...)",
            "design_pressure_bar": "Design pressure, bar(a)",
            "design_factor_f": "ASME B31.8 design factor (0.50 station, 0.72 pipeline)",
            "location_type": "Pipeline | Station | Pig or Valve Station",
            "standard_code": "BOTAŞ | ASME B31.8 / ASME B31.4 | ASME B31.3",
            "manufacturing_process": "SMLS | ERW HFW | SAWH | SAWL",
            "psl_level": "PSL1 | PSL2",
            "corrosion_allowance_mm": "Default 0.0",
            "temperature_derating_factor_t": "Default 1.0",
            "apply_negative_tolerance": "Default true",
            "compare_standards": "If true, also compute the BOTAŞ and API 5L alternatives",
        }

    def _calculate_one(self, payload: Dict[str, Any], standard: str) -> Dict[str, Any]:
        diameter = payload.get("diameter_in", 48)
        if isinstance(diameter, (int, float)):
            diameter = str(diameter)
        return WallThicknessEngine.calculate_wall_thickness(
            diameter_inch=str(diameter),
            material_grade=str(payload.get("material_grade", "X65")),
            design_pressure_bar=_f(payload.get("design_pressure_bar"), 75.0),
            design_factor_f=_f(payload.get("design_factor_f"), 0.50),
            longitudinal_joint_factor_e=_f(payload.get("longitudinal_joint_factor_e"), 1.0),
            temperature_derating_factor_t=_f(payload.get("temperature_derating_factor_t"), 1.0),
            corrosion_allowance_mm=_f(payload.get("corrosion_allowance_mm"), 0.0),
            location_type=_normalize_location(payload.get("location_type")),
            standard_code=standard,
            manufacturing_process=str(payload.get("manufacturing_process", "SAWH")),
            apply_negative_tolerance=bool(payload.get("apply_negative_tolerance", True)),
            manual_negative_tolerance_percent=_f(payload.get("manual_negative_tolerance_percent")),
            psl_level=str(payload.get("psl_level", "PSL2")),
        )

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        standard = _normalize_standard(payload.get("standard_code"))
        raw = self._calculate_one(payload, standard)
        cr = raw.get("calculation_results", {})
        ip = raw.get("input_parameters", {})

        recommendation = {
            "nominal_size_in": ip.get("diameter_inch", payload.get("diameter_in")),
            "od_mm": ip.get("diameter_mm"),
            "material_grade": ip.get("material_grade"),
            "standard": standard,
            "psl_level": ip.get("psl_level"),
            "location_type": ip.get("location_type"),
            "required_thickness_mm": cr.get("t_required_asme_b31_8_mm"),
            "selected_nominal_thickness_mm": cr.get("selected_nominal_thickness_asme_b36_10_mm"),
            "botas_standard_thickness_mm": cr.get("botas_standard_thickness_mm"),
            "botas_standard_label": cr.get("botas_standard_label"),
            "minimum_standard_thickness_mm": cr.get("t_min_standard_mm"),
            "tolerance_rule": cr.get("standard_tolerance_rule"),
            "tolerance_percent": cr.get("tolerance_percent_used"),
            "is_sufficient": cr.get("is_nominal_sufficient"),
            "available_schedules": cr.get("available_schedule_thicknesses", []),
        }

        results = {"recommendation": recommendation, "detail": raw}
        warnings: List[str] = []
        if cr.get("is_nominal_sufficient") is False:
            warnings.append("Seçilen nominal et kalınlığı Barlow gereksinimini karşılamıyor.")
        if not cr.get("botas_standard_thickness_mm"):
            warnings.append("Bu çap için BOTAŞ standart et kalınlığı matrisi kaydı bulunamadı.")

        if bool(payload.get("compare_standards", False)):
            alternatives = {}
            for alt_standard in ("BOTAŞ", "ASME B31.8 / ASME B31.4"):
                try:
                    alt_raw = self._calculate_one(payload, alt_standard)
                    alternatives[alt_standard] = {
                        "required_thickness_mm": alt_raw["calculation_results"].get("t_required_asme_b31_8_mm"),
                        "selected_nominal_thickness_mm": alt_raw["calculation_results"].get("selected_nominal_thickness_asme_b36_10_mm"),
                        "botas_standard_thickness_mm": alt_raw["calculation_results"].get("botas_standard_thickness_mm"),
                        "is_sufficient": alt_raw["calculation_results"].get("is_nominal_sufficient"),
                    }
                except Exception as exc:
                    alternatives[alt_standard] = {"error": str(exc)}
            results["comparison"] = alternatives

        return module_response(
            self,
            results,
            warnings=warnings,
            provenance={
                "standard": "API Spec 5L / BOTAŞ 5120_R7 / ASME B31.8 / ASME B36.10M",
                "source": "API 5L Pipe core (MIT)",
                "engine_version": "1.0.0",
            },
        )
