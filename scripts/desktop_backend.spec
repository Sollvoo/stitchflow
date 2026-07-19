# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


def _runtime_module(name):
    return ".tests" not in name and not name.endswith(".tests")


datas = []
for package_dir in ("stitchflow", "conversions", "core", "users"):
    datas += [(f"../src/{package_dir}", f"src/{package_dir}")]
for package in ("conversions", "core", "users"):
    datas += collect_data_files(package, includes=["templates/**/*", "static/**/*", "migrations/*.py"])
datas += [("../src/frontend/static/dist", "src/frontend/static/dist")]

hiddenimports = []
hiddenimports += [
    "decouple",
    "dj_database_url",
    "pdf2image",
    "PIL",
    "PIL.Image",
    "PIL.ImageEnhance",
    "PIL.ImageFilter",
    "PIL.ImageOps",
    "numpy",
    "pyembroidery",
    "vtracer",
]
for package in (
    "conversions",
    "core",
    "users",
    "stitchflow",
    "storages",
    "django_vite",
    "django_ratelimit",
    "whitenoise",
):
    hiddenimports += collect_submodules(package, filter=_runtime_module)


a = Analysis(
    ["desktop_backend.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["celery", "redis", "gunicorn", "pytest", "black", "ruff"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name="stitchflow-backend",
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="stitchflow-backend",
)
