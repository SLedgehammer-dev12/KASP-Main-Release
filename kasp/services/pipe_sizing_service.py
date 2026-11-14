"""
KASP Pipe Sizing & Natural Gas Flow Network Service (kasp/services/pipe_sizing_service.py)
Embedded from Natural Gas Flow Calc project with ASME B36.10M / API 5L engineering:
- Dynamic line-by-line pipe sizing for the entire compressor station
- Hydraulic pressure drop, velocity checks, and API RP 14E erosion analysis
- Standalone custom pipe sizing API
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.pipe_sizing import (
    size_single_pipe,
    PIPE_MATERIALS,
    PIPE_ROUGHNESS,
    calculate_erosion_velocity,
    calculate_pipe_weight_api5l,
    nd_sort_key,
)
from kasp.core.properties import ThermodynamicSolver


_PIPE_EOS_ALIASES = {
    "coolprop": "coolprop",
    "heos": "coolprop",
    "pr": "pr",
    "peng-robinson": "pr",
    "bwrs": "gerg2008",
    "srk": "srk",
    "rk": "srk",
    "gerg2008": "gerg2008",
    "gerg-2008": "gerg2008",
    "aga8": "aga8",
    "thermopack": "thermopack",
    "ccp": "ccp",
    "dwsim": "dwsim",
    "neqsim": "neqsim",
}


def _normalize_pipe_eos(raw_eos: Any) -> str:
    if not raw_eos:
        return "pr"
    cleaned = str(raw_eos).strip().lower()
    return _PIPE_EOS_ALIASES.get(cleaned, "pr")


def _prepare_pipe_gas_obj(gas_comp: Optional[Dict[str, Any]], eos_key: str):
    if not gas_comp or not isinstance(gas_comp, dict):
        return None
    try:
        comp_frac = GasMixtureBuilder.validate_and_normalize(gas_comp)
        if eos_key == "coolprop":
            return GasMixtureBuilder.build_coolprop_string(comp_frac)
        if eos_key == "neqsim":
            return GasMixtureBuilder.build_neqsim_input(comp_frac)
        return GasMixtureBuilder.build_thermo_data(comp_frac)
    except Exception:
        return None


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
        dp_cyclone_bar: Optional[float] = None,
        dp_filter_bar: Optional[float] = None,
        dp_cooler_bar: Optional[float] = None,
        gas_comp: Optional[Dict[str, Any]] = None,
        eos_model: str = "pr",
        thermo_solver: Optional[ThermodynamicSolver] = None,
        max_velocity_ms: float = 20.0,
        cyclone_inlet_nominal: Optional[str] = None,
        cyclone_outlet_nominal: Optional[str] = None,
        filter_inlet_nominal: Optional[str] = None,
        filter_outlet_nominal: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculates exact ASME B36.10M commercial pipe sizes, schedules, wall thicknesses,
        actual flow velocities, and API RP 14E erosion limits for all station process lines.
        """
        try:
            v_limit_ms = max(0.5, float(max_velocity_ms if max_velocity_ms is not None else 20.0))
        except (TypeError, ValueError):
            v_limit_ms = 20.0
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

        def _valid_dp(val: Optional[float], default_dp: float) -> float:
            if val is None:
                return default_dp
            try:
                f_val = float(val)
                return f_val if math.isfinite(f_val) and f_val >= 0.0 else default_dp
            except (TypeError, ValueError):
                return default_dp

        dp_cyc = _valid_dp(dp_cyclone_bar, 0.25)
        dp_flt = _valid_dp(dp_filter_bar, 0.20)
        dp_clr = _valid_dp(dp_cooler_bar, 0.40)

        eos_key = _normalize_pipe_eos(eos_model)
        gas_obj = _prepare_pipe_gas_obj(gas_comp, eos_key)
        solver = thermo_solver or (ThermodynamicSolver() if gas_obj is not None else None)
        state_cache: Dict[Tuple[float, float], Tuple[Optional[float], Optional[float], Optional[float]]] = {}

        def _eos_props_at(p_bar_val: float, t_c_val: float) -> Dict[str, Optional[float]]:
            if gas_obj is None or solver is None:
                return {"density_kgm3": None, "viscosity_pa_s": None, "z_factor": None}
            key = (round(float(p_bar_val), 3), round(float(t_c_val), 2))
            if key not in state_cache:
                try:
                    t_k = max(100.0, min(800.0, float(t_c_val) + 273.15))
                    p_pa = max(1.0e5, float(p_bar_val) * 1e5)
                    st = solver.get_properties(p_pa, t_k, gas_obj, eos_key)
                    rho_val = float(st.density) if st.density and math.isfinite(st.density) and st.density > 0 else None
                    z_val = float(st.Z) if st.Z and math.isfinite(st.Z) and st.Z > 0 else None
                    raw_mu = st.raw_props.get("mu") if hasattr(st, "raw_props") and isinstance(st.raw_props, dict) else None
                    mu_val = float(raw_mu) if raw_mu is not None and math.isfinite(float(raw_mu)) and float(raw_mu) > 0 else None
                    state_cache[key] = (rho_val, mu_val, z_val)
                except Exception:
                    state_cache[key] = (None, None, None)
            rho_c, mu_c, z_c = state_cache[key]
            return {"density_kgm3": rho_c, "viscosity_pa_s": mu_c, "z_factor": z_c}

        def _norm_nominal(val: Optional[str]) -> Optional[str]:
            if val is None:
                return None
            cleaned = str(val).replace('"', "").strip()
            if not cleaned or cleaned.lower() in {"auto", "otomatik", "none", "null"}:
                return None
            return cleaned

        cyc_in_nom = _norm_nominal(cyclone_inlet_nominal)
        cyc_out_nom = _norm_nominal(cyclone_outlet_nominal)
        flt_in_nom = _norm_nominal(filter_inlet_nominal)
        flt_out_nom = _norm_nominal(filter_outlet_nominal)

        def _size_line(
            flow_kgs: float,
            p_bar: float,
            t_c: float,
            max_velocity_ms: float,
            preferred_nominal: Optional[str] = None,
            enforce_preferred_nominal: bool = False,
        ) -> Dict[str, Any]:
            props = _eos_props_at(p_bar, t_c)
            return size_single_pipe(
                flow_kgs=flow_kgs,
                p_bar=p_bar,
                t_c=t_c,
                mw=gas_mw,
                max_velocity_ms=max_velocity_ms,
                material=pipe_material,
                design_factor_F=design_factor_F,
                preferred_nominal=preferred_nominal,
                enforce_preferred_nominal=enforce_preferred_nominal,
                density_kgm3=props["density_kgm3"],
                viscosity_pa_s=props["viscosity_pa_s"],
                z_factor=props["z_factor"],
            )

        # Flow divisions
        flow_per_comp = mass_flow_kgs / comp_op_count
        flow_per_cyclone = mass_flow_kgs / cyclone_op_count
        flow_per_filter = mass_flow_kgs / filter_op_count
        flow_per_bay = mass_flow_kgs / cooler_bays_count
        surge_flow = flow_per_comp * 0.68  # API 617 surge limit flow
        bypass_flow = mass_flow_kgs * 0.35  # TCV bypass line

        # Sizing 16 key process lines with explicit hierarchy & battery-limit boundaries
        lines: Dict[str, Dict[str, Any]] = {}
        p_cooled = max(1.0, round(p_out_bar - dp_clr, 2))

        # 1. Mainline Transmission Inlet (Before station inlet pig trap)
        lines["mainline_inlet"] = {
            "tag": "L-101",
            "name": "Ana İletim Boru Hattı Girişi (Mainline Inlet)",
            "service": "Ham Doğal Gaz Giriş",
            "hierarchy_level": "mainline_tie_in",
            "hierarchy_label": "Ana İletim Sınır Hattı",
            "parent_header": None,
            "from_boundary": "Ana İletim Boru Hattı Giriş Tie-In Noktası",
            "to_boundary": "Giriş Pig Alıcı Kovanı (PIG-R) Giriş ESDV Flanşı",
            "boundary_summary": "Ana İletim Girişi ➔ PIG-R Giriş Flanşı",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_in_bar,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            "note": "PIG-R aksında 22.5° çift hot bend (S-offset) ile 90° dirsek olmadan toprak altı kottan istasyon girişine bağlanır.",
            **_size_line(mass_flow_kgs, p_in_bar, t_in_c, v_limit_ms),
        }

        # 2. Station Suction Header (PIG-R Outlet -> Filtration Yard Main Suction Header)
        lines["suction_header"] = {
            "tag": "L-102",
            "name": "Station Suction Header (PIG-R ➔ Filtreleme Sahası)",
            "service": "Ana İstasyon Emiş Omurgası (Ham Gaz & Filtreleme Dağıtımı)",
            "hierarchy_level": "main_header",
            "hierarchy_label": "Station Suction Header",
            "parent_header": "station_suction_header",
            "from_boundary": "Giriş Pig Alıcı Kovanı (PIG-R) Çıkış İzolasyon Vanası (MOV/ESDV)",
            "to_boundary": "MFS & CFS Filtreleme Sahası Ana Emiş Bağlantı Kollektörü",
            "boundary_summary": "PIG-R Çıkışı ➔ MFS/CFS Ana Emiş Kollektörü",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_in_bar,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_in_bar, t_in_c, v_limit_ms),
        }

        # 3a. Cyclone Separator Inlet Branches (MFS inlet manifold & unit nozzles at p_in)
        lines["cyclone_branch"] = {
            "tag": "L-103",
            "name": "Siklon Seperatör Giriş Borulaması (MFS Giriş Branşmanı)",
            "service": "Sıvı/Katı Ayrıştırma Giriş Bağlantısı",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Giriş Borulaması (MFS)",
            "parent_header": "station_suction_header",
            "from_boundary": "Station Suction Header MFS Giriş Branşman Bağlantısı",
            "to_boundary": "MFS Siklon Seperatörleri (V-101..N) Giriş Nozulları",
            "boundary_summary": "Station Suction Header ➔ MFS V-101..N Giriş",
            "flow_kgs": round(flow_per_cyclone, 2),
            "pressure_bar": p_in_bar,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            "diameter_source": "user_input" if cyc_in_nom else "station_3d_calc",
            **_size_line(
                flow_per_cyclone,
                p_in_bar,
                t_in_c,
                v_limit_ms,
                preferred_nominal=cyc_in_nom,
                enforce_preferred_nominal=bool(cyc_in_nom),
            ),
        }

        # 3b. Cyclone Separator Outlet Branches (MFS top outlets -> MFS collector / CFS inlet tie at p_cfs)
        p_cfs = max(1.0, round(p_in_bar - dp_cyc, 2))
        lines["cyclone_outlet_branch"] = {
            "tag": "L-103A",
            "name": "Siklon Seperatör Çıkış Borulaması (MFS Çıkış / CFS Ara Bağlantı)",
            "service": "Sıvı/Katı Ayrıştırma Çıkış & CFS Ara Bağlantısı",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Çıkış Borulaması (MFS)",
            "parent_header": "station_suction_header",
            "from_boundary": "MFS Siklon Seperatörleri (V-101..N) Üst Çıkış Nozulları",
            "to_boundary": "MFS Ortak Çıkış Kollektörü / CFS Giriş Manifoldu",
            "boundary_summary": "MFS V-101..N Çıkış ➔ CFS Giriş Manifoldu",
            "flow_kgs": round(flow_per_cyclone, 2),
            "pressure_bar": p_cfs,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            "diameter_source": "user_input" if cyc_out_nom else "station_3d_calc",
            **_size_line(
                flow_per_cyclone,
                p_cfs,
                t_in_c,
                v_limit_ms,
                preferred_nominal=cyc_out_nom,
                enforce_preferred_nominal=bool(cyc_out_nom),
            ),
        }

        # 4a. Cartridge Filter Inlet Branches (CFS inlet distributor & U-bends at p_cfs)
        lines["filter_branch"] = {
            "tag": "L-104",
            "name": "Kartuş Filtre Giriş Borulaması (CFS Giriş Branşmanı)",
            "service": "Hassas Filtrasyon (0.3 µm) Giriş Bağlantısı",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Giriş Borulaması (CFS)",
            "parent_header": "station_suction_header",
            "from_boundary": "MFS Çıkış Kollektörü / CFS Giriş Dağıtım Manifoldu",
            "to_boundary": "CFS Kartuş Filtreleri (F-101..N) Giriş Nozulları",
            "boundary_summary": "MFS Çıkış Kollektörü ➔ CFS F-101..N Giriş",
            "flow_kgs": round(flow_per_filter, 2),
            "pressure_bar": p_cfs,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            "diameter_source": "user_input" if flt_in_nom else "station_3d_calc",
            **_size_line(
                flow_per_filter,
                p_cfs,
                t_in_c,
                v_limit_ms,
                preferred_nominal=flt_in_nom,
                enforce_preferred_nominal=bool(flt_in_nom),
            ),
        }

        # 4b. Cartridge Filter Outlet Branches (CFS outlet nozzles & collector -> Station Suction Header at p_comp_in)
        p_comp_in = max(1.0, round(p_cfs - dp_flt, 2))
        lines["filter_outlet_branch"] = {
            "tag": "L-104A",
            "name": "Kartuş Filtre Çıkış Borulaması (CFS Çıkış Branşmanı)",
            "service": "Hassas Filtrasyon Çıkış & Ana Emiş Header Dönüşü",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Çıkış Borulaması (CFS)",
            "parent_header": "station_suction_header",
            "from_boundary": "CFS Kartuş Filtreleri (F-101..N) Çıkış Nozulları",
            "to_boundary": "Station Suction Header (Filtrelenmiş Ana Omurga Tie-In)",
            "boundary_summary": "CFS F-101..N Çıkış ➔ Station Suction Header",
            "flow_kgs": round(flow_per_filter, 2),
            "pressure_bar": p_comp_in,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            "diameter_source": "user_input" if flt_out_nom else "station_3d_calc",
            **_size_line(
                flow_per_filter,
                p_comp_in,
                t_in_c,
                v_limit_ms,
                preferred_nominal=flt_out_nom,
                enforce_preferred_nominal=bool(flt_out_nom),
            ),
        }

        # 5. Unit Suction Header (Filtered Gas -> TC Units Suction Connection Header End)
        lines["comp_suction_header"] = {
            "tag": "L-105",
            "name": "Unit Suction Header (TC Üniteleri Emiş Bağlantı Header'ı)",
            "service": "Ünite Emiş Ana Kollektörü (Filtrelenmiş Gaz Besleme Başlığı)",
            "hierarchy_level": "main_header",
            "hierarchy_label": "Unit Suction Header",
            "parent_header": "station_suction_header",
            "from_boundary": "CFS Kartuş Filtre Dönüş Birleşimi (Ana Emiş Omurgası)",
            "to_boundary": "Turbo-Kompresör (TC) Üniteleri Emiş Bağlantı Header'ı Sonu (Kör Flanş)",
            "boundary_summary": "CFS Dönüşü ➔ TC Emiş Bağlantı Header'ı Sonu",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_comp_in,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_comp_in, t_in_c, v_limit_ms),
        }

        # 6. Individual Turbo-Compressor Suction Feed (Note 32: Branch -> 16" nozzle)
        lines["comp_suction_branch"] = {
            "tag": "L-106",
            "name": "TC Ünite Emiş Branşmanı (Kompresör Emiş Girişi)",
            "service": "Ünite Emiş Bağlantı Borulaması",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Bağlantı Borulaması (TC Emiş)",
            "parent_header": "station_suction_header",
            "from_boundary": "Unit Suction Header TC Ünite Emiş Tee Bağlantısı",
            "to_boundary": "Ünite Emiş MOV Vanası + Redüksiyon + TC Kompresör Emiş Nozulu (C-101..N)",
            "boundary_summary": "Unit Suction Header Tee ➔ TC Emiş Nozulu (C-101..N)",
            "flow_kgs": round(flow_per_comp, 2),
            "pressure_bar": p_comp_in,
            "temp_c": t_in_c,
            "max_vel_target": v_limit_ms,
            **_size_line(flow_per_comp, p_comp_in, t_in_c, v_limit_ms),
        }

        # 7. Individual Turbo-Compressor Discharge Branch (Note 32: 16" nozzle -> Branch)
        lines["comp_discharge_branch"] = {
            "tag": "L-107",
            "name": "TC Ünite Basma Branşmanı (Kompresör Basma Çıkışı)",
            "service": "Ünite Basma Bağlantı Borulaması",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Bağlantı Borulaması (TC Basma)",
            "parent_header": "station_discharge_header",
            "from_boundary": "TC Kompresör Basma Nozulu (C-101..N) + Ekspansiyon + Çekvalf/MOV",
            "to_boundary": "Unit Discharge Header TC Ünite Basma Tee Bağlantısı",
            "boundary_summary": "TC Basma Nozulu (C-101..N) ➔ Unit Discharge Header Tee",
            "flow_kgs": round(flow_per_comp, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(flow_per_comp, p_out_bar, t_discharge_c, v_limit_ms),
        }

        # 8. Dedicated Hot Gas Anti-Surge Recycle Loop (ASV)
        lines["anti_surge_loop"] = {
            "tag": "L-108",
            "name": "Ünite Anti-Surge Sıcak Gaz Geri Dönüş Hattı (ASV)",
            "service": "Dinamik Kompresör Koruma Borulaması",
            "hierarchy_level": "recycle_control",
            "hierarchy_label": "Ünite Koruma Hattı (ASV)",
            "parent_header": "station_suction_and_discharge_headers",
            "from_boundary": "TC Ünite Basma Branşmanı (Çekvalf Öncesi Sıcak Gaz Ayrımı)",
            "to_boundary": "Hızlı Açılır ASV Vanası ➔ Anti-Surge / İstasyon Recycle Header'ı",
            "boundary_summary": "TC Basma Branşmanı ➔ ASV ➔ Recycle Header",
            "flow_kgs": round(surge_flow, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(surge_flow, p_out_bar, t_discharge_c, v_limit_ms),
        }

        # 9A. Unit Discharge Header (TC Units Hot Gas Discharge Collector -> Gas Cooler Inlet Tie-In)
        lines["unit_discharge_header"] = {
            "tag": "L-109A",
            "name": "Unit Discharge Header (TC Üniteleri Sıcak Basma Header'ı)",
            "service": "Ünite Basma Ana Kollektörü (Sıcak Gaz Toplama ➔ Gaz Soğutucu Beslemesi)",
            "hierarchy_level": "main_header",
            "hierarchy_label": "Unit Discharge Header",
            "parent_header": "station_discharge_header",
            "from_boundary": "Turbo-Kompresör (TC) Ünite Basma Branşmanlarının Bağlandığı Sıcak Header Başlangıcı",
            "to_boundary": "Gaz Hava Soğutucu (E-101) Sıcak Giriş Manifoldu Tie-In Bağlantısı",
            "boundary_summary": "TC Basma Branşmanları ➔ Gaz Soğutucu Sıcak Giriş Tie-In",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_out_bar, t_discharge_c, v_limit_ms),
        }

        # 9B. Station Discharge Header (Cooled Gas Return -> PSV/ESD/USM -> Outlet Pig Launcher PIG-L)
        lines["discharge_header"] = {
            "tag": "L-109",
            "name": "Station Discharge Header (Soğutucu Dönüşü ➔ Çıkış Pig Kovanı PIG-L)",
            "service": "Ana İstasyon Basma Omurgası (Soğutulmuş Gaz Sevk & Emniyet Manifoldu)",
            "hierarchy_level": "main_header",
            "hierarchy_label": "Station Discharge Header",
            "parent_header": "station_discharge_header",
            "from_boundary": "TC Basma Header'ı / Gaz Soğutucu (E-101) Soğuk Dönüş Tie-In Noktası",
            "to_boundary": "Çıkış Pig Atıcı Kovanı (PIG-L) Giriş İzolasyon Vanası (MOV/ESDV)",
            "boundary_summary": "Gaz Soğutucu Soğuk Dönüşü ➔ PSV/ESD/USM ➔ PIG-L Giriş Flanşı",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_cooled, t_cooled_c, v_limit_ms),
        }

        # 10. Station-Wide Recycle / Anti-Surge Collector Header (Note 13)
        lines["station_recycle"] = {
            "tag": "L-110",
            "name": "İstasyon Recycle & Anti-Surge Toplama Kollektörü (Note 13)",
            "service": "Tam İstasyon Basınçlandırma & ASV Dönüş Kollektörü",
            "hierarchy_level": "recycle_control",
            "hierarchy_label": "İstasyon Recycle / ASV Kollektörü",
            "parent_header": "station_suction_and_discharge_headers",
            "from_boundary": "Station Discharge Header (PCV Note 13) & Ünite ASV Dönüş Bağlantıları",
            "to_boundary": "Station Suction Header Ana Geri Dönüş Bağlantısı",
            "boundary_summary": "Discharge / ASV Toplama ➔ Station Suction Header",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_out_bar, t_discharge_c, v_limit_ms),
        }

        # 11. Gas Cooler Hot Inlet Distribution Manifold (Equipment manifold off Unit Discharge Header)
        lines["cooler_inlet"] = {
            "tag": "L-111",
            "name": "Gaz Soğutucu Sıcak Giriş Dağıtım Manifoldu (E-101 Giriş)",
            "service": "Fin-Fan Hava Soğutucu Ekipman Giriş Borulaması",
            "hierarchy_level": "equipment_header",
            "hierarchy_label": "Ekipman Bağlantı Borulaması (Soğutucu Giriş)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Unit Discharge Header Sıcak Gaz Soğutucu Bağlantı Noktası",
            "to_boundary": "Gaz Hava Soğutucu (E-101) Bay Giriş Dağıtım Manifoldu",
            "boundary_summary": "Unit Discharge Header ➔ E-101 Sıcak Giriş Manifoldu",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_out_bar, t_discharge_c, v_limit_ms),
        }

        # 12. Gas Cooler Hot Inlet Risers & Dedicated Per-Bay Inlet/Outlet Headers + Outlet Risers (divided by bay count)
        lines["cooler_bay_risers"] = {
            "tag": "L-112",
            "name": "Gaz Soğutucu Bay Giriş Yükseltici Branşmanları (E-101 Giriş Riser)",
            "service": "Fin-Fan Bay Giriş Headerı Besleme Borusu (Debi / Bay Sayısı)",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Bay Branşmanı (Soğutucu Giriş Riser)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Gaz Soğutucu Giriş Dağıtım Manifoldu (L-111)",
            "to_boundary": "Bay Giriş Headerı (L-112A • E-101)",
            "boundary_summary": "E-101 Giriş Manifoldu ➔ Bay Giriş Headerı",
            "flow_kgs": round(flow_per_bay, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(flow_per_bay, p_out_bar, t_discharge_c, v_limit_ms),
        }

        lines["cooler_bay_inlet_header"] = {
            "tag": "L-112A",
            "name": "Gaz Soğutucu Bay Giriş Headerı (Her Bay İçin Ayrı Sıcak Header)",
            "service": "Fin-Fan Bay Tüp Demeti Giriş Kollektörü (Debi / Bay Sayısı)",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Bay Headerı (Soğutucu Giriş)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Bay Giriş Riser Branşmanı (L-112)",
            "to_boundary": "Bay Fin-Tüp Demeti Giriş Nozulları (E-101)",
            "boundary_summary": "Bay Giriş Riser ➔ Bay Giriş Headerı ➔ Tüp Demeti",
            "flow_kgs": round(flow_per_bay, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(flow_per_bay, p_out_bar, t_discharge_c, v_limit_ms),
        }

        lines["cooler_bay_outlet_header"] = {
            "tag": "L-112B",
            "name": "Gaz Soğutucu Bay Çıkış Headerı (Her Bay İçin Ayrı Soğuk Header)",
            "service": "Fin-Fan Bay Tüp Demeti Çıkış Kollektörü (Debi / Bay Sayısı)",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Bay Headerı (Soğutucu Çıkış)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Bay Fin-Tüp Demeti Çıkış Nozulları (E-101)",
            "to_boundary": "Bay Çıkış Riser Branşmanı (L-112C)",
            "boundary_summary": "Tüp Demeti ➔ Bay Çıkış Headerı ➔ Bay Çıkış Riser",
            "flow_kgs": round(flow_per_bay, 2),
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": v_limit_ms,
            **_size_line(flow_per_bay, p_cooled, t_cooled_c, v_limit_ms),
        }

        lines["cooler_bay_outlet_risers"] = {
            "tag": "L-112C",
            "name": "Gaz Soğutucu Bay Çıkış Bağlantı Boruları (E-101 Çıkış Riser)",
            "service": "Fin-Fan Bay Çıkış Headerı ➔ Soğuk Toplama Manifoldu (Debi / Bay Sayısı)",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Bay Branşmanı (Soğutucu Çıkış Riser)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Bay Çıkış Headerı (L-112B • E-101)",
            "to_boundary": "Gaz Soğutucu Soğuk Çıkış Toplama Manifoldu (L-114)",
            "boundary_summary": "Bay Çıkış Headerı ➔ E-101 Soğuk Çıkış Manifoldu",
            "flow_kgs": round(flow_per_bay, 2),
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": v_limit_ms,
            **_size_line(flow_per_bay, p_cooled, t_cooled_c, v_limit_ms),
        }

        # 13. Gas Cooler By-Pass Line (TCV Note 17)
        lines["cooler_bypass"] = {
            "tag": "L-113",
            "name": "Gaz Soğutucu Sıcaklık Kontrol Baypas Hattı (TCV Note 17)",
            "service": "İkincil Sıcaklık Kontrol Branşmanı",
            "hierarchy_level": "equipment_branch",
            "hierarchy_label": "Ekipman Kontrol Branşmanı (TCV Baypas)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Gaz Soğutucu Sıcak Giriş Manifoldu (Note 17 Ayrımı)",
            "to_boundary": "TCV-101 Vanası ➔ Gaz Soğutucu Soğuk Çıkış / Discharge Karışım Noktası",
            "boundary_summary": "E-101 Sıcak Giriş ➔ TCV-101 ➔ Soğuk Çıkış Karışımı",
            "flow_kgs": round(bypass_flow, 2),
            "pressure_bar": p_out_bar,
            "temp_c": t_discharge_c,
            "max_vel_target": v_limit_ms,
            **_size_line(bypass_flow, p_out_bar, t_discharge_c, v_limit_ms),
        }

        # 14. Gas Cooler Cold Outlet Collection Manifold (Returns cooled gas to Station Discharge Header)
        lines["cooler_outlet"] = {
            "tag": "L-114",
            "name": "Gaz Soğutucu Soğuk Çıkış Toplama Manifoldu (E-101 Çıkış)",
            "service": "Fin-Fan Hava Soğutucu Ekipman Çıkış Borulaması",
            "hierarchy_level": "equipment_header",
            "hierarchy_label": "Ekipman Bağlantı Borulaması (Soğutucu Çıkış)",
            "parent_header": "station_discharge_header",
            "from_boundary": "Gaz Hava Soğutucu (E-101) Çıkış Riser Toplama Manifoldu",
            "to_boundary": "Station Discharge Header Soğutulmuş Gaz Dönüş Bağlantısı (PIG-L Yönü)",
            "boundary_summary": "E-101 Soğuk Çıkış Manifoldu ➔ Station Discharge Header",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": v_limit_ms,
            **_size_line(mass_flow_kgs, p_cooled, t_cooled_c, v_limit_ms),
        }

        # 15. Mainline Transmission Outlet (After Outlet Pig Launcher PIG-L)
        lines["mainline_outlet"] = {
            "tag": "L-115",
            "name": "Ana İletim Boru Hattı Çıkışı (Mainline Outlet)",
            "service": "İletim Şebekesine Sevk",
            "hierarchy_level": "mainline_tie_in",
            "hierarchy_label": "Ana İletim Sınır Hattı",
            "parent_header": None,
            "from_boundary": "Çıkış Pig Atıcı Kovanı (PIG-L) Çıkış ESDV Flanşı",
            "to_boundary": "Ana İletim Boru Hattı Sevk Tie-In Noktası",
            "boundary_summary": "PIG-L Çıkış Flanşı ➔ Ana İletim Sevk Hattı",
            "flow_kgs": mass_flow_kgs,
            "pressure_bar": p_cooled,
            "temp_c": t_cooled_c,
            "max_vel_target": v_limit_ms,
            "note": "PIG-L aksında 22.5° çift hot bend (S-offset) ile 90° dirsek olmadan toprak altı kottan ana iletim hattına devam eder.",
            **_size_line(mass_flow_kgs, p_cooled, t_cooled_c, v_limit_ms),
        }

        # Preserve each line's standalone velocity-limit sizing BEFORE header equalization
        for l_data in lines.values():
            l_data["individual_nominal_size_in"] = l_data.get("nominal_size_in")
            l_data["individual_nominal_key"] = l_data.get("nominal_key")
            l_data["individual_velocity_ms"] = l_data.get("actual_velocity_ms")

        # Governing Header Rule:
        # Excluding equipment connection piping (MFS, CFS, TC unit branches, ASV loop, Gas Cooler manifolds/risers/bypass),
        # take the largest calculated commercial NPS across all main station & unit headers and apply it to:
        #   - Station Suction Header (`suction_header`, L-102)
        #   - Unit Suction Header (`comp_suction_header`, L-105)
        #   - Unit Discharge Header (`unit_discharge_header`, L-109A)
        #   - Station Discharge Header (`discharge_header`, L-109)
        header_keys = (
            "suction_header",
            "comp_suction_header",
            "unit_discharge_header",
            "discharge_header",
        )
        all_non_equip_header_keys = (
            "suction_header",
            "comp_suction_header",
            "unit_discharge_header",
            "discharge_header",
            "station_recycle",
        )
        header_nominals = [
            (key, lines[key].get("nominal_key"))
            for key in all_non_equip_header_keys
            if lines.get(key, {}).get("nominal_key")
        ]
        governing_header_key = None
        governing_header_nps = None
        if len(header_nominals) >= 2:
            larger_key, larger_nominal = max(
                header_nominals, key=lambda item: nd_sort_key(item[1])
            )
            governing_header_key = larger_key
            governing_header_nps = f'{larger_nominal}"'
            for key in header_keys:
                current = lines[key]
                indiv_nps = current.get("individual_nominal_size_in")
                indiv_key = current.get("individual_nominal_key")
                indiv_vel = current.get("individual_velocity_ms")
                if current.get("nominal_key") == larger_nominal:
                    current["diameter_equalized_to"] = f'{larger_nominal}"'
                    current["header_pair"] = "suction_discharge_common_nps"
                    current["governing_header_key"] = larger_key
                    continue
                meta = {
                    field: current[field]
                    for field in (
                        "tag",
                        "name",
                        "service",
                        "hierarchy_level",
                        "hierarchy_label",
                        "parent_header",
                        "from_boundary",
                        "to_boundary",
                        "boundary_summary",
                        "flow_kgs",
                        "pressure_bar",
                        "temp_c",
                        "max_vel_target",
                    )
                    if field in current
                }
                resized = {
                    **meta,
                    **_size_line(
                        flow_kgs=float(current["flow_kgs"]),
                        p_bar=float(current["pressure_bar"]),
                        t_c=float(current["temp_c"]),
                        max_velocity_ms=float(current["max_vel_target"]),
                        preferred_nominal=larger_nominal,
                    ),
                }
                if resized.get("nominal_key") != larger_nominal:
                    resized = {
                        **meta,
                        **_size_line(
                            flow_kgs=float(current["flow_kgs"]),
                            p_bar=float(current["pressure_bar"]),
                            t_c=float(current["temp_c"]),
                            max_velocity_ms=max(float(current["max_vel_target"]), 30.0),
                            preferred_nominal=larger_nominal,
                        ),
                    }
                resized["max_design_velocity_ms"] = v_limit_ms
                resized["individual_nominal_size_in"] = indiv_nps
                resized["individual_nominal_key"] = indiv_key
                resized["individual_velocity_ms"] = indiv_vel
                resized["diameter_equalized_to"] = f'{larger_nominal}"'
                resized["header_pair"] = "suction_discharge_common_nps"
                resized["governing_header_key"] = larger_key
                resized["equalized_from_nominal_size_in"] = indiv_nps
                lines[key] = resized
            if larger_key in lines:
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

        piping_warnings: List[str] = []
        for line in lines.values():
            vel_status = str(line.get("velocity_status", ""))
            evr = float(line.get("erosion_ratio_pct") or 0.0)
            v_act = line.get("actual_velocity_ms")
            v_ero = line.get("erosion_velocity_ms")
            v_max = line.get("max_design_velocity_ms")
            tag = line.get("tag", "")
            name = line.get("name", "")
            if "Erozyon Limiti Aşıldı" in vel_status or evr >= 100.0:
                piping_warnings.append(
                    f"{tag} ({name}): API RP 14E erozyon hızı aşıldı ({v_act} m/s > {v_ero} m/s, %{evr})."
                )
            elif "Tasarım Hızı Üzerinde" in vel_status:
                piping_warnings.append(
                    f"{tag} ({name}): Tasarım hız sınırı aşıldı ({v_act} m/s > {v_max} m/s, erozyon oranı %{evr})."
                )
            elif evr >= 80.0:
                piping_warnings.append(
                    f"{tag} ({name}): Erozyon hız sınırına yakın çalışma (%{evr} API RP 14E)."
                )
            if line.get("preferred_nominal_requested") and line.get("meets_min_velocity_diameter") is False:
                min_req_nps = line.get("velocity_min_nominal_in") or "-"
                piping_warnings.append(
                    f"{tag} ({name}): Kullanıcı seçimi {line.get('nominal_size_in')}, maks. izin verilen hız "
                    f"({v_max} m/s) için gereken minimum çapın ({min_req_nps}) altındadır (v = {v_act} m/s)."
                )
            std_rec = line.get("standard_recommendation") or {}
            if std_rec.get("is_sufficient") is False:
                piping_warnings.append(
                    f"{tag} ({name}): Seçilen boru et kalınlığı {standard_code} standardı için yetersiz."
                )

        # Overall network statistics & Station Main-Header / Equipment Boundary Architecture
        total_steel_weight_ton_per_km = sum(l["pipe_weight_kg_m"] for l in lines.values()) / 1000.0
        avg_velocity = sum(l["actual_velocity_ms"] for l in lines.values()) / len(lines)

        suct_hdr = lines["suction_header"]
        unit_suct_hdr = lines["comp_suction_header"]
        unit_disch_hdr = lines["unit_discharge_header"]
        disch_hdr = lines["discharge_header"]
        piping_architecture: Dict[str, Any] = {
            "governing_header_rule": {
                "rule": "max_of_non_equipment_headers",
                "governing_line_key": governing_header_key,
                "governing_nominal_size_in": governing_header_nps,
                "max_velocity_ms": v_limit_ms,
                "equalized_headers": list(header_keys),
            },
            "main_headers": {
                "station_suction_header": {
                    "key": "station_suction_header",
                    "name": "Station Suction Header (Ana İstasyon Emiş Header'ı)",
                    "line_keys": ["suction_header", "comp_suction_header"],
                    "tags": ["L-102", "L-105"],
                    "nominal_size_in": suct_hdr.get("nominal_size_in"),
                    "individual_nominal_size_in": suct_hdr.get("individual_nominal_size_in"),
                    "acceptable_nominals": suct_hdr.get("acceptable_nominals"),
                    "od_mm": suct_hdr.get("od_mm"),
                    "from_boundary": "Giriş Pig Alıcı Kovanı (PIG-R) Çıkış İzolasyon Vanası (MOV/ESDV)",
                    "to_boundary": "Turbo-Kompresör (TC) Üniteleri Emiş Bağlantı Header'ı Sonu (Kör Flanş / Gelecek Ünite Tie-In)",
                    "connected_equipment_lines": [
                        "cyclone_branch",
                        "cyclone_outlet_branch",
                        "filter_branch",
                        "filter_outlet_branch",
                        "comp_suction_branch",
                        "station_recycle",
                    ],
                    "description": (
                        "Giriş pig kovanından (PIG-R) başlayıp MFS siklon seperatör, CFS kartuş filtre ve "
                        "turbo-kompresör ünitelerinin kendi branşmanlarıyla bağlandığı ve TC üniteleri emiş "
                        "bağlantı header'ı sonunda sona eren ana büyük çaplı emiş borulaması."
                    ),
                },
                "unit_suction_header": {
                    "key": "unit_suction_header",
                    "name": "Unit Suction Header (TC Üniteleri Emiş Header'ı)",
                    "line_keys": ["comp_suction_header"],
                    "tags": ["L-105"],
                    "nominal_size_in": unit_suct_hdr.get("nominal_size_in"),
                    "individual_nominal_size_in": unit_suct_hdr.get("individual_nominal_size_in"),
                    "acceptable_nominals": unit_suct_hdr.get("acceptable_nominals"),
                    "od_mm": unit_suct_hdr.get("od_mm"),
                    "from_boundary": unit_suct_hdr.get("from_boundary"),
                    "to_boundary": unit_suct_hdr.get("to_boundary"),
                    "connected_equipment_lines": ["comp_suction_branch"],
                    "description": "CFS çıkışından itibaren TC ünite emiş branşmanlarını besleyen ünite emiş header'ı.",
                },
                "unit_discharge_header": {
                    "key": "unit_discharge_header",
                    "name": "Unit Discharge Header (TC Üniteleri Basma Header'ı)",
                    "line_keys": ["unit_discharge_header"],
                    "tags": ["L-109A"],
                    "nominal_size_in": unit_disch_hdr.get("nominal_size_in"),
                    "individual_nominal_size_in": unit_disch_hdr.get("individual_nominal_size_in"),
                    "acceptable_nominals": unit_disch_hdr.get("acceptable_nominals"),
                    "od_mm": unit_disch_hdr.get("od_mm"),
                    "from_boundary": unit_disch_hdr.get("from_boundary"),
                    "to_boundary": unit_disch_hdr.get("to_boundary"),
                    "connected_equipment_lines": ["comp_discharge_branch", "cooler_inlet"],
                    "description": "TC ünite sıcak basma branşmanlarının toplandığı ve Gaz Soğutucuya bağlanan ünite basma header'ı.",
                },
                "station_discharge_header": {
                    "key": "station_discharge_header",
                    "name": "Station Discharge Header (Ana İstasyon Basma Header'ı)",
                    "line_keys": ["unit_discharge_header", "discharge_header"],
                    "tags": ["L-109A", "L-109"],
                    "nominal_size_in": disch_hdr.get("nominal_size_in"),
                    "individual_nominal_size_in": disch_hdr.get("individual_nominal_size_in"),
                    "acceptable_nominals": disch_hdr.get("acceptable_nominals"),
                    "od_mm": disch_hdr.get("od_mm"),
                    "from_boundary": "Turbo-Kompresör (TC) Ünite Basma Çıkış Hatlarının Bağlandığı Header Başlangıcı",
                    "to_boundary": "Çıkış Pig Atıcı Kovanı (PIG-L) Giriş İzolasyon Vanası (MOV/ESDV)",
                    "connected_equipment_lines": [
                        "comp_discharge_branch",
                        "cooler_inlet",
                        "cooler_bay_risers",
                        "cooler_bay_inlet_header",
                        "cooler_bay_outlet_header",
                        "cooler_bay_outlet_risers",
                        "cooler_bypass",
                        "cooler_outlet",
                        "station_recycle",
                    ],
                    "description": (
                        "Turbo-kompresör ünite çıkış hatlarının bağlandığı basma header'ı ile başlayıp gaz hava "
                        "soğutucu (Gas Cooler) giriş/çıkış manifold bağlantılarını taşıyarak çıkış pig kovanına "
                        "(PIG-L) kadar kesintisiz devam eden ana büyük çaplı basma borulaması."
                    ),
                },
            },
            "naming_limitations": [
                "Yardımcı ince borulamalar (2\"–4\" yakıt gazı, enstrüman havası, kondensat LCV drenaj alt hatları ve vana çukuru tahliyeleri) görsel sadelik amacıyla tekil izometrik hat numarası yerine üst ekipman sistemi altında gruplanmıştır.",
                "TC ünite emiş/basma branşmanlarında (PFD Note 32) header branşman çapından kompresör gövde nozul çapına geçişteki konik redüksiyon/ekspansiyon parçası 3D sahnede tekil branşman çapıyla temsil edilmekte, sınır tanımında açıkça belirtilmektedir.",
                "3D sahnede kamera uzaklaştığında etiket çakışmasını (occlusion) önlemek için sabit 3D plakalar ana omurga kollektörleri, başlangıç/bitiş sınırları ve ana branşman gruplarıyla sınırlandırılmış; tekil segment kimliği boru tıklama (HUD) ile sunulmuştur.",
                "Çoklu iletim hattı giriş/çıkışları (farklı çaplı paralel pig kovanları) parametrik istasyon modelinde tek eşdeğer giriş pig kovanı (PIG-R) ve tek eşdeğer çıkış pig kovanı (PIG-L) sınır koşuluyla modellenmiştir.",
            ],
        }

        return {
            "success": True,
            "design_standard": "ASME B31.8 / API 5L / API RP 14E",
            "pipe_material": pipe_material,
            "design_factor_F": design_factor_F,
            "pipe_standard": standard_code,
            "psl_level": str(psl_level or "PSL2"),
            "max_velocity_ms": round(v_limit_ms, 2),
            "eos_model": eos_key if gas_obj is not None else "approx_correlation",
            "total_lines_sized": len(lines),
            "average_network_velocity_ms": round(avg_velocity, 2),
            "estimated_steel_weight_ton_per_km": round(total_steel_weight_ton_per_km, 2),
            "warnings": piping_warnings,
            "piping_architecture": piping_architecture,
            "lines": lines,
        }
