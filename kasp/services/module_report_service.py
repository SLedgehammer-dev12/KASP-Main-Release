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
) -> BytesIO:
    """Build a multi-sheet XLSX workbook with design, module and station results."""
    modules = modules or {}
    results = results or {}
    station_data = station_data or {}
    wb = Workbook()

    # 1. Summary
    ws = wb.active
    ws.title = "Özet"
    summary_rows = [
        ("Proje Adı", inputs.get("project_name", "-")),
        ("Rapor Tarihi", datetime.datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("EOS", inputs.get("eos_model") or inputs.get("eos_method", "-")),
        ("Hesaplama Metodu", inputs.get("calc_method") or inputs.get("method", "-")),
        ("Modüller", ", ".join(sorted(modules.keys())) if modules else "-"),
        ("İstasyon Modeli", "Var" if station_data else "Yok"),
    ]
    _write_kv(ws, "KASP Entegrasyon Raporu", summary_rows)

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

    # 8. Warnings
    warnings = []
    for module in modules.values():
        if isinstance(module, dict):
            warnings.extend(module.get("warnings") or [])
    if warnings:
        ws = wb.create_sheet("Uyarılar")
        _write_table(ws, "Modül Uyarıları", ["#", "Uyarı"], [[i + 1, w] for i, w in enumerate(warnings)])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
