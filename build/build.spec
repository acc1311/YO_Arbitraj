# -*- mode: python ; coding: utf-8 -*-
# YO Arbitraj v1.0 — PyInstaller Build Spec
#
# Build local:   pyinstaller build/build.spec
# Build CI:      pyinstaller build/build.spec --distpath dist --workpath build/work --noconfirm

import sys
import os

# Detectare automata radacina proiectului
# Spec-ul e in build/, deci radacina e un nivel mai sus
SPEC_DIR  = os.path.dirname(os.path.abspath(SPEC))
ROOT_DIR  = os.path.dirname(SPEC_DIR)

block_cipher = None

a = Analysis(
    [os.path.join(ROOT_DIR, 'main.py')],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.scrolledtext',
        'core.contests',
        'core.parser',
        'core.validator',
        'core.crosscheck',
        'core.scorer',
        'export.reporter',
        'ui.main_window',
        'csv', 'json', 'io', 'os', 're',
        'math', 'datetime', 'collections',
        'threading', 'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy', 'pandas', 'scipy', 'matplotlib',
        'PIL', 'PyQt5', 'PyQt6', 'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YO_Arbitraj_v1.0',
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
    # icon=os.path.join(ROOT_DIR, 'assets', 'icon.ico'),
)
