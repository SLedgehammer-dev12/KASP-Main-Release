# -*- mode: python ; coding: utf-8 -*-
# Release spec for GitHub release v2.1.0 (Windows).
# v2.1.0: Security hardening, thermodynamic fixes, repository pattern, strategy pattern, 164 tests.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from release_metadata import RELEASE_EXE_STEM


def include_runtime_submodule(name):
    parts = name.split(".")
    if name.startswith("scipy._lib.array_api_compat.") and not name.startswith(
        ("scipy._lib.array_api_compat.common", "scipy._lib.array_api_compat.numpy")
    ):
        return False
    if any(part in parts for part in ("tests", "testing", "torch", "dask", "cupy", "conftest")):
        return False
    return not parts[-1].startswith(("test_", "_test"))


thermo_datas = collect_data_files("thermo")
chemicals_datas = collect_data_files("chemicals")
scipy_datas = collect_data_files("scipy")
thermopack_datas = collect_data_files("thermopack")

all_datas = [
    ("kasp", "kasp"),
    ("kasp_database.db", "."),
    ("kasp_config.json", "."),
    ("release_metadata.py", "."),
    ("resources", "resources"),
]
all_datas.extend(thermo_datas)
all_datas.extend(chemicals_datas)
all_datas.extend(scipy_datas)
all_datas.extend(thermopack_datas)

# DWSIM DLL bundle
dwsim_binaries = []
dwsim_dll_dir = ROOT / "kasp" / "core" / "libs"
if dwsim_dll_dir.exists():
    for dll_name in ["DWSIM.Thermodynamics.StandaloneLibrary.dll", "DWSIM.UnitOperations.dll"]:
        dll_path = dwsim_dll_dir / dll_name
        if dll_path.exists():
            dwsim_binaries.append((str(dll_path), "."))

try:
    pythonnet_datas = collect_data_files("pythonnet")
    all_datas.extend(pythonnet_datas)
except Exception:
    pass

try:
    certifi_datas = collect_data_files("certifi")
    all_datas.extend(certifi_datas)
except Exception:
    pass

all_hidden = []
all_hidden.extend([
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.qt_compat",
])
all_hidden.extend(collect_submodules("thermo", filter=include_runtime_submodule))
all_hidden.extend(collect_submodules("chemicals", filter=include_runtime_submodule))
all_hidden.extend(collect_submodules("scipy", filter=include_runtime_submodule))
all_hidden.extend(collect_submodules("thermopack", filter=include_runtime_submodule))

# pythonnet hidden imports
try:
    all_hidden.extend(collect_submodules("pythonnet", filter=include_runtime_submodule))
except Exception:
    pass
all_hidden.append("clr")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=dwsim_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "doctest", "torch"],
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
    name=RELEASE_EXE_STEM,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="resources/icon.ico",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
