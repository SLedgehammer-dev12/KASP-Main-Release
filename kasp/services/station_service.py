"""Compressor Station Modeling & Process Flow Service (station_service.py).

Implements rigorous process engineering sizing for natural gas compressor stations:
- Mainline Suction & Discharge Tie-ins with Pig Receiver and Pig Launcher
- Suction Header & Dynamic Parallel Cyclone Separators (Scrubbers)
- Dynamic Parallel Cartridge Coalescing / Dust Filters
- Compressor Shelter / Unit Building housing N Parallel Turbo-Compressor Trains
- Individual Hot Gas Anti-Surge Recycle Loops with Fast-Acting Valves
- Station-wide Main Recycle / Bypass Line (Discharge to Suction Header)
- Fin-Fan Gas Air Coolers (Cooling Heat Duty & Dynamic Bay Count)
- Overpressure & Emergency Depressurization (PSV & Blowdown Valves)
- Process Nodal Telemetry & Animated Flow Vector Velocities
"""

import math
from typing import Any, Dict, List, Optional
from kasp.core.constants import MOLAR_MASSES, normalize_component
from kasp.core.units import UnitSystem
from kasp.services.pipe_sizing_service import PipeSizingService


def calculate_station_process_model(
    inputs: Dict[str, Any],
    design_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculates comprehensive compressor station layout, sizing metrics, and nodal states.

    Args:
        inputs: Design inputs dict containing flow, p_in, p_out, t_in, gas_comp, etc.
        design_results: Optional design calculation results from calculation_service.

    Returns:
        Structured dictionary with station summary, dynamic equipment counts,
        nodal process states, and animated pipe flow velocity vectors.
    """
    # 1. Parse Baseline Process Inputs
    # Station UI provides an explicit kg/s slider in `mass_flow`; direct API
    # callers may provide `flow` + `flow_unit`. Prefer the explicit mass_flow
    # value so the live station slider is not silently ignored.
    raw_mass_flow = inputs.get("mass_flow")
    if raw_mass_flow is not None and str(raw_mass_flow).strip() != "":
        try:
            mass_flow_kgs = float(raw_mass_flow)
        except (TypeError, ValueError):
            mass_flow_kgs = 50.0
    else:
        try:
            raw_flow = float(inputs.get("flow", inputs.get("mass_flow", 50.0)) or 50.0)
        except (TypeError, ValueError):
            raw_flow = 50.0
        flow_unit = str(inputs.get("flow_unit", "kg/s")).strip()

        # Robust flow conversion to kg/s across all supported engineering units
        # Standard natural gas density at 15°C, 1.01325 bar is approx 0.772 kg/Sm³
        if flow_unit == "kg/s":
            mass_flow_kgs = raw_flow
        elif flow_unit in ("kg/h", "kgh"):
            mass_flow_kgs = raw_flow / 3600.0
        elif flow_unit in ("Sm³/h", "Sm3/h", "m3/h", "m³/h", "Nm³/h", "Nm3/h"):
            mass_flow_kgs = (raw_flow * 0.772) / 3600.0
        elif flow_unit in ("MMSCFD", "mmscfd"):
            # 1 MMSCFD ≈ 0.320 kg/s
            mass_flow_kgs = raw_flow * 0.320
        elif flow_unit in ("MMSCMD", "mmscmd"):
            # 1 MMSCMD = 1e6 Sm³/day
            mass_flow_kgs = (raw_flow * 1e6 * 0.772) / 86400.0
        else:
            mass_flow_kgs = max(1.0, raw_flow)

    if not math.isfinite(mass_flow_kgs) or mass_flow_kgs <= 0:
        mass_flow_kgs = 50.0
    else:
        mass_flow_kgs = max(0.5, mass_flow_kgs)

    # Pressures in bar(a) — use the shared unit system so bar(g) is converted correctly.
    p_in_unit = str(inputs.get("p_in_unit", "bar(a)"))
    p_out_unit = str(inputs.get("p_out_unit", "bar(a)"))
    try:
        raw_p_in = float(inputs.get("p_in", 25.0) or 25.0)
    except (TypeError, ValueError):
        raw_p_in = 25.0
    try:
        raw_p_out = float(inputs.get("p_out", 75.0) or 75.0)
    except (TypeError, ValueError):
        raw_p_out = 75.0

    p_in = UnitSystem.convert_pressure(raw_p_in, p_in_unit, "bar(a)")
    p_out = UnitSystem.convert_pressure(raw_p_out, p_out_unit, "bar(a)")

    if not math.isfinite(p_in) or p_in < 0.5:
        p_in = 0.5

    # Ensure pressure ratio >= 1.05
    if not math.isfinite(p_out) or p_out <= p_in:
        p_out = p_in * 2.5

    # Temperature in °C (supports °C / K / °F inputs from the UI)
    try:
        raw_t_in = float(inputs.get("t_in", 20.0) or 20.0)
    except (TypeError, ValueError):
        raw_t_in = 20.0

    t_in = UnitSystem.convert_temperature(
        raw_t_in,
        str(inputs.get("t_in_unit", "°C")),
        "°C",
    )
    if not math.isfinite(t_in):
        t_in = 20.0
    # Clamping temperature to physical range above absolute zero (-100 °C = 173.15 K)
    t_in = max(-100.0, min(250.0, t_in))
    gas_comp = inputs.get("gas_comp") or {"CH4": 0.95, "C2H6": 0.03, "N2": 0.02}

    # Estimate average Molecular Weight using the canonical component map.
    # This accepts both web keys (METHANE) and legacy keys (CH4) via ALIAS_MAP.
    norm_comp = {}
    tot_mol = sum(float(v) for v in gas_comp.values()) or 1.0
    for k, v in gas_comp.items():
        norm_comp[normalize_component(k)] = float(v) / tot_mol

    mw = sum(norm_comp.get(g, 0.0) * MOLAR_MASSES.get(g, 16.04) for g in norm_comp)
    if mw <= 0.0:
        mw = 18.2  # Typical Natural Gas MW fallback

    # Gas densities (approx PR / ideal gas with compressibility Z ~ 0.88 - 0.92)
    R_gas = 8.314462 / (mw * 1e-3)  # J/(kg*K)
    T_in_K = t_in + 273.15
    Z_in = 0.89
    rho_suction = (p_in * 1e5) / (Z_in * R_gas * T_in_K)  # kg/m3

    # MMSCMD (Million Standard Cubic Meters per Day at 15°C, 1.01325 bar)
    rho_std = (1.01325e5) / (1.0 * R_gas * 288.15)
    vol_flow_mmscmd = (mass_flow_kgs * 86400.0) / (rho_std * 1e6)

    # 2. Dynamic Cyclone Separator (Scrubber) Sizing
    # Typical heavy liquid & solid dropout scrubber vessel capacity is ~15-25 kg/s (2.0-3.0 MMSCMD)
    unit_cap_cyclone = 22.0  # kg/s per cyclone vessel
    user_cyclone_op = inputs.get("cyclone_op_count") or inputs.get("cyclones_count")
    if user_cyclone_op:
        cyclone_op_count = max(1, min(12, int(user_cyclone_op)))
    else:
        cyclone_op_count = max(1, min(8, math.ceil(mass_flow_kgs / unit_cap_cyclone)))
    cyclone_total_count = cyclone_op_count + 1  # Standard N+1 sparing
    flow_per_cyclone = mass_flow_kgs / cyclone_op_count
    dp_cyclone = round(0.30 * (flow_per_cyclone / unit_cap_cyclone) ** 1.8, 3)  # bar drop
    p_post_cyclone = round(p_in - dp_cyclone, 2)

    # 3. Dynamic Cartridge Coalescing Filter Sizing
    # Downstream of cyclones on suction header, fine particulate (< 0.3 micron)
    unit_cap_filter = 18.0  # kg/s per filter vessel
    user_filter_op = inputs.get("filter_op_count") or inputs.get("filters_count")
    if user_filter_op:
        filter_op_count = max(1, min(12, int(user_filter_op)))
    else:
        filter_op_count = max(1, min(8, math.ceil(mass_flow_kgs / unit_cap_filter)))
    filter_total_count = filter_op_count + 1  # Standard N+1 sparing
    flow_per_filter = mass_flow_kgs / filter_op_count
    dp_filter = round(0.22 * (flow_per_filter / unit_cap_filter) ** 1.5, 3)
    p_comp_inlet = round(p_post_cyclone - dp_filter, 2)

    # 4. Dynamic Turbo-Compressor Train Sizing & Unit Building
    # Use the real design payload when available (power_shaft_per_unit_kw,
    # t_out_c, head_kj_kg, actual_poly_efficiency). Legacy callers that send
    # a `summary` sub-document are still supported.
    dr = design_results or {}
    summ = dr.get("summary") or {}

    def _first_number(*values):
        for value in values:
            if value is None:
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(num):
                return num
        return None

    design_unit_cap = _first_number(
        dr.get("mass_flow_per_unit_kgs"),
        summ.get("mass_flow"),
    )

    design_power_total = _first_number(
        dr.get("power_shaft_total_kw"),
        summ.get("power"),
        summ.get("gas_power"),
    )
    design_num_units = max(1, int(_first_number(dr.get("num_units")) or 1))
    design_power_per_unit = _first_number(
        dr.get("power_shaft_per_unit_kw"),
        (design_power_total / design_num_units) if design_power_total else None,
    )

    design_t_discharge = _first_number(dr.get("t_out_c"), dr.get("t_out"), summ.get("t_out"), summ.get("t2"))
    if design_t_discharge is not None and design_t_discharge > 200.0:
        design_t_discharge -= 273.15

    design_head = _first_number(
        dr.get("head_kj_kg"),
        dr.get("head_total_kj_kg"),
        summ.get("head"),
        summ.get("polytropic_head"),
    )

    design_eff = _first_number(
        dr.get("actual_poly_efficiency"),
        summ.get("eff"),
        summ.get("polytropic_efficiency"),
    )
    if design_eff is not None and 0.0 < design_eff <= 1.0:
        design_eff *= 100.0

    # Only trust the design thermodynamic point when the station pressure ratio
    # still matches it. If the live panel changes P_in/P_out, fall back to the
    # local polytropic estimate instead of showing a stale design power.
    design_pr = _first_number(dr.get("compression_ratio"))
    current_pr = p_out / p_in if p_in > 0 else 1.0
    if design_pr and design_pr > 0 and abs(current_pr - design_pr) / design_pr > 0.01:
        design_power_per_unit = None
        design_head = None
        design_eff = None
        design_t_discharge = None

    # Flow per design train is used later to scale power when only mass flow changes.
    design_total_flow = _first_number(dr.get("mass_flow_total_kgs"))
    design_flow_per_unit = (
        design_total_flow / design_num_units
        if design_total_flow and design_total_flow > 0
        else None
    )

    unit_cap_comp = design_unit_cap if design_unit_cap and design_unit_cap > 0 else 35.0

    pr_safe = max(1.001, p_out / max(0.5, p_in))

    if design_head and design_head > 0:
        polytropic_head_kj = round(design_head, 2)
    else:
        polytropic_head_kj = round(115.0 * math.log(pr_safe), 2)

    if design_eff and design_eff > 0:
        polytropic_eff = round(design_eff, 2)
    else:
        polytropic_eff = 82.5
    polytropic_eff = max(10.0, min(95.0, polytropic_eff))

    if design_t_discharge is not None:
        t_discharge_hot = round(design_t_discharge, 1)
    else:
        # Isentropic/polytropic temperature estimate
        k_ratio = 1.28
        n_poly = (polytropic_eff / 100.0 * (k_ratio - 1)) / k_ratio + 1.0
        t_discharge_hot = round(T_in_K * (pr_safe ** ((n_poly - 1) / n_poly)) - 273.15, 1)
    t_discharge_hot = max(t_in, min(350.0, t_discharge_hot))

    user_comp_op = inputs.get("comp_op_count") or inputs.get("operating_trains")
    if user_comp_op:
        comp_op_count = max(1, min(8, int(user_comp_op)))
    else:
        comp_op_count = max(1, min(6, math.ceil(mass_flow_kgs / unit_cap_comp)))
    comp_total_count = comp_op_count + 1  # Standard N+1 operational reliability
    flow_per_comp = round(mass_flow_kgs / comp_op_count, 2)

    if design_power_per_unit is not None and design_power_per_unit > 0:
        scaled_power_per_unit = design_power_per_unit
        if design_flow_per_unit and design_flow_per_unit > 0:
            scaled_power_per_unit *= (mass_flow_kgs / comp_op_count) / design_flow_per_unit
        power_per_unit_kw = round(scaled_power_per_unit, 1)
        total_power_kw = round(power_per_unit_kw * comp_op_count, 1)
    else:
        total_power_kw = round(
            (mass_flow_kgs * polytropic_head_kj) / (polytropic_eff / 100.0 * 0.98),
            1,
        )
        power_per_unit_kw = round(total_power_kw / comp_op_count, 1)

    # Unit Building Dimensions (housing N compressor trains)
    shelter_width_m = 24.0
    shelter_length_m = round(14.0 * comp_total_count + 8.0, 1)
    shelter_height_m = 12.5

    # 5. Anti-Surge & Recycle Lines Sizing
    surge_flow_limit = round(0.68 * flow_per_comp, 2)
    asv_valve_size_in = 8 if flow_per_comp < 30.0 else (12 if flow_per_comp < 60.0 else 16)
    asv_stroke_time_s = 0.8  # Fail-open fast pneumatic actuator (< 1.0s)
    station_recycle_capacity_kgs = round(mass_flow_kgs * 1.0, 1)

    def _size_control_valve(path, flow_kgs, p_in_bar, p_out_bar, t_c):
        try:
            from kasp.integrations.control_valve.adapter import ControlValveAdapter

            p_in_val = max(0.5, float(p_in_bar))
            p_out_val = max(0.1, float(p_out_bar))
            if p_in_val <= p_out_val:
                p_out_val = p_in_val * 0.8

            res = ControlValveAdapter().calculate(
                {
                    "service": "gas",
                    "composition": gas_comp,
                    "mass_flow_kgs": max(0.001, float(flow_kgs)),
                    "p_in_bar": p_in_val,
                    "p_out_bar": p_out_val,
                    "t_c": max(-50.0, float(t_c)),
                    "path": path,
                }
            )
            return res.get("results", {}), list(res.get("warnings", []) or [])
        except BaseException as exc:
            return None, [f"{path} vana boyutlandırma hatası: {exc}"]

    asv_sizing, asv_warnings = _size_control_valve(
        "ASV", surge_flow_limit, p_out, max(p_in, p_comp_inlet), t_discharge_hot
    )
    pcv_sizing, pcv_warnings = _size_control_valve(
        "PCV", station_recycle_capacity_kgs, p_out, max(p_in, p_comp_inlet), t_discharge_hot
    )

    # 6. Fin-Fan Gas Air Coolers Sizing
    # High discharge gas (100-140°C) must be cooled to pipeline limit (approx 40-45°C)
    t_target_pipeline = 45.0
    cp_avg = 2.45  # kJ/(kg*K) average heat capacity for natural gas
    heat_duty_mw = round(max(0.1, mass_flow_kgs * cp_avg * (t_discharge_hot - t_target_pipeline) / 1000.0), 2)
    cooler_bay_capacity_mw = 3.2  # MW thermal duty per cooler bay
    user_cooler_bays = inputs.get("cooler_bays_count")
    if user_cooler_bays:
        cooler_bays_count = max(2, min(16, int(user_cooler_bays)))
    else:
        cooler_bays_count = max(2, min(8, math.ceil(heat_duty_mw / cooler_bay_capacity_mw)))
    dp_cooler = 0.40  # bar
    p_post_cooler = round(p_out - dp_cooler, 2)

    air_cooler_design = None
    air_cooler_warnings = []
    include_air_cooler_design = bool(inputs.get("include_air_cooler_design", False))
    if include_air_cooler_design and t_discharge_hot > t_target_pipeline + 1.0:
        try:
            from kasp.integrations.air_cooler.adapter import AirCoolerAdapter

            design = AirCoolerAdapter().calculate(
                {
                    "composition": gas_comp,
                    "mass_flow_kgs": mass_flow_kgs,
                    "p_in_bar": p_out,
                    "p_out_bar": p_post_cooler,
                    "t_in_c": t_discharge_hot,
                    "t_out_c": t_target_pipeline,
                    "air_in_c": float(inputs.get("ambient_temp", 15.0) or 15.0),
                    "air_out_c": float(inputs.get("ambient_temp", 15.0) or 15.0) + 20.0,
                    "auto_size": True,
                }
            )
            air_cooler_design = design.get("results")
            air_cooler_warnings = list(design.get("warnings", []) or [])
        except BaseException as exc:
            air_cooler_warnings.append(f"Detaylı hava soğutucu tasarımı yapılamadı: {exc}")

    tcv_sizing, tcv_warnings = _size_control_valve(
        "TCV", mass_flow_kgs * 0.35, p_out, p_post_cooler, t_discharge_hot
    )
    # Gas Cooler By-pass Line (BOTAŞ PFD Note 17: TCV secondary temperature control)
    cooler_bypass_valve_size_in = 16 if mass_flow_kgs < 60.0 else 24

    # 7. Safety & Depressurization (PSV & Blowdown)
    psv_set_pressure_bar = round(p_out * 1.10, 1)
    psv_count = 2  # 1 Duty + 1 Standby (100% capacity each)
    bdv_depressurization_time_min = 15.0  # API 521 standard

    # Preliminary gas relief sizing via the integrated API 520/521 module.
    psv_sizing = None
    psv_sizing_warnings = []
    try:
        from kasp.integrations.psv.adapter import PSVAdapter

        psv_result = PSVAdapter().calculate(
            {
                "service": "gas",
                "p1_bar": psv_set_pressure_bar * 1.10,
                "p2_bar": 1.01325,
                "t_c": t_discharge_hot,
                "mass_flow_kgs": mass_flow_kgs,
                "composition": gas_comp,
                "valve_type": "conventional",
                "num_valves": 1,
            }
        )
        psv_sizing = psv_result.get("results", {})
        psv_sizing_warnings = list(psv_result.get("warnings", []) or [])
        if psv_sizing.get("Required_Area_sqin") is not None:
            psv_sizing = {
                "required_area_sqin": psv_sizing.get("Required_Area_sqin"),
                "selected_orifice": psv_sizing.get("Selected_Orifice_Letter"),
                "selected_orifice_area_sqin": psv_sizing.get("Selected_Orifice_Area_sqin"),
                "orifice_loading_pct": psv_sizing.get("Orifice_Loading_Pct"),
                "flow_type": psv_sizing.get("Flow_Type"),
                "standard": (psv_result.get("provenance") or {}).get("standard"),
                "warnings": psv_sizing_warnings,
            }
    except BaseException as exc:
        psv_sizing_warnings.append(f"PSV ön boyutlandırma yapılamadı: {exc}")

    # 8. Condensate Drain Collection (BOTAŞ PFD Note 14 & 15)
    liquid_condensate_rate_m3h = round(0.008 * mass_flow_kgs, 3)
    condensate_tank_volume_m3 = round(max(10.0, liquid_condensate_rate_m3h * 24.0 * 2.5), 1)

    # 8. Mainline Pigging Units
    mainline_nps = 24 if mass_flow_kgs < 50 else (36 if mass_flow_kgs < 120 else 48)
    pig_receiver_size = f"{mainline_nps}\" x {mainline_nps + 4}\" Class 600"
    pig_launcher_size = f"{mainline_nps}\" x {mainline_nps + 4}\" Class 900"

    # 9. Process Nodes Matrix
    nodes = [
        {
            "id": "N01_MAINLINE_INLET",
            "name": "Ana Hat Emiş Girişi (Mainline In)",
            "pressure_bar": round(p_in, 2),
            "temp_c": round(t_in, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Gaz (Vapor)",
            "state_desc": "Pig Alıcı (Trap) öncesi ham hat gazı",
            "color": "#38bdf8",
        },
        {
            "id": "N02_SUCTION_HEADER",
            "name": "Emiş Kolektörü (Suction Header)",
            "pressure_bar": round(p_in - 0.05, 2),
            "temp_c": round(t_in, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Gaz (Vapor)",
            "state_desc": "Siklon seperatör dağıtım kolektörü",
            "color": "#0ea5e9",
        },
        {
            "id": "N03_CYCLONE_OUTLET",
            "name": "Siklon Çıkışı (Post-Cyclone)",
            "pressure_bar": p_post_cyclone,
            "temp_c": round(t_in - 0.2, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Temizlenmiş Gaz (>10µm serbest)",
            "state_desc": f"{cyclone_op_count} aktif siklon sonrası sıvı ayrıştırılmış gaz",
            "color": "#2563eb",
        },
        {
            "id": "N04_FILTER_OUTLET",
            "name": "Kartuş Filtre Çıkışı (Post-Filter)",
            "pressure_bar": p_comp_inlet,
            "temp_c": round(t_in - 0.3, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Hassas Gaz (<0.3µm aerosol)",
            "state_desc": f"{filter_op_count} aktif kartuş sonrası süper-temiz gaz",
            "color": "#1d4ed8",
        },
        {
            "id": "N05_COMPRESSOR_DISCHARGE",
            "name": "Kompresör Çıkışı (Compressor Out)",
            "pressure_bar": round(p_out, 2),
            "temp_c": round(t_discharge_hot, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Yüksek Basınçlı Sıcak Gaz",
            "state_desc": f"{comp_op_count} aktif turbo-kompresör treni çıkışı",
            "color": "#ef4444",
        },
        {
            "id": "N06_DISCHARGE_HEADER",
            "name": "Basma Kolektörü (Discharge Header)",
            "pressure_bar": round(p_out - 0.05, 2),
            "temp_c": round(t_discharge_hot - 0.5, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Basma Kolektör Gazı",
            "state_desc": "Hava soğutucular ve ana recycle ayrım noktası",
            "color": "#dc2626",
        },
        {
            "id": "N07_COOLER_OUTLET",
            "name": "Soğutucu Çıkışı (Post-Cooler)",
            "pressure_bar": p_post_cooler,
            "temp_c": round(t_target_pipeline, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Soğutulmuş Hat Gazı",
            "state_desc": f"{cooler_bays_count} bay hava soğutucu çıkışı",
            "color": "#10b981",
        },
        {
            "id": "N08_MAINLINE_OUTLET",
            "name": "Ana Hat İletim Basma (Mainline Out)",
            "pressure_bar": round(p_post_cooler - 0.05, 2),
            "temp_c": round(t_target_pipeline, 1),
            "flow_kgs": round(mass_flow_kgs, 2),
            "phase": "Şebeke Teslim Gazı",
            "state_desc": "Pig Atıcı (Trap) sonrası ana iletim hattı",
            "color": "#059669",
        },
    ]

    # 10. Dynamic Pipe Sizing & Natural Gas Flow Network (ASME B36.10M / API 5L / API RP 14E)
    station_piping = PipeSizingService.size_station_network(
        mass_flow_kgs=mass_flow_kgs,
        p_in_bar=p_in,
        p_out_bar=p_out,
        t_in_c=t_in,
        t_discharge_c=t_discharge_hot,
        t_cooled_c=t_target_pipeline,
        comp_op_count=comp_op_count,
        cyclone_op_count=cyclone_op_count,
        filter_op_count=filter_op_count,
        cooler_bays_count=cooler_bays_count,
        gas_mw=mw,
        pipe_material=inputs.get("pipe_material", "API 5L X70"),
        design_factor_F=float(inputs.get("design_factor_F", 0.50)),
        pipe_standard=inputs.get("pipe_standard", "BOTAŞ"),
        psl_level=inputs.get("psl_level", "PSL2"),
    )
    p_lines = station_piping["lines"]

    # 11. Pipe Flow Vectors (Dynamic speed factors scaled by actual flow velocities)
    pipe_flows = {
        "main_suction": {
            "speed_factor": round(max(0.4, p_lines["suction_header"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["suction_header"]["actual_velocity_ms"],
            "nominal_size": p_lines["suction_header"]["nominal_size_in"],
            "dir": "right",
            "color": "#0ea5e9",
            "status": "active",
        },
        "cyclone_branches": {
            "speed_factor": round(max(0.3, p_lines["cyclone_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["cyclone_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["cyclone_branch"]["nominal_size_in"],
            "dir": "down",
            "color": "#2563eb",
            "status": "active",
        },
        "filter_branches": {
            "speed_factor": round(max(0.3, p_lines["filter_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["filter_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["filter_branch"]["nominal_size_in"],
            "dir": "down",
            "color": "#1d4ed8",
            "status": "active",
        },
        "comp_suction": {
            "speed_factor": round(max(0.4, p_lines["comp_suction_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["comp_suction_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["comp_suction_branch"]["nominal_size_in"],
            "dir": "right",
            "color": "#3b82f6",
            "status": "active",
        },
        "comp_discharge": {
            "speed_factor": round(max(0.4, p_lines["comp_discharge_branch"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["comp_discharge_branch"]["actual_velocity_ms"],
            "nominal_size": p_lines["comp_discharge_branch"]["nominal_size_in"],
            "dir": "up",
            "color": "#ef4444",
            "status": "active",
        },
        "anti_surge_loop": {
            "speed_factor": round(p_lines["anti_surge_loop"]["actual_velocity_ms"] / 15.0, 2),
            "actual_velocity_ms": p_lines["anti_surge_loop"]["actual_velocity_ms"],
            "nominal_size": p_lines["anti_surge_loop"]["nominal_size_in"],
            "dir": "down",
            "color": "#f59e0b",
            "status": "standby",
        },
        "station_recycle": {
            "speed_factor": 0.0,
            "actual_velocity_ms": p_lines["station_recycle"]["actual_velocity_ms"],
            "nominal_size": p_lines["station_recycle"]["nominal_size_in"],
            "dir": "left",
            "color": "#f97316",
            "status": "closed",
        },
        "cooler_inlet": {
            "speed_factor": round(max(0.4, p_lines["cooler_inlet"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["cooler_inlet"]["actual_velocity_ms"],
            "nominal_size": p_lines["cooler_inlet"]["nominal_size_in"],
            "dir": "right",
            "color": "#dc2626",
            "status": "active",
        },
        "main_discharge": {
            "speed_factor": round(max(0.4, p_lines["mainline_outlet"]["actual_velocity_ms"] / 12.0), 2),
            "actual_velocity_ms": p_lines["mainline_outlet"]["actual_velocity_ms"],
            "nominal_size": p_lines["mainline_outlet"]["nominal_size_in"],
            "dir": "right",
            "color": "#10b981",
            "status": "active",
        },
    }

    return {
        "success": True,
        "station_summary": {
            "total_mass_flow_kgs": round(mass_flow_kgs, 2),
            "volumetric_flow_mmscmd": round(vol_flow_mmscmd, 2),
            "suction_pressure_bar": round(p_in, 2),
            "discharge_pressure_bar": round(p_out, 2),
            "pressure_ratio": round(p_out / p_in, 2),
            "total_power_kw": round(total_power_kw, 1),
            "total_power_mw": round(total_power_kw / 1000.0, 2),
            "cooler_heat_duty_mw": heat_duty_mw,
            "gas_mw": round(mw, 2),
            "suction_density_kgm3": round(rho_suction, 2),
            "mainline_pipe_size": p_lines["mainline_inlet"]["nominal_size_in"],
            "mainline_velocity_ms": p_lines["mainline_inlet"]["actual_velocity_ms"],
        },
        "equipment_sizing": {
            "cyclones": {
                "operating_count": cyclone_op_count,
                "installed_count": cyclone_total_count,
                "configuration": f"{cyclone_op_count} Çalışan + 1 Yedek",
                "flow_per_unit_kgs": round(flow_per_cyclone, 2),
                "pressure_drop_bar": dp_cyclone,
                "vessel_diameter_mm": 1200,
                "liquid_knockout_pct": 99.5,
                "inlet_pipe_size": p_lines["cyclone_branch"]["nominal_size_in"],
                "inlet_velocity_ms": p_lines["cyclone_branch"]["actual_velocity_ms"],
            },
            "cartridge_filters": {
                "operating_count": filter_op_count,
                "installed_count": filter_total_count,
                "configuration": f"{filter_op_count} Çalışan + 1 Yedek",
                "flow_per_unit_kgs": round(flow_per_filter, 2),
                "clean_dp_bar": dp_filter,
                "filter_efficiency_micron": "0.3 µm (%99.98)",
                "inlet_pipe_size": p_lines["filter_branch"]["nominal_size_in"],
                "inlet_velocity_ms": p_lines["filter_branch"]["actual_velocity_ms"],
            },
            "turbo_compressors": {
                "operating_count": comp_op_count,
                "installed_count": comp_total_count,
                "configuration": f"{comp_op_count} Çalışan + 1 Yedek ({comp_total_count} x %{round(100.0 / comp_op_count)})",
                "flow_per_unit_kgs": flow_per_comp,
                "power_per_unit_kw": power_per_unit_kw,
                "power_per_unit_hp": round(power_per_unit_kw * 1.34102, 1),
                "suction_nozzle_size_in": f"{p_lines['comp_suction_branch']['nominal_size_in']} (başlık {p_lines['comp_suction_header']['nominal_size_in']} - Note 32)",
                "discharge_nozzle_size_in": f"{p_lines['comp_discharge_branch']['nominal_size_in']} (başlık {p_lines['discharge_header']['nominal_size_in']} - Note 32)",
                "suction_velocity_ms": p_lines["comp_suction_branch"]["actual_velocity_ms"],
                "discharge_velocity_ms": p_lines["comp_discharge_branch"]["actual_velocity_ms"],
                "anti_surge_valve_size_in": int(p_lines["anti_surge_loop"]["nominal_key"]) if p_lines["anti_surge_loop"]["nominal_key"].isdigit() else asv_valve_size_in,
                "anti_surge_stroke_time_s": asv_stroke_time_s,
                "surge_limit_flow_kgs": surge_flow_limit,
                "anti_surge_valve_sizing": asv_sizing,
                "anti_surge_valve_warnings": asv_warnings,
            },
            "compressor_building": {
                "width_m": shelter_width_m,
                "length_m": shelter_length_m,
                "height_m": shelter_height_m,
                "area_m2": round(shelter_width_m * shelter_length_m, 1),
                "crane_capacity_tons": 15.0,
                "acoustic_attenuation_dba": "85 dBA @ 1m",
            },
            "air_coolers": {
                "bay_count": cooler_bays_count,
                "fans_per_bay": 2,
                "total_fans": cooler_bays_count * 2,
                "total_heat_duty_mw": heat_duty_mw,
                "inlet_temp_c": round(t_discharge_hot, 1),
                "outlet_temp_c": t_target_pipeline,
                "pressure_drop_bar": dp_cooler,
                "inlet_header_pipe_size": p_lines["cooler_inlet"]["nominal_size_in"],
                "riser_pipe_size": p_lines["cooler_bay_risers"]["nominal_size_in"],
                "outlet_pipe_size": p_lines["cooler_outlet"]["nominal_size_in"],
                "detailed_design": air_cooler_design,
                "design_warnings": air_cooler_warnings,
                "cooler_bypass_valve_sizing": tcv_sizing,
                "cooler_bypass_warnings": tcv_warnings,
                "bypass_line": {
                    "pipe_size": p_lines["cooler_bypass"]["nominal_size_in"],
                    "control_valve": "TCV Sıcaklık Kontrol Baypas Vanası (Note 17)",
                    "purpose": "VFD fan devir düşümüne rağmen aşırı soğuma durumunda sıcak gaz karışımı",
                },
            },
            "condensate_system": {
                "collection_tank_volume_m3": condensate_tank_volume_m3,
                "estimated_liquid_rate_m3h": liquid_condensate_rate_m3h,
                "source_drains": "Siklon Seperatör ve Kartuş Filtre LCV Seviye Kontrol Vanaları",
                "vent_protection": "Flame Arrester Emniyetli Atmosferik Vent Bacası (Note 14)",
            },
            "safety_relief_and_blowdown": {
                "psv_count": psv_count,
                "psv_set_pressure_bar": psv_set_pressure_bar,
                "relief_capacity_pct": 100.0,
                "bdv_valves_count": 2,
                "depressurization_time_min": bdv_depressurization_time_min,
                "flare_vent_stack_height_m": 35.0,
                "psv_sizing": psv_sizing,
                "psv_sizing_warnings": psv_sizing_warnings,
            },
            "pigging": {
                "mainline_nps": p_lines["mainline_inlet"]["nominal_size_in"],
                "receiver": pig_receiver_size,
                "launcher": pig_launcher_size,
                "signaller_type": "İntrusif Manyetik Pinger",
            },
            "station_recycle": {
                "pipe_size": p_lines["station_recycle"]["nominal_size_in"],
                "max_recirculation_capacity_kgs": station_recycle_capacity_kgs,
                "control_valve_type": "Kademeli Basınç Düşürücü Düşük Gürültülü Trim",
                "pcv_sizing": pcv_sizing,
                "pcv_warnings": pcv_warnings,
            },
        },
        "nodes": nodes,
        "pipe_flows": pipe_flows,
        "station_piping": station_piping,
    }
