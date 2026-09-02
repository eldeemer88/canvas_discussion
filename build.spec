# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec, shared by the macOS and Windows builds."""

import sys

APP_NAME = "Canvas Discussion Grader" if sys.platform == "darwin" else "CanvasDiscussionGrader"

# Pulled in transitively but never used; each one is tens of MB.
EXCLUDES = [
    "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "IPython", "jupyter", "notebook", "pytest", "sphinx",
    "scipy", "sqlalchemy", "PIL.ImageQt", "gunicorn",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_webagg",
]

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=[],
    datas=[("static", "static")],   # served by Flask from sys._MEIPASS
    hiddenimports=[
        "waitress", "openpyxl.cell._writer",
        "matplotlib.backends.backend_agg",
        "pandas._libs.tslibs.base",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,          # UPX trips antivirus heuristics on Windows
    console=sys.platform != "darwin",   # .app has no terminal; Windows keeps one
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="edu.pitt.ta.canvasdiscussiongrader",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSBackgroundOnly": False,
        },
    )
