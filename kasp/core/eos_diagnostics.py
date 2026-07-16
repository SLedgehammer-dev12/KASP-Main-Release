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
        from ccp import Q_, State
        return {"available": True}
    except ImportError as e:
        return {"available": False, "reason": f"ImportError: {e}"}
    except Exception as e:
        return {"available": False, "reason": f"RuntimeError: {e}"}


def _check_dwsim():
    import os, sys

    try:
        import clr
    except ImportError:
        return {"available": False, "reason": "pythonnet not installed (pip install pythonnet)"}

    libs_dir = os.path.join("kasp", "core", "libs")
    dll_path = None
    for name in ("DWSIM.Thermodynamics.StandaloneLibrary.dll", "DWSIM.Thermodynamics.dll"):
        candidate = os.path.join(libs_dir, name)
        if os.path.exists(candidate):
            dll_path = candidate
            break

    if not dll_path:
        return {"available": False, "reason": f"DLL not found in {libs_dir}/"}

    try:
        os.environ["PATH"] = os.path.abspath(libs_dir) + os.pathsep + os.environ.get("PATH", "")
        from System.Reflection import Assembly
        from System import AppDomain, ResolveEventHandler

        def _resolve(sender, args):
            name = args.Name.split(",")[0].strip()
            dll = os.path.join(os.path.abspath(libs_dir), name + ".dll")
            if os.path.exists(dll):
                return Assembly.LoadFrom(dll)
            return None

        AppDomain.CurrentDomain.AssemblyResolve += ResolveEventHandler(_resolve)
        Assembly.LoadFrom(os.path.abspath(dll_path))
        return {"available": True, "dll_path": dll_path}
    except Exception as e:
        return {"available": False, "reason": f"Load failed: {e}"}
