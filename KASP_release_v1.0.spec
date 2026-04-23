# -*- mode: python ; coding: utf-8 -*-
# Release spec for GitHub release v1.0 (source baseline 4.6.2)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from release_metadata import RELEASE_EXE_STEM

thermo_datas = collect_data_files("thermo")
chemicals_datas = collect_data_files("chemicals")
scipy_datas = collect_data_files("scipy")

all_datas = [("kasp", "kasp"), ("kasp_database.db", "."), ("kasp_config.json", "."), ("resources", "resources")]
all_datas.extend(thermo_datas)
all_datas.extend(chemicals_datas)
all_datas.extend(scipy_datas)

all_hidden = []
all_hidden.extend(collect_submodules("thermo"))
all_hidden.extend(collect_submodules("chemicals"))
all_hidden.extend(collect_submodules("scipy"))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
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
