"""Excel/JSON module report builder for KASP integration results."""

from __future__ import annotations

import datetime
from io import BytesIO
from typing import Any, Dict, Iterable, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(size=14, bold=True, color="1F4E78")
THIN = Side(style="thin", color="B0B7C3")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(_safe(v)) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}={_safe(v)}" for k, v in value.items())
    return str(value)


def _module_results(modules: Dict[str, Any], module_id: str) -> Dict[str, Any]:
    module = (modules or {}).get(module_id) or {}
    if isinstance(module, dict):
        return module.get("results") or {}
    return {}


def _write_kv(ws, title: str, rows: Iterable[Iterable[Any]]):
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:B1")
    row_idx = 3
    for row in rows:
        values = list(row)
        for col_idx, value in enumerate(values[:2], start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=_safe(value))
            cell.border = BORDER
            if col_idx == 1:
                cell.font = Font(bold=True)
        row_idx += 1
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 58
    ws.freeze_panes = "A4"


def _write_table(ws, title: str, headers: List[str], rows: Iterable[Iterable[Any]]):
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=idx, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    row_idx = 4
    for row in rows:
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=_safe(value))
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        row_idx += 1
    for idx, header in enumerate(headers, start=1):
        width = max(14, min(42, len(str(header)) + 8))
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A4"


def build_module_workbook(
    inputs: Dict[str, Any],
    results: Dict[str, Any] | None,
    modules: Dict[str, Any] | None,
    station_data: Dict[str, Any] | None,
    selected_units: List[Dict[str, Any]] | None = None,
    warnings: List[Any] | None = None,
) -> BytesIO:
    """Build a multi-sheet XLSX workbook with design, turbine, module and station results."""
    modules = modules or {}
    results = results or {}
    station_data = station_data or {}
    turbine_rows = (
        selected_units
        if selected_units is not None
        else (results.get("selected_units") if isinstance(results.get("selected_units"), list) else [])
    ) or []
    wb = Workbook()

    # 1. Summary
    ws = wb.active
    ws.title = "Özet"
    summary_rows = [
        ("Proje Adı", inputs.get("project_name", "-")),
        ("Rapor Tarihi", datetime.datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("EOS", inputs.get("eos_model") or inputs.get("eos_method", "-")),
        ("Hesaplama Metodu", inputs.get("calc_method") or inputs.get("method", "-")),
        ("Ortam Sıcaklığı (°C)", inputs.get("ambient_temp", inputs.get("t_amb", "-"))),
        ("Rakım (m)", inputs.get("altitude", 0)),
        ("Türbin Isıl Verimi (%)", results.get("driver_thermal_efficiency_pct") or inputs.get("therm_eff", "-")),
        ("Modüller", ", ".join(sorted(modules.keys())) if modules else "-"),
        ("İstasyon Modeli", "Var" if station_data else "Yok"),
    ]
    if results:
        summary_rows.extend([
            ("Mil Gücü / Ünite (kW)", results.get("power_shaft_per_unit_kw")),
            ("Sürücü Gücü API 617 / Ünite (kW)", results.get("power_unit_kw")),
            ("Yakıt Tüketimi / Ünite (kg/h)", results.get("fuel_unit_kgh")),
            ("Isı Tüketim Oranı - Heat Rate (kJ/kWh)", results.get("heat_rate")),
        ])
    _write_kv(ws, "KASP Entegrasyon Raporu", summary_rows)

    # 1B. Design Thermodynamics & Stage Breakdown
    if results:
        ws = wb.create_sheet("Tasarım")
        poly_eff_val = results.get("actual_poly_efficiency")
        if isinstance(poly_eff_val, (int, float)) and 0 < poly_eff_val <= 1.0:
            poly_eff_val = round(poly_eff_val * 100.0, 2)
        design_kv = [
            ("Giriş Basıncı", f"{inputs.get('p_in', '-')} {inputs.get('p_in_unit', 'bar(a)')}"),
            ("Çıkış Basıncı", f"{inputs.get('p_out', '-')} {inputs.get('p_out_unit', 'bar(a)')}"),
            ("Giriş Sıcaklığı", f"{inputs.get('t_in', '-')} {inputs.get('t_in_unit', '°C')}"),
            ("Çıkış Sıcaklığı (°C)", results.get("t_out")),
            ("Sıkıştırma Oranı (PR)", results.get("compression_ratio")),
            ("Politropik Yük - Head (kJ/kg)", results.get("head_kj_kg")),
            ("Gerçek Politropik Verim (%)", poly_eff_val),
            ("Gaz Gücü / Ünite (kW)", results.get("power_gas_per_unit_kw")),
            ("Mil Gücü / Ünite (kW)", results.get("power_shaft_per_unit_kw")),
            ("Kaplin Gücü / Ünite (kW)", results.get("power_motor_per_unit_kw")),
            ("API 617 Sürücü Gücü / Ünite (kW)", results.get("power_unit_kw")),
            ("İstasyon Toplam Sürücü Gücü (kW)", results.get("power_unit_total_kw")),
            ("Sürücü Isıl Verimi (%)", results.get("driver_thermal_efficiency_pct") or inputs.get("therm_eff")),
            ("Heat Rate (kJ/kWh)", results.get("heat_rate")),
            ("Alt Isıl Değer - LHV (kJ/kg)", results.get("lhv")),
            ("Yakıt Tüketimi / Ünite (kg/h)", results.get("fuel_unit_kgh")),
            ("İstasyon Toplam Yakıt (kg/h)", results.get("fuel_total_kgh")),
        ]
        _write_kv(ws, "Kompresör Tasarım ve Yakıt Özeti", design_kv)

        stages = results.get("stages") or []
        if isinstance(stages, list) and stages:
            start_row = 4 + len(design_kv) + 1
            stage_headers = [
                "Kademe",
                "P_in (bar a)",
                "P_out (bar a)",
                "T_in (°C)",
                "T_out (°C)",
                "Head (kJ/kg)",
                "Güç (kW)",
                "Politropik Verim (%)",
            ]
            for col_idx, header in enumerate(stage_headers, start=1):
                cell = ws.cell(row=start_row, column=col_idx, value=header)
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = BORDER
                ws.column_dimensions[get_column_letter(col_idx)].width = max(
                    ws.column_dimensions[get_column_letter(col_idx)].width or 14,
                    18,
                )
            for offset, stg in enumerate(stages, start=1):
                if not isinstance(stg, dict):
                    continue
                stg_eff = stg.get("actual_poly_eff", stg.get("poly_eff"))
                if isinstance(stg_eff, (int, float)) and 0 < stg_eff <= 1.0:
                    stg_eff = round(stg_eff * 100.0, 2)
                row_vals = [
                    stg.get("stage", offset),
                    stg.get("p_in_bar", stg.get("p_in")),
                    stg.get("p_out_bar", stg.get("p_out")),
                    stg.get("t_in_c", stg.get("t_in")),
                    stg.get("t_out_c", stg.get("t_out")),
                    stg.get("head_kj_kg"),
                    stg.get("power_kw", stg.get("power_gas_kw")),
                    stg_eff,
                ]
                for col_idx, val in enumerate(row_vals, start=1):
                    c = ws.cell(row=start_row + offset, column=col_idx, value=_safe(val))
                    c.border = BORDER

    # 1C. Matched ISO 2314 Turbines
    if turbine_rows:
        ws = wb.create_sheet("Türbinler")
        t_headers = [
            "Model",
            "Üretici",
            "Tip",
            "Saha Gücü (kW)",
            "ISO Gücü (kW)",
            "Saha Heat Rate (kJ/kWh)",
            "Saha Isıl Verim (%)",
            "Güç Marjı (%)",
            "Seçim Skoru",
        ]
        t_data = []
        for u in turbine_rows:
            if not isinstance(u, dict):
                continue
            s_hr = u.get("site_heat_rate_kj_kwh") or u.get("site_heat_rate")
            s_eff = u.get("site_thermal_efficiency_pct")
            if s_eff is None and isinstance(s_hr, (int, float)) and s_hr > 0:
                s_eff = round(360000.0 / float(s_hr), 2)
            t_data.append([
                u.get("model") or u.get("name"),
                u.get("manufacturer", "Genel"),
                u.get("type", "Industrial"),
                u.get("site_power_kw") or u.get("available_power_kw"),
                u.get("iso_power_kw"),
                s_hr,
                s_eff,
                u.get("power_margin_pct"),
                u.get("selection_score"),
            ])
        _write_table(ws, "Eşleşen Gaz Türbinleri (ISO 2314 Saha Düzeltmeli)", t_headers, t_data)

    # 2. PSV
    psv = _module_results(modules, "psv")
    if not psv:
        psv = ((station_data.get("equipment_sizing") or {}).get("safety_relief_and_blowdown") or {}).get("psv_sizing") or {}
    if psv:
        ws = wb.create_sheet("PSV")
        _write_kv(ws, "API 520/521 PSV Ön Boyutlandırma", [
            ("Gerekli Orifis Alanı (in²)", psv.get("Required_Area_sqin") or psv.get("required_area_sqin")),
            ("Seçilen Orifis", psv.get("Selected_Orifice_Letter") or psv.get("selected_orifice")),
            ("Seçilen Orifis Alanı (in²)", psv.get("Selected_Orifice_Area_sqin") or psv.get("selected_orifice_area_sqin")),
            ("Orifis Yükü (%)", psv.get("Orifice_Loading_Pct") or psv.get("orifice_loading_pct")),
            ("Akış Tipi", psv.get("Flow_Type") or psv.get("flow_type")),
            ("Standart", ((modules.get("psv") or {}).get("provenance") or {}).get("standard")),
        ])

    # 3. API 5L
    api5l = (_module_results(modules, "api5l").get("recommendation") or {})
    if api5l:
        ws = wb.create_sheet("API5L")
        _write_kv(ws, "API 5L / BOTAŞ Boru Et Kalınlığı", [
            ("Nominal Çap", api5l.get("nominal_size_in")),
            ("Malzeme", api5l.get("material_grade")),
            ("Standart / PSL", f"{api5l.get('standard')} / {api5l.get('psl_level')}"),
            ("Lokasyon", api5l.get("location_type")),
            ("Gerekli Et Kalınlığı (mm)", api5l.get("required_thickness_mm")),
            ("Seçilen Nominal (mm)", api5l.get("selected_nominal_thickness_mm")),
            ("BOTAŞ Standart (mm)", api5l.get("botas_standard_thickness_mm")),
            ("Tolerans Kuralı", api5l.get("tolerance_rule")),
            ("Uygunluk", api5l.get("is_sufficient")),
        ])

    # 4. Hydraulics
    hyd = (_module_results(modules, "pipe_hydraulics").get("recommendation") or {})
    if hyd:
        ws = wb.create_sheet("Hidrolik")
        _write_kv(ws, "ASME B36.10M / API RP 14E Hat Hidroliği", [
            ("Seçilen Çap", hyd.get("nominal_size_in")),
            ("Schedule", hyd.get("schedule")),
            ("Gaz Hızı (m/s)", hyd.get("velocity_ms")),
            ("Erozyon Oranı (%)", hyd.get("erosion_ratio_pct")),
            ("Toplam ΔP (bar)", hyd.get("pressure_drop_bar_total")),
            ("Çıkış Basıncı (bar)", hyd.get("outlet_pressure_bar")),
            ("Durum", hyd.get("velocity_status")),
        ])

    # 5. Air cooler
    cooler = _module_results(modules, "air_cooler")
    if not cooler:
        cooler = ((station_data.get("equipment_sizing") or {}).get("air_coolers") or {}).get("detailed_design") or {}
    if cooler:
        ws = wb.create_sheet("AirCooler")
        _write_kv(ws, "API 661 Fin-Fan Hava Soğutucu", [
            ("Isıl Yük (kW)", cooler.get("heat_duty_kw") or cooler.get("Q_kW")),
            ("Gerekli Alan (m²)", cooler.get("required_area_m2")),
            ("Gerçek Alan (m²)", cooler.get("actual_area_m2")),
            ("Overdesign (%)", cooler.get("overdesign_pct")),
            ("Gaz ΔP (bar)", cooler.get("gas_pressure_drop_bar") or cooler.get("gas_dP_bar")),
            ("Fan Gücü (kW)", cooler.get("fan_power_kw") or cooler.get("fan_power_kW")),
            ("Fan Uç Hızı (m/s)", cooler.get("fan_tip_speed_ms") or cooler.get("fan_tip_speed_m_s")),
            ("Geometri", cooler.get("geometry")),
        ])

    # 6. Control valve
    valve = _module_results(modules, "control_valve")
    if not valve:
        eq = station_data.get("equipment_sizing") or {}
        valve = (
            ((eq.get("turbo_compressors") or {}).get("anti_surge_valve_sizing"))
            or ((eq.get("station_recycle") or {}).get("pcv_sizing"))
            or ((eq.get("air_coolers") or {}).get("cooler_bypass_valve_sizing"))
            or {}
        )
    if valve:
        ws = wb.create_sheet("KontrolVanasi")
        _write_kv(ws, "IEC 60534 Kontrol Vanası", [
            ("Servis / Hat", f"{valve.get('service')} / {valve.get('path')}"),
            ("Gerekli Cv", valve.get("required_cv")),
            ("Gerekli Kv", valve.get("required_kv")),
            ("Seçilen Vana", f"{valve.get('valve_inch')} (DN{valve.get('valve_dn_mm')})"),
            ("Açıklık (%)", valve.get("opening_percent")),
            ("Choked", valve.get("is_choked")),
            ("Gürültü (dB)", valve.get("noise_db")),
            ("Uyarı", valve.get("warning")),
        ])

    # 7. Station summary
    if station_data:
        ws = wb.create_sheet("Istasyon")
        sm = station_data.get("station_summary") or {}
        eq = station_data.get("equipment_sizing") or {}
        _write_kv(ws, "Kompresör İstasyonu Özeti", [
            ("Toplam Debi (kg/s)", sm.get("total_mass_flow_kgs")),
            ("Basınç Oranı", sm.get("pressure_ratio")),
            ("Toplam Güç (MW)", sm.get("total_power_mw")),
            ("Soğutucu Isıl Yükü (MWth)", sm.get("cooler_heat_duty_mw")),
            ("Boru Standardı", f"{station_data.get('station_piping', {}).get('pipe_standard')} / {station_data.get('station_piping', {}).get('psl_level')}"),
            ("Siklon / Filtre", f"{eq.get('cyclones', {}).get('configuration')} / {eq.get('cartridge_filters', {}).get('configuration')}"),
            ("Kompresör", eq.get("turbo_compressors", {}).get("configuration")),
            ("Hava Soğutucu Bay", eq.get("air_coolers", {}).get("bay_count")),
        ])

        lines = ((station_data.get("station_piping") or {}).get("lines") or {})
        if lines:
            ws = wb.create_sheet("BoruHatları")
            headers = ["Hat No", "Tanım", "Debi (kg/s)", "Basınç (bar a)", "NPS", "Schedule", "t_req (mm)", "t_seçilen (mm)", "Standart t_min (mm)", "Standart", "Hız (m/s)", "EVR (%)", "ΔP/100m (bar)", "Durum"]
            rows = []
            for line in lines.values():
                std = line.get("standard_recommendation") or {}
                rows.append([
                    line.get("tag"), line.get("name"), line.get("flow_kgs"), line.get("pressure_bar"),
                    line.get("nominal_size_in"), line.get("schedule"), line.get("min_required_thickness_mm"),
                    line.get("wall_thickness_mm"), std.get("minimum_standard_thickness_mm"),
                    f"{std.get('standard', '-')} {std.get('psl_level', '')}".strip(),
                    line.get("actual_velocity_ms"), line.get("erosion_ratio_pct"),
                    line.get("pressure_drop_bar_per_100m"), line.get("velocity_status"),
                ])
            _write_table(ws, "15 Proses Hattı Boru Boyutlandırma", headers, rows)

    # 8. Warnings (design + validation + module warnings, deduplicated)
    collected_warnings: List[str] = []
    seen_warnings: set[str] = set()

    def _add_warn(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, dict):
            msg = item.get("message") or str(item)
            field = item.get("field")
            txt = f"[{field}] {msg}" if field else str(msg)
        else:
            txt = str(item)
        txt = txt.strip()
        if txt and txt not in seen_warnings:
            seen_warnings.add(txt)
            collected_warnings.append(txt)

    for w in (warnings or []):
        _add_warn(w)
    for w in (results.get("validation_warnings") or []):
        _add_warn(w)
    for w in (results.get("warnings") or []):
        _add_warn(w)
    for module in modules.values():
        if isinstance(module, dict):
            for w in (module.get("warnings") or []):
                _add_warn(w)
    if collected_warnings:
        ws = wb.create_sheet("Uyarılar")
        _write_table(
            ws,
            "Tasarım ve Modül Uyarıları",
            ["#", "Uyarı"],
            [[i + 1, w] for i, w in enumerate(collected_warnings)],
        )

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
