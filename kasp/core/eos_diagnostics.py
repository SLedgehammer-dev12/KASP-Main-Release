"""
EOS Diagnostics (v2.1)

Tests each EOS backend and reports availability + detailed failure reason.
Called from engineering tab and API health endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def diagnose_all_eos() -> dict[str, dict[str, Any]]:
    results = {}
    results["coolprop"] = _check_coolprop()
    results["pr"] = _check_thermo_pr()
    results["srk"] = _check_thermo_srk()
    results["aga8"] = _check_aga8()
    results["thermopack"] = _check_thermopack()
    results["ccp"] = _check_ccp()
    results["dwsim"] = _check_dwsim()
    return results


def _check_coolprop():
    try:
        import CoolProp.CoolProp as CP
        ver = getattr(CP, '__version__', 'installed')
        return {"available": True, "version": str(ver)}
    except ImportError as e:
        return {"available": False, "reason": f"ImportError: {e}"}


def _check_thermo_pr():
    try:
        from thermo.eos_mix import PRMIX
        from thermo import ChemicalConstantsPackage
        return {"available": True}
    except ImportError as e:
        return {"available": False, "reason": f"ImportError: {e}"}


def _check_thermo_srk():
    try:
        from thermo.eos_mix import SRKMIX
        return {"available": True}
    except ImportError as e:
        return {"available": False, "reason": f"ImportError: {e}"}


def _check_aga8():
    try:
        import pyaga8
        return {"available": True}
    except ImportError:
        try:
            from pyaga8 import AGA8
            return {"available": True}
        except ImportError as e:
            return {"available": False, "reason": f"ImportError: {e}"}


def _check_thermopack():
    try:
        from thermopack.cubic import cubic
        return {"available": True}
    except ImportError as e:
        return {"available": False, "reason": f"ImportError: {e}"}
    except Exception as e:
        return {"available": False, "reason": f"RuntimeError: {e}"}


def _check_ccp():
    try:
        import sys as _sys
        if "pkg_resources" not in _sys.modules:
            import kasp.core.pkg_resources as _shim
            _sys.modules["pkg_resources"] = _shim
        import ccp
        try:
            from ccp import Q_
        except ImportError:
            from pint import Quantity as Q_
        return {"available": True}
    except ImportError as e:
        detail = str(e)
        if "pkg_resources" in detail:
            detail += " (Python 3.12+ compatibility shim loaded)"
        return {"available": False, "reason": f"ImportError: {detail}"}
    except Exception as e:
        return {"available": False, "reason": f"RuntimeError: {e}"}


def _check_dwsim():
    import os, sys

    try:
        import clr
    except ImportError as e:
        return {"available": False, "reason": "ImportError: pythonnet not installed (pip install pythonnet)"}

    dll_name = "DWSIM.Thermodynamics.StandaloneLibrary.dll"
    search_paths = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        search_paths.append(os.path.join(sys._MEIPASS, dll_name))
    search_paths.extend([
        os.path.join("kasp", "core", "libs", dll_name),
        os.path.join("kasp", "libs", dll_name),
        dll_name,
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "DWSIM", dll_name),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "DWSIM", dll_name),
    ])

    for p in search_paths:
        if os.path.exists(p):
            try:
                clr.AddReference(p)
                return {"available": True, "dll_path": p}
            except Exception as e:
                return {"available": False, "reason": f"DLL found at {p} but failed to load: {e}"}

    return {"available": False, "reason": f"DLL not found. Searched: {search_paths[:4]}..."}
