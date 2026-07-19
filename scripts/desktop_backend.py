#!/usr/bin/env python3
"""Desktop backend entrypoint used by Electron and PyInstaller.

The packaged Electron app must not depend on a user-installed Python. PyInstaller
freezes this file into a small command runner that can migrate, check, run
Django, and report external dependency status.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def _bootstrap_paths() -> None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    src = root / "src"
    if src.exists():
        sys.path.insert(0, str(src))


def _configure_env() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stitchflow.settings_desktop")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")


def _execute_django(argv: list[str]) -> None:
    _bootstrap_paths()
    _configure_env()
    from django.core.management import execute_from_command_line

    execute_from_command_line(["stitchflow-backend", *argv])


def _check_inkstitch() -> dict:
    candidates: list[Path] = []
    if sys.platform == "darwin":
        lib_inkscape = (
            Path.home()
            / "Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/inkstitch"
        )
        candidates = [
            lib_inkscape / "inkstitch.app/Contents/MacOS/inkstitch",
            lib_inkscape / "inkstitch",
            Path.home() / ".config/inkscape/extensions/inkstitch/inkstitch",
            Path("/Applications/Inkscape.app/Contents/Resources/share/inkscape/extensions/inkstitch/inkstitch"),
        ]
    elif sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", ""))
        candidates = [
            appdata / "inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe",
            appdata / "inkscape/extensions/inkstitch/bin/inkstitch.exe",
            Path("C:/Program Files/Inkscape/share/inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe"),
        ]

    for candidate in candidates:
        if candidate.exists():
            return {"found": True, "path": str(candidate)}

    found = shutil.which("inkstitch")
    if found:
        return {"found": True, "path": found}

    return {
        "found": False,
        "install_url": "https://inkstitch.org/docs/install/",
        "message": "Ink/Stitch introuvable. Installez Inkscape puis l'extension Ink/Stitch.",
    }


def _check_poppler() -> dict:
    vendor = Path(os.environ.get("STITCH_VENDOR_PATH", "vendor"))
    vendor_candidates = sorted(vendor.glob("poppler-*/Library/bin/pdftocairo*"))
    if vendor_candidates:
        return {"found": True, "path": str(vendor_candidates[-1])}

    found = shutil.which("pdftocairo")
    if found:
        return {"found": True, "path": found}

    return {
        "found": False,
        "message": "Poppler (pdftocairo) introuvable. PDF non supporté sans Poppler.",
        "optional": True,
    }


def _check_python() -> dict:
    version = sys.version_info
    return {
        "found": True,
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
    }


def _print_deps() -> int:
    results = {
        "python": _check_python(),
        "inkstitch": _check_inkstitch(),
        "poppler": _check_poppler(),
    }
    print(json.dumps(results, indent=2))
    return 1 if not results["inkstitch"]["found"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the StitchFlow desktop Django backend.")
    parser.add_argument("--check-deps", action="store_true", help="Print desktop dependency status as JSON.")
    parser.add_argument("--migrate", action="store_true", help="Run Django migrations.")
    parser.add_argument("--check", action="store_true", help="Run Django system checks.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for runserver.")
    parser.add_argument("--port", type=int, help="Port for runserver.")
    args = parser.parse_args()

    if args.check_deps:
        return _print_deps()
    if args.migrate:
        _execute_django(["migrate", "--run-syncdb", "--noinput"])
        return 0
    if args.check:
        _execute_django(["check"])
        return 0
    if not args.port:
        parser.error("--port is required unless --check-deps, --migrate, or --check is used")

    _execute_django(["runserver", f"{args.host}:{args.port}", "--noreload"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
