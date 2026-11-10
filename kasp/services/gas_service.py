"""Pure-Python Gas and Mixture Service for KASP.

Provides component mappings, standard compositions, live total checking,
smart thermodynamic EOS and method recommendations, and N x N binary interaction
parameter (kij) matrix generation and overrides for both Desktop and Web surfaces.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Any, Optional

from kasp.core.constants import SUPPORTED_GASES, DEFAULT_COMPOSITION, ALIAS_MAP

logger = logging.getLogger(__name__)

# Standard natural gas composition
DEFAULT_NATURAL_GAS_COMPOSITION = {
    "METHANE": 85.0,
    "ETHANE": 7.0,
    "PROPANE": 4.0,
    "NITROGEN": 2.0,
    "CARBONDIOXIDE": 2.0,
}

# 19 supported gases in CoolProp with human-friendly Turkish and English labels
GAS_CATALOG = [
    {"id": "METHANE", "formula": "CH4", "name_tr": "Metan (CH4)", "name_en": "Methane (CH4)", "mw": 16.04},
    {"id": "ETHANE", "formula": "C2H6", "name_tr": "Etan (C2H6)", "name_en": "Ethane (C2H6)", "mw": 30.07},
    {"id": "PROPANE", "formula": "C3H8", "name_tr": "Propan (C3H8)", "name_en": "Propane (C3H8)", "mw": 44.10},
    {"id": "ISOBUTANE", "formula": "i-C4H10", "name_tr": "İzobütan (i-C4H10)", "name_en": "Isobutane (i-C4H10)", "mw": 58.12},
    {"id": "BUTANE", "formula": "n-C4H10", "name_tr": "Normal Bütan (n-C4H10)", "name_en": "n-Butane (n-C4H10)", "mw": 58.12},
    {"id": "ISOPENTANE", "formula": "i-C5H12", "name_tr": "İzopentan (i-C5H12)", "name_en": "Isopentane (i-C5H12)", "mw": 72.15},
    {"id": "PENTANE", "formula": "n-C5H12", "name_tr": "Normal Pentan (n-C5H12)", "name_en": "n-Pentane (n-C5H12)", "mw": 72.15},
    {"id": "HEXANE", "formula": "C6H14", "name_tr": "Hekzan (C6H14)", "name_en": "Hexane (C6H14)", "mw": 86.18},
    {"id": "HEPTANE", "formula": "C7H16", "name_tr": "Heptan (C7H16)", "name_en": "Heptane (C7H16)", "mw": 100.21},
    {"id": "OCTANE", "formula": "C8H18", "name_tr": "Oktan (C8H18)", "name_en": "Octane (C8H18)", "mw": 114.23},
    {"id": "NONANE", "formula": "C9H20", "name_tr": "Nonan (C9H20)", "name_en": "Nonane (C9H20)", "mw": 128.26},
    {"id": "DECANE", "formula": "C10H22", "name_tr": "Dekan (C10H22)", "name_en": "Decane (C10H22)", "mw": 142.29},
    {"id": "HYDROGEN", "formula": "H2", "name_tr": "Hidrojen (H2)", "name_en": "Hydrogen (H2)", "mw": 2.016},
    {"id": "NITROGEN", "formula": "N2", "name_tr": "Azot (N2)", "name_en": "Nitrogen (N2)", "mw": 28.01},
    {"id": "OXYGEN", "formula": "O2", "name_tr": "Oksijen (O2)", "name_en": "Oxygen (O2)", "mw": 32.00},
    {"id": "CARBONDIOXIDE", "formula": "CO2", "name_tr": "Karbondioksit (CO2)", "name_en": "Carbon Dioxide (CO2)", "mw": 44.01},
    {"id": "WATER", "formula": "H2O", "name_tr": "Su Buharı (H2O)", "name_en": "Water (H2O)", "mw": 18.02},
    {"id": "HYDROGENSULFIDE", "formula": "H2S", "name_tr": "Hidrojen Sülfür (H2S)", "name_en": "Hydrogen Sulfide (H2S)", "mw": 34.08},
    {"id": "AIR", "formula": "Air", "name_tr": "Hava (Air)", "name_en": "Air (Air)", "mw": 28.97},
]

# Literature kij parameters for PR/SRK
_KEY = lambda a: str(a).replace(" ", "").upper()
_PR_SRK_KIJ = {
    ("CARBONDIOXIDE", "METHANE"): 0.100,
    ("CARBONDIOXIDE", "ETHANE"): 0.130,
    ("CARBONDIOXIDE", "PROPANE"): 0.125,
    ("CARBONDIOXIDE", "BUTANE"): 0.120,
    ("CARBONDIOXIDE", "ISOBUTANE"): 0.120,
    ("CARBONDIOXIDE", "NITROGEN"): -0.017,
    ("CARBONDIOXIDE", "HYDROGENSULFIDE"): 0.100,
    ("CARBONDIOXIDE", "HYDROGEN"): 0.060,
    ("METHANE", "HYDROGENSULFIDE"): 0.080,
    ("ETHANE", "HYDROGENSULFIDE"): 0.080,
    ("PROPANE", "HYDROGENSULFIDE"): 0.070,
    ("BUTANE", "HYDROGENSULFIDE"): 0.060,
    ("ISOBUTANE", "HYDROGENSULFIDE"): 0.060,
    ("NITROGEN", "METHANE"): 0.031,
    ("NITROGEN", "ETHANE"): 0.050,
    ("NITROGEN", "PROPANE"): 0.080,
    ("NITROGEN", "BUTANE"): 0.100,
    ("NITROGEN", "ISOBUTANE"): 0.100,
    ("NITROGEN", "HYDROGENSULFIDE"): 0.170,
    ("HYDROGEN", "METHANE"): 0.030,
    ("HYDROGEN", "ETHANE"): 0.045,
    ("HYDROGEN", "PROPANE"): 0.060,
    ("HYDROGEN", "NITROGEN"): 0.100,
    ("WATER", "METHANE"): 0.450,
    ("WATER", "ETHANE"): 0.400,
    ("WATER", "CARBONDIOXIDE"): 0.120,
    ("WATER", "HYDROGENSULFIDE"): 0.100,
}

_HIGH_ERROR_COMPONENTS = {"CARBONDIOXIDE", "HYDROGENSULFIDE", "HYDROGEN", "WATER", "H2S", "CO2"}


def standard_composition_for_gas(gas_name: str) -> Dict[str, float]:
    """Return a standard composition dict for a selected gas label."""
    normalized = (gas_name or "").casefold()

    if "methane" in normalized or normalized == "ch4":
        return {"METHANE": 100.0}
    if "ethane" in normalized or normalized == "c2h6":
        return {"ETHANE": 100.0}
    if "propane" in normalized or normalized == "c3h8":
        return {"PROPANE": 100.0}
    if "nitrogen" in normalized or normalized == "n2":
        return {"NITROGEN": 100.0}
    if "carbon dioxide" in normalized or normalized == "co2":
        return {"CARBONDIOXIDE": 100.0}
    if "hydrogen sulfide" in normalized or "hydrogen sulphide" in normalized or normalized == "h2s":
        return {"HYDROGENSULFIDE": 100.0}
    if "hydrogen" in normalized or normalized == "h2":
        return {"HYDROGEN": 100.0}
    if "water" in normalized or normalized.startswith("su") or normalized == "h2o":
        return {"WATER": 100.0}
    if normalized == "air" or "hava" in normalized:
        return {"NITROGEN": 78.0, "OXYGEN": 21.0, "ARGON": 1.0}
    return dict(DEFAULT_NATURAL_GAS_COMPOSITION)


def normalize_percentage_values(values: List[float]) -> Tuple[List[float], float]:
    """Normalize percentage values so their sum becomes 100.0."""
    clipped = [max(0.0, float(v)) for v in values]
    total = sum(clipped)
    if total <= 0:
        raise ValueError("Tüm bileşen yüzdeleri sıfır veya boş. Normalize edilecek değer yok.")
    return [(v / total) * 100.0 for v in clipped], total


def normalize_composition_dict(comp: Dict[str, float]) -> Dict[str, float]:
    """Normalize a gas composition dictionary so values sum to 100.0."""
    if not comp or not isinstance(comp, dict):
        return {}
    filtered = {}
    for k, v in comp.items():
        try:
            val = float(v)
            if val > 0:
                filtered[k] = val
        except (TypeError, ValueError):
            continue
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {k: round((v / total) * 100.0, 4) for k, v in filtered.items()}


def build_total_label_state(total: float) -> Tuple[str, str]:
    """Return text and state for the live composition-total label."""
    diff = abs(total - 100.0)
    if diff < 0.01:
        return (f"Toplam: {total:.2f}%  ✔", "valid")
    if diff < 1.0:
        return (f"Toplam: {total:.2f}%  ⚠ (%100'e yakın)", "warning")
    return (f"Toplam: {total:.2f}%  ✘ (100.00% olmalı!)", "invalid")


def get_smart_eos_recommendation(gas_comp: Dict[str, float], p_out_bar: float | None = None) -> Dict[str, Any]:
    """
    Gaz kompozisyonuna göre en uygun EOS tavsiyesini yapılandırılmış olarak döndürür.
    """
    if not gas_comp or not isinstance(gas_comp, dict):
        return {
            "recommended_eos": "coolprop",
            "title": "EoS Önerisi",
            "message": "Gaz kompozisyonu giriniz.",
            "category": "default"
        }

    parsed = {}
    for k, v in gas_comp.items():
        try:
            val = float(v)
            if val > 0:
                parsed[str(k).upper()] = val
        except (TypeError, ValueError):
            continue

    total_pct = sum(parsed.values())
    if total_pct <= 0:
        return {
            "recommended_eos": "coolprop",
            "title": "EoS Önerisi",
            "message": "Gaz kompozisyonu giriniz.",
            "category": "default"
        }

    norm_comp = {k: (v / total_pct) * 100.0 for k, v in parsed.items()}

    # 1. Saf akışkan kontrolü
    if len(norm_comp) == 1 or max(norm_comp.values()) >= 99.0:
        main_comp = max(norm_comp, key=norm_comp.get)
        return {
            "recommended_eos": "coolprop",
            "title": f"Saf Akışkan ({main_comp})",
            "message": "CoolProp (HEOS) saf akışkanlarda en yüksek teorik ve deneysel hassasiyeti sağlar.",
            "category": "pure"
        }

    # 2. Polar / Nemli / Asit Gazı kontrolü
    water_pct = norm_comp.get("WATER", 0.0) + norm_comp.get("H2O", 0.0)
    h2s_pct = norm_comp.get("HYDROGENSULFIDE", 0.0) + norm_comp.get("H2S", 0.0)
    co2_pct = norm_comp.get("CARBONDIOXIDE", 0.0) + norm_comp.get("CO2", 0.0)

    if water_pct > 0.05 or h2s_pct > 0.5:
        return {
            "recommended_eos": "neqsim",
            "title": "Polar / Asit Gazı",
            "message": "Su/H₂S içeren akışkanlar için Equinor NeqSim (SRK-CPA) önerilir.",
            "category": "polar"
        }
    if co2_pct > 5.0:
        return {
            "recommended_eos": "thermopack",
            "title": f"Yüksek CO₂ (%{co2_pct:.1f})",
            "message": "Asit gazı faz dengesi için SINTEF thermopack veya NeqSim (CPA) önerilir.",
            "category": "acid"
        }

    # 3. Zengin Hidrokarbon kontrolü
    heavy_c6 = sum(norm_comp.get(k, 0.0) for k in ["HEXANE", "HEPTANE", "OCTANE", "NONANE", "DECANE"])
    c3_plus = sum(norm_comp.get(k, 0.0) for k in [
        "PROPANE", "ISOBUTANE", "BUTANE", "ISOPENTANE", "PENTANE", "HEXANE", "HEPTANE", "OCTANE", "NONANE", "DECANE"
    ])
    methane_pct = norm_comp.get("METHANE", 0.0)

    if heavy_c6 > 0.25 or c3_plus > 10.0 or methane_pct < 85.0:
        return {
            "recommended_eos": "pr",
            "title": "Zengin Gaz (C1–C6+)",
            "message": "VLE kararlılığı ve hesaplama hızı için SINTEF thermopack veya Peng-Robinson önerilir.",
            "category": "rich"
        }

    # 4. Kuru Boru Hattı Satış Gazı
    return {
        "recommended_eos": "coolprop",
        "title": "Kuru Satış Gazı",
        "message": "Boru hattı şartnamesi için CoolProp, thermopack (PR) veya AGA8-DC92 uygundur.",
        "category": "sales_gas"
    }


def get_smart_method_recommendation(
    gas_comp: Dict[str, float],
    p_in: float | None = None,
    p_out: float | None = None,
    pr: float | None = None,
) -> Dict[str, Any]:
    """
    Gaz kompozisyonuna ve proses şartlarına göre en uygun Politropik Yol Metodu önerisini döndürür.
    """
    calc_pr = pr
    if calc_pr is None:
        try:
            p_in_f = float(p_in) if p_in is not None else None
            p_out_f = float(p_out) if p_out is not None else None
            if p_in_f is not None and p_out_f is not None and p_in_f > 0:
                calc_pr = p_out_f / p_in_f
        except (TypeError, ValueError):
            calc_pr = None

    if not gas_comp or not isinstance(gas_comp, dict):
        return {
            "recommended_method": "Metot 6: Schultz 3-Üslü",
            "title": "Metot Önerisi",
            "message": "Gaz kompozisyonu giriniz."
        }

    parsed = {}
    for k, v in gas_comp.items():
        try:
            val = float(v)
            if val > 0:
                parsed[str(k).upper()] = val
        except (TypeError, ValueError):
            continue

    total_pct = sum(parsed.values())
    if total_pct <= 0:
        return {
            "recommended_method": "Metot 6: Schultz 3-Üslü",
            "title": "Metot Önerisi",
            "message": "Gaz kompozisyonu giriniz."
        }

    norm_comp = {k: (v / total_pct) * 100.0 for k, v in parsed.items()}

    # Saf akışkan
    if len(norm_comp) == 1 or max(norm_comp.values()) >= 99.0:
        return {
            "recommended_method": "Metot 4: Doğrudan H-S",
            "title": "Saf Akışkan",
            "message": "Hızlı ve tam fiziksel doğruluk için Metot 4 (Doğrudan H-S) veya Metot 5 (Huntington-RK45) önerilir."
        }

    # Polar / Ekşi gaz
    water_pct = norm_comp.get("WATER", 0.0) + norm_comp.get("H2O", 0.0)
    h2s_pct = norm_comp.get("HYDROGENSULFIDE", 0.0) + norm_comp.get("H2S", 0.0)
    co2_pct = norm_comp.get("CARBONDIOXIDE", 0.0) + norm_comp.get("CO2", 0.0)
    if water_pct > 0.05 or h2s_pct > 0.5 or co2_pct > 5.0:
        return {
            "recommended_method": "Metot 5: Huntington-RK45",
            "title": "Polar / Asit Gazı",
            "message": "Entalpi-entropi dengesini sürekli diferansiyel adımla çözen Metot 5 (Huntington-RK45) önerilir."
        }

    # Yüksek basınç oranı
    if calc_pr is not None and calc_pr >= 2.5:
        return {
            "recommended_method": "Metot 6: Schultz 3-Üslü",
            "title": f"Yüksek Basınç Oranı (PR={calc_pr:.2f})",
            "message": "ASME PTC-10 standartlarına uyumlu ayrık durum türevleri için Metot 6 (Schultz 3-Üslü) önerilir."
        }

    return {
        "recommended_method": "Metot 6: Schultz 3-Üslü",
        "title": "Endüstri Standardı",
        "message": "ASME PTC-10 ve API 617 uyumlu Metot 6 (Schultz 3-Üslü) veya Metot 5 (Huntington-RK45) önerilir."
    }


def get_kij_matrix_for_composition(
    gas_comp: Dict[str, float],
    custom_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Aktif gaz karışımındaki bileşenler için N x N simetrik kij matrisini oluşturur.
    custom_overrides: {"METHANE:CARBONDIOXIDE": 0.12, ...} şeklinde kullanıcı düzenlemelerini kabul eder.
    """
    comp_safe = gas_comp if (gas_comp and isinstance(gas_comp, dict)) else {}
    custom_overrides = custom_overrides or {}

    # Aktif bileşenleri sıralı olarak seç (mol % > 0)
    active_components = []
    for gas in GAS_CATALOG:
        cid = gas["id"]
        # Alias kontrolü ile bileşen yüzdesini bul
        pct = 0.0
        for comp_name, val in comp_safe.items():
            norm_name = ALIAS_MAP.get(_KEY(comp_name), _KEY(comp_name))
            if norm_name == cid:
                try:
                    pct += float(val)
                except (TypeError, ValueError):
                    pass
        if pct > 0.0:
            active_components.append(cid)

    # Eğer hiç aktif yoksa gaz_comp içindeki ham anahtarları kullan
    if not active_components and comp_safe:
        for k, v in comp_safe.items():
            try:
                if float(v) > 0:
                    active_components.append(ALIAS_MAP.get(_KEY(k), _KEY(k)))
            except (TypeError, ValueError):
                pass
        active_components = sorted(set(active_components))

    n = len(active_components)
    matrix = [[0.0] * n for _ in range(n)]
    sources = [["none"] * n for _ in range(n)]
    risky_missing = []

    for i in range(n):
        for j in range(i, n):
            ci = active_components[i]
            cj = active_components[j]
            if i == j:
                matrix[i][j] = 0.0
                sources[i][j] = "diagonal"
                continue

            pair_key_1 = f"{ci}:{cj}"
            pair_key_2 = f"{cj}:{ci}"
            
            # 1. Kullanıcı override kontrolü
            val = None
            src = "user_override"
            if pair_key_1 in custom_overrides:
                try:
                    val = float(custom_overrides[pair_key_1])
                except (TypeError, ValueError):
                    val = None
            elif pair_key_2 in custom_overrides:
                try:
                    val = float(custom_overrides[pair_key_2])
                except (TypeError, ValueError):
                    val = None

            if val is None:
                # 2. Literatür tablosu kontrolü
                lit_key = tuple(sorted((ci, cj)))
                lit_val = _PR_SRK_KIJ.get(lit_key)
                if lit_val is not None:
                    val = float(lit_val)
                    src = "literature_pr_srk"
                else:
                    val = 0.0
                    src = "default_zero"
                    if ci in _HIGH_ERROR_COMPONENTS or cj in _HIGH_ERROR_COMPONENTS:
                        risky_missing.append(f"{ci}-{cj}")

            matrix[i][j] = val
            matrix[j][i] = val
            sources[i][j] = src
            sources[j][i] = src

    return {
        "components": active_components,
        "size": n,
        "matrix": matrix,
        "sources": sources,
        "risky_missing_pairs": risky_missing,
        "has_overrides": bool(custom_overrides),
    }


# Convenience aliases for Web API & tests
get_kij_matrix_data = get_kij_matrix_for_composition
normalize_gas_composition = normalize_composition_dict
