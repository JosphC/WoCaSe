# -*- mode: python ; coding: utf-8 -*-

import os

_HERE = os.path.abspath(SPECPATH)
_ASSETS = os.path.join(_HERE, "wcs_modules", "assets")

a = Analysis(
    [os.path.join(_HERE, 'wcs_qt.py')],          # correct entry point
    pathex=[_HERE],                                # so 'wcs_modules' is found
    binaries=[],
    datas=[
        (_ASSETS, 'wcs_modules/assets'),           # bundle all icons/images
    ],
    hiddenimports=[
        'wcs_modules',
        'wcs_modules.qt_ui',
        'wcs_modules.main',
        'wcs_modules.logging_config',
        'wcs_modules.path_utils',
        'wcs_modules.td5_builder',
        'wcs_modules.arxml_processor',
        'wcs_modules.code_modifier',
        'wcs_modules.file_generator',
        'wcs_modules.gpt_detector',
        'wcs_modules.tdcl_modifier',
        'wcs_modules.templates',
        'wcs_modules.xml_modifier',
        'wcs_modules.simulator_bridge',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',
    ],
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
    name='WoCaSe',
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
    icon=[os.path.join(_ASSETS, 'lego.ico')],
)
