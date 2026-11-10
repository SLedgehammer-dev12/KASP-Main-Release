"""
KASP Pipe Sizing & Natural Gas Flow Network Service (kasp/services/pipe_sizing_service.py)
Embedded from Natural Gas Flow Calc project with ASME B36.10M / API 5L engineering:
- Dynamic line-by-line pipe sizing for the entire compressor station
- Hydraulic pressure drop, velocity checks, and API RP 14E erosion analysis
- Standalone custom pipe sizing API
"""

from typing import Dict, Any, List, Optional
from kasp.core.pipe_sizing import (
    size_single_pipe,
    PIPE_MATERIALS,
    PIPE_ROUGHNESS,
    calculate_erosion_velocity,
    calculate_pipe_weight_api5l,
    nd_sort_key,
)


class PipeSizingService:
    """
    Comprehensive pipe network sizing and flow velocity engine for KASP.
    """

    @staticmethod
    def size_station_network(
        mass_flow_kgs: float,
        p_in_bar: float,
        p_out_bar: float,
        t_in_c: float,
        t_discharge_c: float,
        t_cooled_c: float,
        comp_op_count: int,
        cyclone_op_count: int,
        filter_op_count: int,
        cooler_bays_count: int,
        gas_mw: float = 18.2,
        pipe_material: str = "API 5L X70",
        design_factor_F: float = 0.50,
        pipe_standard: str = "BOTAŞ",
        psl_level: str = "PSL2",
    ) -> Dict[str, Any]:
        """
        Calculates exact ASME B36.10M commercial pipe sizes, schedules, wall thicknesses,
        actual flow velocities, and API RP 14E erosion limits for all 15 key process lines in the station.
        """
        try:
            mass_flow_kgs = max(0.5, float(mass_flow_kgs))
        except (TypeError, ValueError):
            mass_flow_kgs = 50.0
        try:
            p_in_bar = max(1.0, float(p_in_bar))
        except (TypeError, ValueError):
            p_in_bar = 25.0
        try:
            p_out_bar = max(p_in_bar * 1.05, float(p_out_bar))
        except (TypeError, ValueError):
            p_out_bar = p_in_bar * 2.5
        try:
            t_in_c = float(t_in_c) if t_in_c is not None else 20.0
        except (TypeError, ValueError):
            t_in_c = 20.0
        try:
            t_discharge_c = float(t_discharge_c) if t_discharge_c is not None else 95.0
        except (TypeError, ValueError):
            t_discharge_c = 95.0
        try:
            t_cooled_c = float(t_cooled_c) if t_cooled_c is not None else 45.0
        except (TypeError, ValueError):
            t_cooled_c = 45.0
        comp_op_count = max(1, int(comp_op_count or 1))
        cyclone_op_count = max(1, int(cyclone_op_count or 1))
        filter_op_count = max(1, int(filter_op_count or 1))
        cooler_bays_count = max(1, int(cooler_bays_count or 1))

        # Flow divisions
        flow_per_comp = mass_flow_kgs / comp_op_count
        flow_per_cyclone = mass_flow_kgs / cyclone_op_count
        flow_per_filter = mass_flow_kgs / filter_op_count
        flow_per_bay = mass_flow_kgs / cooler_bays_count
        surge_flow = flow_per_comp * 0.68  # API 617 surge limit flow
        bypass_flow = mass_flow_kgs * 0.35  # TCV bypass line

        # Sizing 15 key process lines
        lines: Dict[str, Dict[str, Any]] = {}

        # 1. Mainline Transmission Inlet (Before station ESD)
        lines["mainline_inlet"] = {
            "tag": "L-101",
            "name": "Ana İletim Boru Hattı Girişi (Mainline Inlet)",
            "service": "Ham Doğal Gaz Giriş",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_in_bar,
            "temp_c": t_in_c,
            "max_vel_target": 16.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_in_bar,
                t_c=t_in_c,
                mw=gas_mw,
                max_velocity_ms=16.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 2. 48" Suction Collector Header
        lines["suction_header"] = {
            "tag": "L-102",
            "name": "Emiş Kollektörü (Suction Header)",
            "service": "Ana Emiş Dağıtımı",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_in_bar,
            "temp_c": t_in_c,
            "max_vel_target": 15.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_in_bar,
                t_c=t_in_c,
                mw=gas_mw,
                max_velocity_ms=15.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 3. Cyclone Separator Inlet Branches (MFS)
        lines["cyclone_branch"] = {
            "tag": "L-103",
            "name": "Siklon Seperatör Branşmanı (MFS Inlet)",
            "service": "Sıvı/Katı Ayrıştırma Beslemesi",
            "flow_kgs": round(flow_per_cyclone, 2),
            "pressure_bar": p_in_bar,
            "temp_c": t_in_c,
            "max_vel_target": 12.0,
            **size_single_pipe(
                flow_kgs=flow_per_cyclone,
                p_bar=p_in_bar,
                t_c=t_in_c,
                mw=gas_mw,
                max_velocity_ms=12.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 4. Cartridge Filter Branches (CFS)
        p_cfs = round(p_in_bar - 0.25, 2)
        lines["filter_branch"] = {
            "tag": "L-104",
            "name": "Kartuş Filtre Branşmanı (CFS Inlet)",
            "service": "Hassas Filtrasyon (0.3 µm)",
            "flow_kgs": round(flow_per_filter, 2),
            "pressure_bar": p_cfs,
            "temp_c": t_in_c,
            "max_vel_target": 12.0,
            **size_single_pipe(
                flow_kgs=flow_per_filter,
                p_bar=p_cfs,
                t_c=t_in_c,
                mw=gas_mw,
                max_velocity_ms=12.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 5. Filtered Compressor Suction Header (Front Manifold)
        p_comp_in = round(p_cfs - 0.20, 2)
        lines["comp_suction_header"] = {
            "tag": "L-105",
            "name": "Filtrelenmiş Gaz Emiş Kollektörü",
            "service": "Kompresör Besleme Başlığı",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_comp_in,
            "temp_c": t_in_c,
            "max_vel_target": 15.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_comp_in,
                t_c=t_in_c,
                mw=gas_mw,
                max_velocity_ms=15.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 6. Individual Turbo-Compressor Suction Feed (Note 32: 30" -> 16" nozzle)
        lines["comp_suction_branch"] = {
            "tag": "L-106",
            "name": "Kompresör Emiş Branşmanı (Ünite Emiş Girişi)",
            "service": "Ünite Emiş Girişi",
            "flow_kgs": round(flow_per_comp, 2),
            "pressure_bar": p_comp_in,
            "temp_c": t_in_c,
            "max_vel_target": 16.0,
            **size_single_pipe(
                flow_kgs=flow_per_comp,
                p_bar=p_comp_in,
                t_c=t_in_c,
                mw=gas_mw,
                max_velocity_ms=16.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 7. Individual Turbo-Compressor Discharge Branch (Note 32: 16" -> 30")
        lines["comp_discharge_branch"] = {
            "tag": "L-107",
            "name": "Kompresör Basma Branşmanı (Ünite Basma Çıkışı)",
            "service": "Sıcak Yüksek Basınç Çıkışı",
            "flow_kgs": round(flow_per_comp, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 18.0,
            **size_single_pipe(
                flow_kgs=flow_per_comp,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=18.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 8. Dedicated Hot Gas Anti-Surge Recycle Loop (ASV)
        lines["anti_surge_loop"] = {
            "tag": "L-108",
            "name": "Anti-Surge Sıcak Gaz Geri Dönüş Hattı (ASV)",
            "service": "Dinamik Kompresör Koruma",
            "flow_kgs": round(surge_flow, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 22.0,
            **size_single_pipe(
                flow_kgs=surge_flow,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=22.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 9. 48" Discharge Collector Header (Front Manifold)
        lines["discharge_header"] = {
            "tag": "L-109",
            "name": "Basma Kollektörü (Discharge Header)",
            "service": "Sıcak Gaz Toplama Başlığı",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 18.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=18.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 10. Station-Wide Recycle Line (Note 13)
        lines["station_recycle"] = {
            "tag": "L-110",
            "name": "İstasyon Geri Dönüş Hattı (Station Recycle)",
            "service": "Tam İstasyon Basınçlandırma/Sirkülasyon",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 20.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=20.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 11. Gas Cooler Inlet Header (Hot gas to air coolers)
        lines["cooler_inlet"] = {
            "tag": "L-111",
            "name": "Gaz Soğutucu Sıcak Gaz Giriş Kollektörü",
            "service": "Fin-Fan Soğutucu Besleme",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 18.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=18.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 12. Gas Cooler Vertical Risers (South face to cooler top)
        lines["cooler_bay_risers"] = {
            "tag": "L-112",
            "name": "Gaz Soğutucu Dikey Yükseltici Borular (Risers)",
            "service": "Bay Dağıtım Yükselticisi",
            "flow_kgs": round(flow_per_bay, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 14.0,
            **size_single_pipe(
                flow_kgs=flow_per_bay,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=14.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 13. Gas Cooler By-Pass Line (TCV Note 17)
        lines["cooler_bypass"] = {
            "tag": "L-113",
            "name": "Gaz Soğutucu Baypas Hattı (TCV Note 17)",
            "service": "İkincil Sıcaklık Kontrolü",
            "flow_kgs": round(bypass_flow, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": 18.0,
            **size_single_pipe(
                flow_kgs=bypass_flow,
                p_bar=p_out_bar,
                t_c=t_discharge_c,
                mw=gas_mw,
                max_velocity_ms=18.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 14. Cooled Gas Main Header
        p_cooled = round(p_out_bar - 0.40, 2)
        lines["cooler_outlet"] = {
            "tag": "L-114",
            "name": "Soğutulmuş Gaz Çıkış Kollektörü",
            "service": "Boru Hattı Sıcaklığına Soğutulmuş Gaz",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": 16.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_cooled,
                t_c=t_cooled_c,
                mw=gas_mw,
                max_velocity_ms=16.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # 15. Mainline Transmission Outlet (Passing through Pig Launcher)
        lines["mainline_outlet"] = {
            "tag": "L-115",
            "name": "Ana İletim Boru Hattı Çıkışı (Mainline Outlet)",
            "service": "İletim Şebekesine Sevk",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": 16.0,
            **size_single_pipe(
                flow_kgs=mass_flow_kgs,
                p_bar=p_cooled,
                t_c=t_cooled_c,
                mw=gas_mw,
                max_velocity_ms=16.0,
                material=pipe_material,
                design_factor_F=design_factor_F,
            ),
        }

        # Station suction and discharge collector headers must have the same
        # commercial nominal pipe size (operator/station requirement). The two
        # headers carry the same total mass flow, so we adopt the larger of the
        # two hydraulically selected sizes and re-size the other line at that
        # nominal size. This recomputes velocity, erosion ratio and pressure
        # drop at the equalized diameter instead of only copying the label.
        header_keys = ("suction_header", "discharge_header")
        header_nominals = [
            (key, lines[key].get("nominal_key"))
            for key in header_keys
            if lines.get(key, {}).get("nominal_key")
        ]
        if len(header_nominals) == 2:
            larger_key, larger_nominal = max(
                header_nominals, key=lambda item: nd_sort_key(item[1])
            )
            for key in header_keys:
                current = lines[key]
                if current.get("nominal_key") == larger_nominal:
                    current["diameter_equalized_to"] = f'{larger_nominal}"'
                    current["header_pair"] = "suction_discharge_common_nps"
                    continue
                meta = {
                    field: current[field]
                    for field in (
                        "tag",
                        "name",
                        "service",
                        "flow_kgs",
                        "pressure_bar",
                        "temp_c",
                        "max_vel_target",
                    )
                    if field in current
                }
                resized = {
                    **meta,
                    **size_single_pipe(
                        flow_kgs=float(current["flow_kgs"]),
                        p_bar=float(current["pressure_bar"]),
                        t_c=float(current["temp_c"]),
                        mw=gas_mw,
                        max_velocity_ms=float(current["max_vel_target"]),
                        material=pipe_material,
                        design_factor_F=design_factor_F,
                        preferred_nominal=larger_nominal,
                    ),
                }
                # Guard against a fallback to a smaller pipe: the equality
                # requirement takes precedence over the preferred-size
                # velocity guard (using a larger pipe always lowers velocity).
                if resized.get("nominal_key") != larger_nominal:
                    resized = {
                        **meta,
                        **size_single_pipe(
                            flow_kgs=float(current["flow_kgs"]),
                            p_bar=float(current["pressure_bar"]),
                            t_c=float(current["temp_c"]),
                            mw=gas_mw,
                            max_velocity_ms=max(float(current["max_vel_target"]), 30.0),
                            material=pipe_material,
                            design_factor_F=design_factor_F,
                            preferred_nominal=larger_nominal,
                        ),
                    }
                resized["diameter_equalized_to"] = f'{larger_nominal}"'
                resized["header_pair"] = "suction_discharge_common_nps"
                resized["equalized_from_nominal_size_in"] = current.get("nominal_size_in")
                lines[key] = resized
            lines[larger_key]["diameter_equalized_to"] = f'{larger_nominal}"'

        # Standard-specific wall thickness recommendation (BOTAŞ / API 5L PSL2)
        standard_map = {
            "botas": "BOTAŞ",
            "botaş": "BOTAŞ",
            "api5l": "ASME B31.8 / ASME B31.4",
            "api 5l": "ASME B31.8 / ASME B31.4",
            "b31.8": "ASME B31.8 / ASME B31.4",
            "b31.3": "ASME B31.3",
        }
        standard_code = standard_map.get(str(pipe_standard).strip().lower(), str(pipe_standard or "BOTAŞ"))
        for line in lines.values():
            nominal_key = line.get("nominal_key")
            if not nominal_key:
                continue
            try:
                from kasp.integrations.api5l.vendor.wall_thickness_engine import WallThicknessEngine

                grade = str(pipe_material).replace("API 5L ", "").strip()
                if grade.lower() in {"gr. b", "gr b", "grade b"}:
                    grade = "GRADE B"
                rec = WallThicknessEngine.calculate_wall_thickness(
                    diameter_inch=str(nominal_key),
                    material_grade=grade,
                    design_pressure_bar=float(line.get("design_pressure_bar") or p_out_bar),
                    design_factor_f=float(design_factor_F),
                    location_type="Station",
                    standard_code=standard_code,
                    psl_level=str(psl_level or "PSL2"),
                )
                cr = rec.get("calculation_results", {})
                line["standard_recommendation"] = {
                    "standard": standard_code,
                    "psl_level": str(psl_level or "PSL2"),
                    "required_thickness_mm": cr.get("t_required_asme_b31_8_mm"),
                    "selected_nominal_thickness_mm": cr.get("selected_nominal_thickness_asme_b36_10_mm"),
                    "botas_standard_thickness_mm": cr.get("botas_standard_thickness_mm"),
                    "botas_standard_label": cr.get("botas_standard_label"),
                    "minimum_standard_thickness_mm": cr.get("t_min_standard_mm"),
                    "tolerance_rule": cr.get("standard_tolerance_rule"),
                    "tolerance_percent": cr.get("tolerance_percent_used"),
                    "is_sufficient": cr.get("is_nominal_sufficient"),
                }
            except Exception as exc:
                line["standard_recommendation"] = {"error": str(exc)}

        # Overall network statistics
        total_steel_weight_ton_per_km = sum(l["pipe_weight_kg_m"] for l in lines.values()) / 1000.0
        avg_velocity = sum(l["actual_velocity_ms"] for l in lines.values()) / len(lines)

        return {
            "success": True,
            "design_standard": "ASME B31.8 / API 5L / API RP 14E",
            "pipe_material": pipe_material,
            "design_factor_F": design_factor_F,
            "pipe_standard": standard_code,
            "psl_level": str(psl_level or "PSL2"),
            "total_lines_sized": len(lines),
            "average_network_velocity_ms": round(avg_velocity, 2),
            "estimated_steel_weight_ton_per_km": round(total_steel_weight_ton_per_km, 2),
            "lines": lines,
        }
