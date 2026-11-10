"""Air-Cooler-Main integration adapter (API 661 / ASME VIII-1 screening).

Vendored engine: Air-Cooler-Main core.
The adapter accepts KASP SI inputs and returns heat duty, U, required/actual
area, gas-side pressure drop, fan power and API 661 checks.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

from kasp.core.constants import normalize_component
from kasp.integrations.base import ModuleManifest, module_response

_VENDOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "vendor"))
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

from air_cooler_main_core import AirFinnedGasCooler  # noqa: E402

import pint  # noqa: E402

_UREG = pint.UnitRegistry()
_Q = _UREG.Quantity

_COOLER_NAMES = {
    "METHANE": "METHANE",
    "ETHANE": "ETHANE",
    "PROPANE": "PROPANE",
    "ISOBUTANE": "ISOBUTANE",
    "BUTANE": "N-BUTANE",
    "ISOPENTANE": "ISOPENTANE",
    "PENTANE": "N-PENTANE",
    "HEXANE": "N-HEXANE",
    "HEPTANE": "N-HEPTANE",
    "OCTANE": "N-OCTANE",
    "NONANE": "N-NONANE",
    "DECANE": "N-DECANE",
    "HYDROGEN": "HYDROGEN",
    "HYDROGENSULFIDE": "HYDROGENSULFIDE",
    "NITROGEN": "NITROGEN",
    "CARBONDIOXIDE": "CARBONDIOXIDE",
    "WATER": "WATER",
    "OXYGEN": "OXYGEN",
    "ARGON": "ARGON",
    "HELIUM": "HELIUM",
    "AIR": "AIR",
}

DEFAULT_GEOMETRY = {
    "tube_rows": 4,
    "tube_passes": 2,
    "tubes_per_row": 24,
    "tube_length": 6.0,
    "tube_od": 0.0254,
    "tube_thickness": 0.00211,
    "fin_height": 0.0159,
    "fin_thickness": 0.0004,
    "fin_density": 393.7,
    "fin_type": "Kıvrımlı (CR)",
    "header_type": "Küresel",
    "pitch": 0.0635,
    "angle": 30,
    "tube_k": 45.0,
    "fin_k": 205.0,
    "fouling_in": 0.000176,
    "fouling_out": 0.000088,
    "fan_efficiency": 0.65,
    "fan_diameter": 2.44,
    "n_fans": 1,
    "fan_rpm": 350,
    "draft_type": "Forced",
}


def _f(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cooler_composition(composition: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not composition:
        return {}
    total = sum(max(0.0, _f(v, 0.0) or 0.0) for v in composition.values())
    if total <= 0:
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for name, value in composition.items():
        fraction = max(0.0, _f(value, 0.0) or 0.0) / total * 100.0
        if fraction <= 0:
            continue
        key = normalize_component(name)
        cooler_name = _COOLER_NAMES.get(key, key)
        result[cooler_name] = {"yuzde": fraction, "tip": "Molar"}
    return result


class AirCoolerAdapter:
    manifest = ModuleManifest(
        id="air_cooler",
        name="Fin-Fan Gas Air Cooler",
        version="5.0.0",
        description="Real-gas fin-fan cooler thermal design, LMTD/U/area, API 661 fan and tube checks.",
        standards=["API 661", "ASME BPVC Section VIII Div. 1", "TEMA"],
        source="Air-Cooler-Main core",
        capabilities=["heat_duty", "lmtd", "u_value", "area_sizing", "gas_dp", "fan_power", "api661_checks"],
    )

    def input_schema(self) -> Dict[str, Any]:
        return {
            "composition": "KASP gas composition, mol%",
            "mass_flow_kgs": "Gas mass flow, kg/s",
            "p_in_bar": "Cooler inlet pressure, bar(a)",
            "p_out_bar": "Cooler outlet pressure, bar(a) (default p_in - 0.4)",
            "t_in_c": "Gas inlet temperature, °C",
            "t_out_c": "Gas outlet temperature, °C",
            "air_in_c": "Ambient air inlet, °C (default 15)",
            "air_out_c": "Air outlet, °C (default air_in + 20)",
            "auto_size": "Iterate tubes_per_row to reach min overdesign (default true)",
            "min_overdesign_pct": "Default 5.0",
            "max_gas_dp_bar": "Default 0.50",
            "geometry": "Optional dict overriding DEFAULT_GEOMETRY",
        }

    def _run_once(self, composition, payload, geometry):
        cooler_comp = _cooler_composition(composition)
        if not cooler_comp:
            raise ValueError("Air cooler için geçerli gaz kompozisyonu gerekli.")
        cooler = AirFinnedGasCooler(
            cooler_comp,
            engine=str(payload.get("engine", "CoolProp")),
            eos=str(payload.get("eos", "HEOS")),
            raw_p_unit=str(payload.get("p_unit", "bar(a)")),
        )
        p_in = _f(payload.get("p_in_bar"), 60.0)
        p_out = _f(payload.get("p_out_bar"), max(0.1, p_in - 0.4))
        t_in = _f(payload.get("t_in_c"), 84.4)
        t_out = _f(payload.get("t_out_c"), 45.0)
        air_in = _f(payload.get("air_in_c"), 15.0)
        air_out = _f(payload.get("air_out_c"), air_in + 20.0)
        result = cooler.hesapla_detayli_dizayn(
            _f(payload.get("mass_flow_kgs"), 12.0),
            "kg/s",
            _Q(p_in, "bar"),
            _Q(p_out, "bar"),
            _Q(t_in, "degC"),
            _Q(t_out, "degC"),
            _Q(air_in, "degC"),
            _Q(air_out, "degC"),
            geometry,
        )
        return result

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        composition = payload.get("composition") or {}
        geometry = dict(DEFAULT_GEOMETRY)
        geometry.update(payload.get("geometry") or {})
        warnings: List[str] = []

        auto_size = bool(payload.get("auto_size", True))
        min_overdesign = _f(payload.get("min_overdesign_pct"), 5.0)
        max_dp = _f(payload.get("max_gas_dp_bar"), 0.50)
        best = None
        attempts = 0
        max_tubes = int(_f(payload.get("max_tubes_per_row"), 120))

        while True:
            attempts += 1
            result = self._run_once(composition, payload, geometry)
            result["_geometry"] = dict(geometry)
            best = result
            overdesign = float(result.get("overdesign_pct") or 0.0)
            gas_dp = float(result.get("gas_dP_bar") or 0.0)
            if not auto_size:
                break
            if overdesign >= min_overdesign and gas_dp <= max_dp:
                break
            if int(geometry.get("tubes_per_row", 24)) >= max_tubes:
                warnings.append("Otomatik boyutlandırma maksimum tüp sayısına ulaştı.")
                break
            # Increase surface in ~8% steps; this also lowers gas velocity/dP.
            geometry["tubes_per_row"] = min(
                max_tubes,
                max(int(geometry.get("tubes_per_row", 24)) + 4, int(int(geometry.get("tubes_per_row", 24)) * 1.08)),
            )

        assert best is not None
        overdesign = float(best.get("overdesign_pct") or 0.0)
        gas_dp = float(best.get("gas_dP_bar") or 0.0)
        fan_tip = float(best.get("fan_tip_speed_m_s") or 0.0)
        if overdesign < min_overdesign:
            warnings.append(f"Yüzey alanı yetersiz: overdesign %{overdesign:.1f} (< %{min_overdesign:.1f}).")
        if gas_dp > max_dp:
            warnings.append(f"Gaz tarafı ΔP yüksek: {gas_dp:.3f} bar (> {max_dp:.3f} bar).")
        if fan_tip > 61.0:
            warnings.append(f"Fan uç hızı API 661 sınırı üzerinde: {fan_tip:.1f} m/s (> 61 m/s).")

        normalized = {
            "heat_duty_kw": best.get("Q_kW"),
            "u_value_w_m2k": best.get("U_W_m2K"),
            "lmtd_k": best.get("lmtd_K"),
            "ft_correction": best.get("Ft"),
            "required_area_m2": best.get("required_area_m2"),
            "actual_area_m2": best.get("actual_area_m2"),
            "overdesign_pct": best.get("overdesign_pct"),
            "gas_pressure_drop_bar": best.get("gas_dP_bar"),
            "gas_velocity_ms": best.get("gas_velocity_m_s"),
            "gas_reynolds": best.get("gas_Re"),
            "air_mass_flow_kgs": best.get("m_dot_air_kg_s"),
            "air_volume_m3h": best.get("V_air_m3_h"),
            "fan_power_kw": best.get("fan_power_kW"),
            "fan_tip_speed_ms": best.get("fan_tip_speed_m_s"),
            "fan_sound_power_db": best.get("fan_sound_power_dB"),
            "condensation_applied": best.get("condensation_applied"),
            "segmental_applied": best.get("segmental_applied"),
            "geometry": best.get("_geometry"),
            "auto_size_iterations": attempts,
            "detail": {k: v for k, v in best.items() if k != "_geometry"},
        }
        return module_response(
            self,
            normalized,
            warnings=warnings,
            provenance={
                "standard": "API 661 / ASME VIII-1 / TEMA screening",
                "source": "Air-Cooler-Main core",
                "gas_properties": "CoolProp HEOS / SRK / PR",
            },
        )
