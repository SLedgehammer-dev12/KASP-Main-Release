# -*- mode: python ; coding: utf-8 -*-
# KASP V4.6 — Local Spec File (workspace build)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

# Data files
thermo_datas   = collect_data_files('thermo')
chemicals_datas = collect_data_files('chemicals')
scipy_datas    = collect_data_files('scipy')

all_datas = [('kasp', 'kasp'), ('kasp_database.db', '.'), ('kasp_config.json', '.')]
all_datas.extend(thermo_datas)
all_datas.extend(chemicals_datas)
all_datas.extend(scipy_datas)

# Hidden imports
all_hidden = []
all_hidden.extend(collect_submodules('thermo'))
all_hidden.extend(collect_submodules('chemicals'))
all_hidden.extend(collect_submodules('scipy'))
all_hidden.extend(['pysqlite2', 'MySQLdb'])

a = Analysis(
    ['main.py'],
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
    name='KASP V4.6',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
