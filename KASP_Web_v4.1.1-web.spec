# -*- mode: python ; coding: utf-8 -*-
# Release spec for KASP Web Edition (Windows .exe).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from release_metadata import WEB_EXE_STEM, WEB_ICON_ICO


def include_runtime_submodule(name):
    parts = name.split(".")
    if name.startswith("scipy._lib.array_api_compat.") and not name.startswith(
        ("scipy._lib.array_api_compat.common", "scipy._lib.array_api_compat.numpy")
    ):
        return False
    if any(part in parts for part in ("tests", "testing", "torch", "dask", "cupy", "conftest")):
        return False
    return not parts[-1].startswith(("test_", "_test"))


all_datas = [
    ("kasp", "kasp"),
    ("kasp_config.json", "."),
    ("release_metadata.py", "."),
    ("resources", "resources"),
]
for pkg in ("thermo", "chemicals", "scipy", "thermopack", "ccp"):
    all_datas.extend(collect_data_files(pkg))

# DWSIM DLL bundle
dwsim_binaries = []
dwsim_dll_dir = ROOT / "kasp" / "core" / "libs"
if dwsim_dll_dir.exists():
    for dll_name in ["DWSIM.Thermodynamics.StandaloneLibrary.dll", "DWSIM.UnitOperations.dll"]:
        dll_path = dwsim_dll_dir / dll_name
        if dll_path.exists():
            dwsim_binaries.append((str(dll_path), "."))

# NeqSim jar bundle
neqsim_jar_path = ROOT / "kasp" / "core" / "libs" / "neqsim.jar"
if neqsim_jar_path.exists():
    all_datas.append((str(neqsim_jar_path), "kasp/core/libs"))

try:
    all_datas.extend(collect_data_files("certifi"))
except Exception:
    pass

all_hidden = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]
for pkg in ("kasp", "uvicorn", "fastapi", "starlette", "pydantic", "anyio", "h11"):
    try:
        all_hidden.extend(collect_submodules(pkg, filter=include_runtime_submodule))
    except Exception:
        pass
for pkg in ("thermo", "chemicals", "scipy", "thermopack", "ccp"):
    all_hidden.extend(collect_submodules(pkg, filter=include_runtime_submodule))

try:
    all_hidden.extend(collect_submodules("pythonnet", filter=include_runtime_submodule))
    all_hidden.append("clr")
except Exception:
    pass

a = Analysis(
    ["run_web.py"],
    pathex=[],
    binaries=dwsim_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "doctest", "torch", "PyQt5", "PySide6", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=WEB_EXE_STEM,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=WEB_ICON_ICO,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
