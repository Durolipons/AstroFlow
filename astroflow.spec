# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AstroFlow (Windows).

Build with::

    pyinstaller astroflow.spec --noconfirm --clean

Produces ``dist/AstroFlow/AstroFlow.exe`` (one-dir layout, which starts
faster and is more reliable with Kivy's SDL2 DLLs than one-file).

Data files: every bundled directory is resolved at runtime via
``os.path.dirname(__file__)`` (see core/ephemeris.py, astronomy/config.py,
ui/main.py), which PyInstaller maps into ``sys._MEIPASS`` -- so mirroring
the repo layout in ``datas`` below is all that is needed.

Runtime deps intentionally limited to kivy + pyswisseph + tzdata:
astropy / astroquery / jplephem / PyOpenGL are declared in
requirements.txt but are never imported anywhere in the codebase.
"""

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("ui/app.kv", "ui"),
        ("core/ephe", "core/ephe"),
        ("astronomy/data", "astronomy/data"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "PyOpenGL",
        "astropy",
        "astroquery",
        "jplephem",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AstroFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI app: no console window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AstroFlow",
)
