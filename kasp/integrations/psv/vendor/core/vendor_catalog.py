import os
import json
import sys
import logging

logger = logging.getLogger(__name__)

_catalog_cache = None
_catalog_path = None

def _load_catalog():
    global _catalog_cache, _catalog_path
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    _catalog_path = os.path.join(base_path, "vendor_data", "psv_vendor_catalog_official.json")

    if not os.path.exists(_catalog_path):
        logger.warning("Vendor catalog file not found at: %s", _catalog_path)
        _catalog_cache = {"models": []}
        return

    try:
        with open(_catalog_path, 'r', encoding='utf-8') as f:
            _catalog_cache = json.load(f)
    except Exception as e:
        logger.error("Vendor catalog read error: %s", e)
        _catalog_cache = {"models": []}

_DESIGN_CATEGORY_KEYWORDS = {
    "conventional": ("conventional", "spring"),
    "balanced_bellows": ("balanced", "bellows"),
    "pilot": ("pilot",),
}

def _design_categories(design_type):
    """Classify a vendor design_type string into one or more valve categories."""
    text = (design_type or "").lower()
    cats = set()
    for cat, keywords in _DESIGN_CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            cats.add(cat)
    if not cats and text:
        cats.add("conventional")
    return cats

def _verification_status(model):
    """Classify a catalog row by provenance.

    Returns "sourced" for rows traceable to a manufacturer document and
    "screening" for generated placeholder rows that must not be presented as
    verified commercial selections.
    """
    quality = str(model.get("data_quality", "") or "").lower()
    source = str(model.get("source", "") or "")
    if quality == "screening_placeholder":
        return "screening"
    if "Synthetic" in source or "Coverage Extension" in source:
        return "screening"
    if not source:
        return "screening"
    return "sourced"


def get_vendor_valves(api_letter, valve_type=None):
    if not api_letter or api_letter == "-":
        return []

    if _catalog_cache is None:
        _load_catalog()

    matching_valves = []
    for model in _catalog_cache.get("models", []):
        if model.get("api526_equivalent") == api_letter or model.get("orifice_letter") == api_letter:
            if valve_type:
                if valve_type.lower() not in _design_categories(model.get("design_type", "")):
                    continue
            entry = dict(model)
            entry["verification_status"] = _verification_status(model)
            matching_valves.append(entry)

    return matching_valves

def reload_catalog():
    global _catalog_cache
    _catalog_cache = None
    _load_catalog()


def get_family_data(api_letter):
    """Return manufacturer-sourced family data (real actual areas and
    certified Kd) for an API orifice letter.

    These rows come from the catalog's ``families`` section and can be used
    to verify the capacity of a selected valve model instead of relying on
    the generated screening rows.
    """
    if not api_letter or api_letter == "-":
        return []
    if _catalog_cache is None:
        _load_catalog()

    results = []
    for family in _catalog_cache.get("families", []):
        areas = family.get("actual_area_mm2_by_orifice") or {}
        if api_letter not in areas:
            continue
        results.append({
            "manufacturer": family.get("manufacturer"),
            "series": family.get("series"),
            "design_type": family.get("design_type"),
            "model_code_prefix": family.get("model_code_prefix"),
            "certified_kd_gas": family.get("certified_kd_gas"),
            "body_material": family.get("body_material"),
            "trim_material": family.get("trim_material"),
            "actual_area_mm2": areas.get(api_letter),
            "actual_area_sqin": round(areas[api_letter] / 645.16, 4) if areas.get(api_letter) else None,
            "source": family.get("source"),
            "notes": family.get("notes"),
            "verification_status": "sourced",
        })
    return results


def catalog_quality_summary():
    """Count catalog rows by verification status for UI/API disclosure."""
    if _catalog_cache is None:
        _load_catalog()
    summary = {"sourced": 0, "screening": 0}
    for model in _catalog_cache.get("models", []):
        summary[_verification_status(model)] += 1
    return summary
