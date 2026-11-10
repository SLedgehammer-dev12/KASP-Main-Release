"""Pure-Python Input Validation Service for KASP.

Provides physics-based validation for pressure, temperature, flow, gas mixture,
speed, and multi-stage parameters without any Qt dependencies.
Can be used by FastAPI endpoints, background tasks, and UI controllers.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple

from kasp.core.units import UnitSystem
from kasp.core.exceptions import UnitConversionError
from kasp.i18n import tr


def validate_pressure(value: Any, unit: str = "bar(a)") -> Tuple[bool, str, str]:
    """
    Validate pressure input.
    Returns: (is_valid, message, severity: 'error' | 'warning' | 'ok')
    """
    if value is None or str(value).strip() == "":
        return False, tr("Basınç değeri zorunludur"), "error"

    try:
        val = float(value)
        unit = str(unit or "bar(a)").strip()

        if not math.isfinite(val):
            return False, tr("Basınç sonlu bir sayı olmalıdır"), "error"

        # Check for non-positive absolute pressure
        if unit in ["bar(a)", "psia", "kPa", "MPa", "Pa", "atm"]:
            if val <= 0:
                return False, tr("Mutlak basınç > 0 olmalıdır"), "error"

        # Check gauge pressure (limit: -1.0 bar(g) = vacuum)
        if unit in ["bar(g)", "psig"]:
            try:
                limit = UnitSystem.convert_pressure(-1.0, "bar(g)", unit)
            except Exception:
                limit = -1.0 if unit == "bar(g)" else -14.5038

            if val < limit:
                return False, tr(f"Efektif basınç çok düşük (min {limit:.1f} {unit})"), "error"

        # Range warnings
        try:
            val_bar = UnitSystem.convert_pressure(val, unit, "bar(a)")
            if val_bar > 500.0:
                return True, tr(f"⚠️ Çok yüksek basınç ({val:.1f} {unit})"), "warning"
        except Exception:
            pass

        return True, "", "ok"
    except (ValueError, TypeError):
        return False, tr("Geçersiz sayı formatı"), "error"


def validate_temperature(value: Any, unit: str = "°C") -> Tuple[bool, str, str]:
    """
    Validate temperature input against absolute zero and physical limits.
    Returns: (is_valid, message, severity: 'error' | 'warning' | 'ok')
    """
    if value is None or str(value).strip() == "":
        return False, tr("Sıcaklık değeri zorunludur"), "error"

    try:
        val = float(value)
        unit = str(unit or "°C").strip()

        if not math.isfinite(val):
            return False, tr("Sıcaklık sonlu bir sayı olmalıdır"), "error"

        try:
            k_val = UnitSystem.convert_temperature(val, unit, "K")
        except UnitConversionError as e:
            return False, tr(f"Birim dönüşüm hatası: {e}"), "error"

        if k_val <= 0:
            return False, tr("Sıcaklık mutlak sıfırın (0 K) üzerinde olmalıdır!"), "error"

        if k_val < 100:
            return True, tr("⚠️ Çok düşük sıcaklık (kriyojenik)"), "warning"

        if k_val > 900:
            return True, tr("⚠️ Çok yüksek sıcaklık"), "warning"

        return True, "", "ok"
    except (ValueError, TypeError):
        return False, tr("Geçersiz sayı formatı"), "error"


def validate_flow(value: Any, unit: str = "kg/s") -> Tuple[bool, str, str]:
    """
    Validate flow rate.
    Returns: (is_valid, message, severity: 'error' | 'warning' | 'ok')
    """
    if value is None or str(value).strip() == "":
        return False, tr("Debi değeri zorunludur"), "error"

    try:
        val = float(value)
        if not math.isfinite(val):
            return False, tr("Debi sonlu bir sayı olmalıdır"), "error"

        if val <= 0:
            return False, tr("Debi pozitif olmalıdır"), "error"

        if val > 1e8:
            return True, tr("⚠️ Çok yüksek debi"), "warning"

        return True, "", "ok"
    except (ValueError, TypeError):
        return False, tr("Geçersiz sayı formatı"), "error"


def validate_pressure_ratio(p_in: float, p_in_unit: str, p_out: float, p_out_unit: str, num_stages: int = 1) -> Tuple[bool, float, str, str]:
    """
    Calculate and validate pressure ratio (PR = P_out / P_in in absolute pressure).
    Returns: (is_valid, pr_value, message, severity)
    """
    try:
        p_in_bar = UnitSystem.convert_pressure(float(p_in), p_in_unit, "bar(a)")
        p_out_bar = UnitSystem.convert_pressure(float(p_out), p_out_unit, "bar(a)")

        if p_in_bar <= 0 or p_out_bar <= 0:
            return False, 0.0, tr("Basınç değerleri pozitif olmalıdır"), "error"

        pr = p_out_bar / p_in_bar
        if pr <= 1.0:
            return False, pr, tr(f"Çıkış basıncı girişten büyük olmalıdır (PR={pr:.2f} <= 1.0)"), "error"

        if pr > 4.0 and int(num_stages) == 1:
            return True, pr, tr(f"Yüksek basınç oranı (PR={pr:.2f} > 4.0). Çok kademeli sıkıştırma önerilir."), "warning"

        pr_per_stage = pr ** (1.0 / max(1, int(num_stages)))
        if pr_per_stage > 4.5:
            return True, pr, tr(f"Kademe başına düşen basınç oranı ({pr_per_stage:.2f}) yüksek."), "warning"

        return True, pr, "", "ok"
    except Exception as e:
        return False, 0.0, f"Basınç oranı hesaplanamadı: {e}", "error"


def validate_design_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive validation of all design inputs dictionary.
    Returns:
    {
        "is_valid": bool,
        "errors": [{"field": str, "message": str}],
        "warnings": [{"field": str, "message": str}],
        "metrics": {"pr": float, "delta_p": float}
    }
    """
    errors = []
    warnings = []

    p_in = inputs.get("p_in")
    p_in_u = inputs.get("p_in_unit", "bar(a)")
    ok_p1, msg_p1, sev_p1 = validate_pressure(p_in, p_in_u)
    if not ok_p1:
        errors.append({"field": "p_in", "message": msg_p1})
    elif sev_p1 == "warning":
        warnings.append({"field": "p_in", "message": msg_p1})

    p_out = inputs.get("p_out")
    p_out_u = inputs.get("p_out_unit", "bar(a)")
    ok_p2, msg_p2, sev_p2 = validate_pressure(p_out, p_out_u)
    if not ok_p2:
        errors.append({"field": "p_out", "message": msg_p2})
    elif sev_p2 == "warning":
        warnings.append({"field": "p_out", "message": msg_p2})

    t_in = inputs.get("t_in")
    t_in_u = inputs.get("t_in_unit", "°C")
    ok_t, msg_t, sev_t = validate_temperature(t_in, t_in_u)
    if not ok_t:
        errors.append({"field": "t_in", "message": msg_t})
    elif sev_t == "warning":
        warnings.append({"field": "t_in", "message": msg_t})

    flow = inputs.get("flow")
    flow_u = inputs.get("flow_unit", "kg/s")
    ok_f, msg_f, sev_f = validate_flow(flow, flow_u)
    if not ok_f:
        errors.append({"field": "flow", "message": msg_f})
    elif sev_f == "warning":
        warnings.append({"field": "flow", "message": msg_f})

    num_stages = int(inputs.get("num_stages", 1))
    if num_stages < 1 or num_stages > 20:
        errors.append({"field": "num_stages", "message": "Kademe sayısı 1 ile 20 arasında olmalıdır."})

    # PR check if p1 and p2 are valid
    pr = 0.0
    if ok_p1 and ok_p2:
        ok_pr, pr_val, msg_pr, sev_pr = validate_pressure_ratio(p_in, p_in_u, p_out, p_out_u, num_stages)
        pr = pr_val
        if not ok_pr:
            errors.append({"field": "p_out", "message": msg_pr})
        elif sev_pr == "warning":
            warnings.append({"field": "num_stages", "message": msg_pr})

    # Gas composition validation
    gas_comp = inputs.get("gas_comp") or {}
    if not gas_comp or sum(float(v) for v in gas_comp.values()) <= 0:
        errors.append({"field": "gas_comp", "message": "En az bir gaz bileşeni girilmelidir."})
    else:
        total = sum(float(v) for v in gas_comp.values())
        if abs(total - 100.0) >= 1.0:
            warnings.append({"field": "gas_comp", "message": f"Gaz bileşimi toplamı %{total:.2f}; %100'e normalize edilecek."})

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "pressure_ratio": round(pr, 3),
        }
    }
