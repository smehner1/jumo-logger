# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller-Spec fuer JumoLogger (Windows .exe)
#
# Bauen (auf Windows oder via GitHub Actions):
#   pip install pyinstaller
#   pyinstaller jumo_logger.spec

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # eigene Module
        "logging_setup",
        "settings",
        "version",
        # tkinter -- auf Windows im Standard-Python enthalten, aber explizit angeben
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        # matplotlib
        "matplotlib.backends.backend_tkagg",
        "matplotlib.backends._backend_tk",
        # pymodbus
        "pymodbus.client",
        "pymodbus.client.tcp",
        "pymodbus.framer",
        "pymodbus.pdu",
        # openpyxl
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Qt-Backends und andere GUI-Frameworks ausschliessen -- reduziert die .exe-Groesse
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "IPython", "jupyter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="JumoLogger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=False: kein schwarzes CMD-Fenster im Hintergrund
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
