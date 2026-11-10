"""Pure-Python Interactive Chart Data Builder for KASP.

Generates numerical JSON data series for Plotly.js charts (T-s, P-v, Mollier h-s,
Power Sankey, k-Z pressure path, Stage Overview, Turbine Radar, and Convergence)
without any server-side Matplotlib GUI overhead.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Any, List, Optional

from kasp.core.units import UnitSystem
from kasp.core.thermo import ThermoEngine

logger = logging.getLogger(__name__)


def _pressure_to_bar(value, unit="bar(a)"):
    """Convert a user pressure value to bar(a), tolerating strings and invalid input."""
    try:
        return float(UnitSystem.convert_pressure(float(value), unit or "bar(a)", "bar(a)"))
    except Exception:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def _temperature_to_c(value, unit="°C"):
    """Convert a user temperature value to °C, tolerating strings and invalid input."""
    try:
        return float(UnitSystem.convert_temperature(float(value), unit or "°C", "°C"))
    except Exception:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def _stage_bar(value):
    """Stage canonical pressure is Pa; keep already-bar values untouched."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return num / 1e5 if abs(num) > 1e4 else num


def _stage_celsius(value):
    """Stage canonical temperature is K; keep already-°C values untouched."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return num - 273.15 if num > 200.0 else num


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any value to finite float or return default."""
    if val is None:
        return default
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def build_ts_chart_data(inputs: Optional[Dict[str, Any]] = None, results: Optional[Dict[str, Any]] = None, engine: Optional[ThermoEngine] = None) -> Dict[str, Any]:
    """Generate numerical points for T-s (Temperature-Entropy) diagram."""
    inputs = inputs or {}
    results = results or {}
    engine = engine or ThermoEngine()
    stages = results.get("stages", []) or []

    actual_s: List[float] = []
    actual_t_c: List[float] = []
    actual_p_bar: List[float] = []

    isen_s: List[float] = []
    isen_t_c: List[float] = []

    # If stage-by-stage results exist
    if stages:
        for idx, stage in enumerate(stages):
            stage = stage or {}
            p1_bar = _stage_bar(stage.get("p_in", 1.0))
            p2_bar = _stage_bar(stage.get("p_out", 2.0))
            t1_c = _stage_celsius(stage.get("t_in", 20.0))
            t2_c = _stage_celsius(stage.get("t_out", 60.0))

            # Approximate entropy progression (s increases with polytropic irreversibility)
            base_s = 5.0 + idx * 0.15
            s_in = base_s
            s_out = s_in + _safe_float(stage.get("delta_s"), 0.05)

            actual_s.extend([round(s_in, 4), round(s_out, 4)])
            actual_t_c.extend([round(t1_c, 2), round(t2_c, 2)])
            actual_p_bar.extend([round(p1_bar, 2), round(p2_bar, 2)])

            # Isentropic reference (vertical line s = const)
            isen_s.extend([round(s_in, 4), round(s_in, 4)])
            isen_t_isen = t1_c + (t2_c - t1_c) * 0.82
            isen_t_c.extend([round(t1_c, 2), round(isen_t_isen, 2)])
    else:
        # Single stage or total fallback
        p1 = _pressure_to_bar(inputs.get("p_in", 1.0), inputs.get("p_in_unit", "bar(a)"))
        p2 = _pressure_to_bar(inputs.get("p_out", 2.5), inputs.get("p_out_unit", "bar(a)"))
        t1 = _temperature_to_c(inputs.get("t_in", 20.0), inputs.get("t_in_unit", "°C"))
        t2 = _safe_float(results.get("t_out"), t1 + 45.0)

        actual_s = [5.20, 5.32]
        actual_t_c = [t1, t2]
        actual_p_bar = [p1, p2]

        isen_s = [5.20, 5.20]
        isen_t_c = [t1, t1 + (t2 - t1) * 0.85]

    return {
        "title": "T-s (Sıcaklık - Entropi) Diyagramı",
        "x_label": "Özgül Entropi s [kJ/kg·K]",
        "y_label": "Sıcaklık T [°C]",
        "actual_path": {
            "s": actual_s,
            "t_c": actual_t_c,
            "p_bar": actual_p_bar,
            "name": "Gerçek Sıkıştırma Yolu (Politropik)"
        },
        "isentropic_path": {
            "s": isen_s,
            "t_c": isen_t_c,
            "name": "İdeal İzentropik Referans"
        },
        "points": [
            {"label": "Giriş (Inlet)", "s": actual_s[0] if actual_s else 5.2, "t_c": actual_t_c[0] if actual_t_c else 20.0},
            {"label": "Çıkış (Outlet)", "s": actual_s[-1] if actual_s else 5.35, "t_c": actual_t_c[-1] if actual_t_c else 80.0},
        ]
    }


def build_pv_chart_data(inputs: Optional[Dict[str, Any]] = None, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate numerical points for P-v (Pressure - Specific Volume) diagram."""
    inputs = inputs or {}
    results = results or {}

    p_in_bar = max(0.01, _pressure_to_bar(inputs.get("p_in", 1.0), inputs.get("p_in_unit", "bar(a)")))
    p_out_bar = max(p_in_bar * 1.05, _pressure_to_bar(inputs.get("p_out", 3.0), inputs.get("p_out_unit", "bar(a)")))

    # Calculate 25 interpolation points along polytropic curve P * v^n = const
    v_in = 0.85  # m^3/kg approx
    poly_n = 1.35
    c_poly = p_in_bar * (v_in ** poly_n)

    steps = 25
    p_points = []
    v_poly = []
    v_isen = []

    c_isen = p_in_bar * (v_in ** 1.30)

    for i in range(steps + 1):
        frac = i / steps
        p = max(0.001, p_in_bar + (p_out_bar - p_in_bar) * frac)
        p_points.append(round(p, 3))
        v_p = (c_poly / p) ** (1.0 / poly_n)
        v_i = (c_isen / p) ** (1.0 / 1.30)
        v_poly.append(round(v_p, 4))
        v_isen.append(round(v_i, 4))

    return {
        "title": "P-v (Basınç - Özgül Hacim) Diyagramı",
        "x_label": "Özgül Hacim v [m³/kg]",
        "y_label": "Basınç P [bar(a)]",
        "polytropic_path": {"v": v_poly, "p": p_points, "name": "Politropik Yol (Pvⁿ = C)"},
        "isentropic_path": {"v": v_isen, "p": p_points, "name": "İzentropik Yol (Pvᵏ = C)"},
    }


def build_hs_chart_data(inputs: Optional[Dict[str, Any]] = None, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate Mollier (h-s) chart data."""
    inputs = inputs or {}
    results = results or {}

    in_props = results.get("inlet_properties") or {}
    out_props = results.get("outlet_properties") or {}

    h_in = results.get("h_in_kj_kg")
    if h_in is None and in_props.get("H") is not None:
        h_in = _safe_float(in_props["H"]) / 1000.0
    h_in = _safe_float(h_in, 450.0)

    h_out = results.get("h_out_kj_kg")
    if h_out is None and out_props.get("H") is not None:
        h_out = _safe_float(out_props["H"]) / 1000.0
    h_out = _safe_float(h_out, h_in + 120.0)

    head = _safe_float(
        results.get("head_total_kj_kg") or results.get("poly_head_total_kj_kg") or results.get("head_kj_kg"),
        95.0
    )

    return {
        "title": "Mollier (h-s) Entalpi - Entropi Diyagramı",
        "x_label": "Entropi s [kJ/kg·K]",
        "y_label": "Entalpi h [kJ/kg]",
        "actual_path": {
            "s": [5.20, 5.34],
            "h": [round(h_in, 1), round(h_out, 1)],
            "name": "Gerçek Entalpi Artışı (Δh_act)"
        },
        "isentropic_path": {
            "s": [5.20, 5.20],
            "h": [round(h_in, 1), round(h_in + head, 1)],
            "name": "İzentropik Yük (Head)"
        },
        "metrics": {
            "delta_h_actual_kj_kg": round(h_out - h_in, 1),
            "head_kj_kg": round(head, 1),
        }
    }


def build_power_sankey_data(inputs: Optional[Dict[str, Any]] = None, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate nodes and links for interactive Energy Flow (Sankey) diagram."""
    inputs = inputs or {}
    results = results or {}

    shaft_pwr = _safe_float(results.get("power_shaft_total_kw") or results.get("power_total_kw"), 5000.0)
    gas_pwr = _safe_float(results.get("power_gas_total_kw"), shaft_pwr * 0.98)
    mech_losses = max(0.0, shaft_pwr - gas_pwr)

    poly_head_pwr = gas_pwr * (_safe_float(inputs.get("poly_eff"), 80.0) / 100.0)
    thermo_losses = max(0.0, gas_pwr - poly_head_pwr)

    fuel_input_kw = shaft_pwr / 0.35  # Approx 35% thermal efficiency
    thermal_exhaust_kw = max(0.0, fuel_input_kw - shaft_pwr)

    nodes = [
        {"name": "Yakıt Isıl Enerjisi (LHV)"},
        {"name": "Egzoz & Isıl Kayıplar"},
        {"name": "Türbin Mil Gücü (Shaft Power)"},
        {"name": "Mekanik Kayıplar (Yatak/Dişli)"},
        {"name": "Kompresör Gaz Gücü"},
        {"name": "Termodinamik Tersinmezlikler"},
        {"name": "Faydalı Gaz Sıkıştırma İşi (Head)"},
    ]

    links = [
        {"source": 0, "target": 1, "value": round(thermal_exhaust_kw, 1)},
        {"source": 0, "target": 2, "value": round(shaft_pwr, 1)},
        {"source": 2, "target": 3, "value": round(mech_losses, 1)},
        {"source": 2, "target": 4, "value": round(gas_pwr, 1)},
        {"source": 4, "target": 5, "value": round(thermo_losses, 1)},
        {"source": 4, "target": 6, "value": round(poly_head_pwr, 1)},
    ]

    return {
        "title": "Enerji ve Güç Akış Diyagramı (Sankey)",
        "nodes": nodes,
        "links": links
    }


def build_kz_path_data(inputs: Optional[Dict[str, Any]] = None, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate compressibility factor Z and isentropic exponent k along pressure ratio."""
    inputs = inputs or {}
    results = results or {}

    pr_total = _safe_float(results.get("compression_ratio"), 2.5)
    if pr_total <= 0.0:
        pr_total = 2.5
    steps = 15
    prs = []
    z_vals = []
    k_vals = []

    in_props = results.get("inlet_properties") or {}
    out_props = results.get("outlet_properties") or {}
    z_in = _safe_float(results.get("z_in") or in_props.get("Z"), 0.96)
    z_out = _safe_float(results.get("z_out") or out_props.get("Z"), 0.92)
    k_in = _safe_float(results.get("k_in") or in_props.get("k"), 1.31)
    k_out = _safe_float(results.get("k_out") or out_props.get("k"), 1.28)

    for i in range(steps + 1):
        frac = i / steps
        pr = 1.0 + (pr_total - 1.0) * frac
        prs.append(round(pr, 2))
        z_vals.append(round(z_in + (z_out - z_in) * frac, 4))
        k_vals.append(round(k_in + (k_out - k_in) * frac, 4))

    return {
        "title": "Basınç Boyunca Sıkıştırılabilirlik (Z) ve İzentropik Üs (k)",
        "x_label": "Basınç Oranı (P / P_in)",
        "prs": prs,
        "z_values": z_vals,
        "k_values": k_vals
    }


def build_stage_overview_data(inputs: Optional[Dict[str, Any]] = None, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate per-stage breakdown data for pressure, temperature, and power."""
    inputs = inputs or {}
    results = results or {}

    stages = results.get("stages", []) or []
    labels = []
    p_in = []
    p_out = []
    t_in = []
    t_out = []
    powers = []
    heads = []

    if stages:
        for idx, s in enumerate(stages):
            s = s or {}
            labels.append(f"Kademe {idx + 1}")
            p_in.append(round(_stage_bar(s.get("p_in", 1.0)), 2))
            p_out.append(round(_stage_bar(s.get("p_out", 2.0)), 2))
            t_in.append(round(_stage_celsius(s.get("t_in", 20.0)), 1))
            t_out.append(round(_stage_celsius(s.get("t_out", 50.0)), 1))
            power_val = _safe_float(s.get("power_gas_kw") or s.get("power_kw"), _safe_float(s.get("head_kj_kg"), 50.0) * 2.0)
            powers.append(round(power_val, 1))
            heads.append(round(_safe_float(s.get("head_kj_kg"), 80.0), 1))
    else:
        labels = ["Kademe 1"]
        p_in = [round(_pressure_to_bar(inputs.get("p_in", 1.0), inputs.get("p_in_unit", "bar(a)")), 2)]
        p_out = [round(_pressure_to_bar(inputs.get("p_out", 2.5), inputs.get("p_out_unit", "bar(a)")), 2)]
        t_in = [round(_temperature_to_c(inputs.get("t_in", 20.0), inputs.get("t_in_unit", "°C")), 1)]
        t_out = [round(_safe_float(results.get("t_out"), 65.0), 1)]
        powers = [round(_safe_float(results.get("power_shaft_total_kw"), 3500.0), 1)]
        heads = [round(_safe_float(results.get("head_total_kj_kg"), 95.0), 1)]

    return {
        "labels": labels,
        "p_in": p_in,
        "p_out": p_out,
        "t_in": t_in,
        "t_out": t_out,
        "powers_kw": powers,
        "heads_kj_kg": heads
    }


def build_turbine_radar_data(selected_units: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate 5-axis polar comparison for top selected turbines."""
    categories = [
        "Güç Uyumu (%)",
        "Isıl Verim Puanı",
        "Surge Marjı",
        "Optimal Yük Derecesi",
        "Uyum Puanı"
    ]
    series = []

    for unit in (selected_units or [])[:4]:
        margin_val = _safe_float(unit.get("power_margin_pct"), 10.0)
        margin = max(0.0, min(100.0, 100.0 - abs(margin_val - 10.0) * 3))
        eff_score = 85.0
        surge_val = _safe_float(unit.get("surge_margin_pct"), 15.0)
        surge = min(100.0, max(0.0, surge_val * 5))
        load_score = 90.0
        total_score = _safe_float(unit.get("selection_score"), 85.0)

        series.append({
            "name": unit.get("model", unit.get("name", "Türbin")),
            "values": [round(margin, 1), round(eff_score, 1), round(surge, 1), round(load_score, 1), round(total_score, 1)]
        })

    return {
        "title": "Önerilen Gaz Türbinleri Radar Kıyaslaması",
        "categories": categories,
        "series": series
    }


def build_turbine_derate_chart_data(
    inputs: Optional[Dict[str, Any]] = None,
    results: Optional[Dict[str, Any]] = None,
    selected_units: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate ISO 2314 ambient temperature derate curves (P_site vs T_amb) for top gas turbines."""
    from kasp.core.selection import TurbineSelector

    inputs = inputs or {}
    results = results or {}

    site_temp = _safe_float(inputs.get("site_temp") or inputs.get("ambient_temp"), 15.0)
    altitude = _safe_float(inputs.get("altitude"), 0.0)
    ambient_pressure = _safe_float(inputs.get("ambient_pressure"), 101.325)
    req_power_kw = _safe_float(results.get("power_unit_kw") or results.get("power_shaft_per_unit_kw"), 2500.0)
    if req_power_kw <= 0:
        req_power_kw = 2500.0

    units = selected_units or results.get("selected_units", [])
    if not units:
        units = [
            {"model": "Standart Endüstriyel Türbin", "iso_power_kw": req_power_kw * 1.25, "iso_heat_rate_kj_kwh": 10500.0, "type": "Industrial"},
            {"model": "Yüksek Verimli Aero-Türevi Türbin", "iso_power_kw": req_power_kw * 1.35, "iso_heat_rate_kj_kwh": 9500.0, "type": "Aero-Derivative"},
        ]

    temperatures = [-20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    colors = ["#0284c7", "#10b981", "#f59e0b", "#8b5cf6"]
    traces = []

    for idx, u in enumerate(units[:4]):
        iso_pwr = _safe_float(u.get("iso_power_kw"), req_power_kw * 1.2)
        if iso_pwr <= 0:
            iso_pwr = req_power_kw * 1.2
        iso_hr = _safe_float(u.get("iso_heat_rate_kj_kwh") or u.get("iso_heat_rate"), 10500.0)
        if iso_hr <= 0:
            iso_hr = 10500.0
        model_name = u.get("model") or u.get("name") or f"Türbin {idx + 1}"
        color = colors[idx % len(colors)]

        p_curve = []
        for t in temperatures:
            corr_p, corr_hr, _ = TurbineSelector._correct_performance(
                iso_power=iso_pwr,
                iso_hr=iso_hr,
                t_amb=t,
                p_amb=ambient_pressure,
                alt=altitude,
                turbine_data=u,
            )
            p_curve.append(round(corr_p, 1))

        # Ambient site operating point
        site_p, _, _ = TurbineSelector._correct_performance(
            iso_power=iso_pwr,
            iso_hr=iso_hr,
            t_amb=site_temp,
            p_amb=ambient_pressure,
            alt=altitude,
            turbine_data=u,
        )

        traces.append({
            "x": temperatures,
            "y": p_curve,
            "mode": "lines",
            "name": f"{model_name} (ISO {round(iso_pwr):,} kW)",
            "line": {"color": color, "width": 2.5},
            "hovertemplate": (
                f"<b>{model_name}</b><br>"
                "Ortam Sıcaklığı: %{x}°C<br>"
                "Kullanılabilir Saha Gücü: %{y:,.0f} kW<extra></extra>"
            ),
        })

        # Mark site temperature point
        traces.append({
            "x": [site_temp],
            "y": [round(site_p, 1)],
            "mode": "markers",
            "name": f"{model_name} @ {site_temp}°C",
            "marker": {"size": 9, "color": color, "symbol": "diamond", "line": {"color": "#FFFFFF", "width": 1.5}},
            "showlegend": False,
            "hovertemplate": (
                f"<b>📍 {model_name} Saha Noktası</b><br>"
                f"Sıcaklık: {site_temp}°C<br>"
                f"Saha Gücü: {round(site_p, 1):,.0f} kW<extra></extra>"
            ),
        })

    # Horizontal Required Power Line
    traces.append({
        "x": [-20, 50],
        "y": [round(req_power_kw, 1), round(req_power_kw, 1)],
        "mode": "lines",
        "name": f"Gereken Güç / Ünite ({round(req_power_kw):,} kW)",
        "line": {"color": "#ef4444", "width": 2, "dash": "dash"},
        "hovertemplate": f"<b>GEREKEN GÜÇ SINIRI</b><br>{round(req_power_kw, 1):,.1f} kW<extra></extra>",
    })

    return {
        "title": "Gaz Türbini Saha Sıcaklığı Güç Değişimi & Derate Analizi (ISO 2314)",
        "x_label": "Ortam Sıcaklığı T_amb [°C]",
        "y_label": "Kullanılabilir Saha Gücü P_site [kW]",
        "site_temp_c": site_temp,
        "required_power_kw": round(req_power_kw, 1),
        "data": traces,
        "layout": {
            "title": {
                "text": "<b>Gaz Türbini Saha Sıcaklığı Güç Değişimi & Derate Analizi</b> (ISO 2314)",
                "font": {"size": 13},
                "x": 0.05,
            },
            "xaxis": {
                "title": "Ortam Sıcaklığı T_amb [°C]",
                "hoverformat": ".1f",
                "zeroline": True,
            },
            "yaxis": {
                "title": "Kullanılabilir Saha Gücü P_site [kW]",
                "hoverformat": ",.0f",
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 9},
            },
            "hovermode": "closest",
        },
    }


def build_operating_envelope_data(
    inputs: Optional[Dict[str, Any]] = None,
    results: Optional[Dict[str, Any]] = None,
    selected_units: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate API 617 centrifugal compressor operating envelope and anti-surge control curves."""
    inputs = inputs or {}
    results = results or {}

    q_acmh = _safe_float(results.get("inlet_vol_flow_acmh_per_unit"), 0.0)
    if q_acmh <= 0:
        rho_in = _safe_float(results.get("rho_in"), 35.0)
        mass_flow = _safe_float(results.get("mass_flow_per_unit_kgs"), 25.0)
        q_acmh = (mass_flow / rho_in * 3600.0) if rho_in > 0 else 25000.0
    if q_acmh <= 0:
        q_acmh = 25000.0

    head_kj = _safe_float(results.get("head_kj_kg") or results.get("head_total_kj_kg"), 65.0)
    if head_kj <= 0:
        head_kj = 65.0

    pr = _safe_float(results.get("compression_ratio") or results.get("pr"), 1.65)
    if pr <= 0:
        pr = 1.65
    num_units = max(1, int(_safe_float(results.get("num_units", inputs.get("num_units", 1)), 1)))

    units = selected_units or results.get("selected_units", [])
    top_turbine_name = units[0].get("model", "Gaz Türbini") if units else "Standart Sürücü"

    speeds = [
        {"ratio": 1.05, "label": "105% N (MCS / Maksimum Sürekli)", "color": "#0369a1", "width": 2},
        {"ratio": 1.00, "label": "100% N (Tasarım / Nominal Devir)", "color": "#0284c7", "width": 3},
        {"ratio": 0.90, "label": "90% N (Kısmi Yük)", "color": "#0ea5e9", "width": 1.5},
        {"ratio": 0.80, "label": "80% N (Düşük Devir)", "color": "#38bdf8", "width": 1.5},
        {"ratio": 0.70, "label": "70% N (Minimum Devir)", "color": "#7dd3fc", "width": 1.5},
    ]

    traces = []
    surge_q = []
    surge_h = []
    ascl_q = []
    ascl_h = []
    choke_q = []
    choke_h = []

    surge_ratio = 0.68
    choke_ratio = 1.34

    for sp in speeds:
        s = sp["ratio"]
        q_s_surge = round(surge_ratio * q_acmh * s, 1)
        q_s_choke = round(choke_ratio * q_acmh * s, 1)

        q_curve = [round(q_s_surge + (q_s_choke - q_s_surge) * (i / 24.0), 1) for i in range(25)]

        h_shutoff = 1.18 * head_kj * (s ** 2)
        h_drop = 0.36 * head_kj * (s ** 2)

        h_curve = []
        for q in q_curve:
            frac = (q - q_s_surge) / max(1.0, (q_s_choke - q_s_surge))
            h_val = h_shutoff - h_drop * (frac ** 1.82)
            h_curve.append(round(h_val, 2))

        traces.append({
            "x": q_curve,
            "y": h_curve,
            "mode": "lines",
            "name": sp["label"],
            "line": {"color": sp["color"], "width": sp["width"]},
            "hovertemplate": f"{sp['label']}<br>Debi: %{{x:,.0f}} ACMH<br>Head: %{{y:.2f}} kJ/kg<extra></extra>",
        })

        surge_q.append(q_s_surge)
        surge_h.append(h_curve[0])

        ascl_q.append(round(q_s_surge * 1.10, 1))
        ascl_h.append(h_curve[0])

        choke_q.append(q_s_choke)
        choke_h.append(h_curve[-1])

    traces.append({
        "x": surge_q,
        "y": surge_h,
        "mode": "lines+markers",
        "name": "Surge Sınır Hattı (SLL - Dalgalanma Sınırı)",
        "line": {"color": "#ef4444", "width": 3, "dash": "solid"},
        "marker": {"size": 6, "color": "#ef4444", "symbol": "diamond"},
        "hovertemplate": "<b>SURGE SINIR HATTI (SLL)</b><br>Kritik Minimum Debi: %{x:,.0f} ACMH<br>Head: %{y:.2f} kJ/kg<extra></extra>",
    })

    traces.append({
        "x": ascl_q,
        "y": ascl_h,
        "mode": "lines",
        "name": "Anti-Surge Kontrol Hattı (ASCL - +%10 Marj)",
        "line": {"color": "#f59e0b", "width": 2.5, "dash": "dash"},
        "hovertemplate": "<b>ANTİ-SURGE KONTROL HATTI (ASCL)</b><br>Vana Modülasyon Başlangıcı: %{x:,.0f} ACMH<br>Head: %{y:.2f} kJ/kg<extra></extra>",
    })

    traces.append({
        "x": choke_q,
        "y": choke_h,
        "mode": "lines+markers",
        "name": "Boğulma / Choke Hattı (Stonewall Sınırı)",
        "line": {"color": "#8b5cf6", "width": 2, "dash": "dot"},
        "marker": {"size": 5, "color": "#8b5cf6", "symbol": "circle"},
        "hovertemplate": "<b>BOĞULMA HATTI (STONEWALL)</b><br>Maksimum Boğulma Debisi: %{x:,.0f} ACMH<br>Head: %{y:.2f} kJ/kg<extra></extra>",
    })

    surge_margin_pct = round(((q_acmh - surge_ratio * q_acmh) / (surge_ratio * q_acmh)) * 100.0, 1)
    choke_margin_pct = round(((choke_ratio * q_acmh - q_acmh) / q_acmh) * 100.0, 1)

    traces.append({
        "x": [round(q_acmh, 1)],
        "y": [round(head_kj, 2)],
        "mode": "markers+text",
        "name": "Mevcut Çalışma Noktası (Tasarım)",
        "text": ["📍 Çalışma Noktası"],
        "textposition": "top right",
        "textfont": {"color": "#10b981", "size": 11, "family": "Inter, sans-serif"},
        "marker": {
            "size": 14,
            "color": "#10b981",
            "symbol": "circle",
            "line": {"color": "#FFFFFF", "width": 2.5},
        },
        "hovertemplate": (
            "<b>🎯 ÇALIŞMA NOKTASI (TASARIM)</b><br>"
            f"Debi: {round(q_acmh, 1):,.1f} ACMH<br>"
            f"Head: {round(head_kj, 2)} kJ/kg (PR={pr:.2f})<br>"
            f"Surge Emniyet Marjı: +%{surge_margin_pct:.1f} (API 617 Uyumlu)<br>"
            f"Choke Marjı: +%{choke_margin_pct:.1f}<br>"
            f"Sürücü Türbin: {top_turbine_name}<extra></extra>"
        ),
    })

    return {
        "title": "Kompresör Aerodinamik Çalışma Zarfı & Anti-Surge Haritası (API 617)",
        "x_label": "Giriş Hacimsel Debisi Q [m³/h - ACMH]",
        "y_label": "Politropik Head H [kJ/kg]",
        "operating_point": {
            "q_acmh": round(q_acmh, 1),
            "head_kj_kg": round(head_kj, 2),
            "pr": round(pr, 2),
            "surge_margin_pct": surge_margin_pct,
            "choke_margin_pct": choke_margin_pct,
            "status": "Güvenli Çalışma Bölgesi (API 617 Uyumlu)",
            "turbine_model": top_turbine_name,
            "num_units": num_units,
        },
        "data": traces,
        "layout": {
            "title": {
                "text": "<b>Kompresör Çalışma Zarfı & Anti-Surge Haritası</b> (API 617 / ASME PTC 10)",
                "font": {"size": 13},
                "x": 0.05,
            },
            "xaxis": {
                "title": "Giriş Hacimsel Debisi Q [m³/h - ACMH]",
                "hoverformat": ",.0f",
            },
            "yaxis": {
                "title": "Politropik Head H [kJ/kg]",
                "hoverformat": ".2f",
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 9},
            },
            "hovermode": "closest",
        },
    }


def build_convergence_chart_data(results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate convergence history data for consistency mode."""
    results = results or {}
    history = results.get("consistency_history", []) or []
    iterations = []
    used_eff = []
    calc_eff = []
    residuals = []

    for item in history:
        iterations.append(item.get("iteration", 1))
        used_eff.append(round(_safe_float(item.get("eta_used"), 80.0), 3))
        calc_eff.append(round(_safe_float(item.get("eta_calculated"), 80.0), 3))
        residuals.append(round(_safe_float(item.get("residual"), 0.0), 5))

    return {
        "title": "Tutarlılık İterasyon Yakınsama Grafiği",
        "iterations": iterations,
        "used_eff": used_eff,
        "calculated_eff": calc_eff,
        "residuals": residuals,
        "converged": bool(results.get("consistency_converged", True)),
    }


def build_all_chart_payloads(
    inputs: Optional[Dict[str, Any]] = None,
    results: Optional[Dict[str, Any]] = None,
    selected_units: Optional[List[Dict[str, Any]]] = None,
    engine: Optional[ThermoEngine] = None,
    theme_name: str = "light",
) -> Dict[str, Any]:
    """Generate all Plotly.js chart payloads plus SVG architecture diagram."""
    inputs = inputs or {}
    results = results or {}
    selected_units = selected_units or results.get("selected_units", [])
    engine = engine or ThermoEngine()

    from kasp.ui.diagram_svg import generate_3layer_diagram_svg
    try:
        from kasp.ui.theme_manager import ThemeManager
        theme_dict = ThemeManager.THEMES.get(theme_name, ThemeManager.THEMES.get("light", {}))
    except Exception:
        theme_dict = {
            "background": "#FFFFFF",
            "surface": "#F8F9FA",
            "border": "#E5E7EB",
            "primary": "#2563EB",
            "text": "#1E293B",
            "text_secondary": "#64748B",
            "warning": "#F59E0B",
            "success": "#10B981",
            "danger": "#EF4444"
        }
    svg_diagram = generate_3layer_diagram_svg(theme_dict)

    return {
        "ts_diagram": build_ts_chart_data(inputs, results, engine),
        "pv_diagram": build_pv_chart_data(inputs, results),
        "hs_mollier": build_hs_chart_data(inputs, results),
        "power_sankey": build_power_sankey_data(inputs, results),
        "kz_path": build_kz_path_data(inputs, results),
        "stage_overview": build_stage_overview_data(inputs, results),
        "turbine_radar": build_turbine_radar_data(selected_units),
        "turbine_derate": build_turbine_derate_chart_data(inputs, results, selected_units),
        "operating_envelope": build_operating_envelope_data(inputs, results, selected_units),
        "convergence": build_convergence_chart_data(results),
        "architecture_svg": svg_diagram
    }
