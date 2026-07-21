"""
Script de vérification des dépendances au démarrage.
Appelé par Electron main.js avant de démarrer Django.
Retourne un JSON avec le statut de chaque dépendance.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_inkstitch() -> dict:
    """Vérifie qu'Ink/Stitch est installé et fonctionnel."""
    candidates = []
    if sys.platform == 'darwin':
        _lib_inkscape = Path.home() / 'Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/inkstitch'
        candidates = [
            # Inkscape .app sandboxé (installation standard macOS)
            _lib_inkscape / 'inkstitch.app/Contents/MacOS/inkstitch',
            _lib_inkscape / 'inkstitch',
            # Inkscape legacy ~/.config
            Path.home() / '.config/inkscape/extensions/inkstitch/inkstitch',
            # Inkscape dans /Applications
            Path('/Applications/Inkscape.app/Contents/Resources/share/inkscape/extensions/inkstitch/inkstitch'),
        ]
    elif sys.platform == 'win32':
        import os
        appdata = Path(os.environ.get('APPDATA', ''))
        candidates = [
            appdata / 'inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe',
            appdata / 'inkscape/extensions/inkstitch/bin/inkstitch.exe',
        ]

    for p in candidates:
        if p.exists():
            return {'found': True, 'path': str(p)}

    found = shutil.which('inkstitch')
    if found:
        return {'found': True, 'path': found}

    return {
        'found': False,
        'install_url': 'https://sollvoo.github.io/stitchflow/#prerequis',
        'message': (
            'Ink/Stitch introuvable. Installez Inkscape, ouvrez-le une première fois, '
            'puis installez Ink/Stitch depuis le guide StitchFlow.'
        ),
    }


def check_poppler() -> dict:
    """Vérifie que pdftocairo (Poppler) est disponible."""
    found = shutil.which('pdftocairo')
    if found:
        return {'found': True, 'path': found}

    script_dir = Path(__file__).parent.parent
    vendor = Path(os.environ.get('STITCH_VENDOR_PATH', script_dir / 'vendor'))
    if sys.platform == 'darwin':
        vendor_candidates = [
            vendor / 'poppler-macos' / 'bin' / 'pdftocairo',
            *sorted(vendor.glob('poppler-*/bin/pdftocairo')),
        ]
    elif sys.platform == 'win32':
        vendor_candidates = sorted(vendor.glob('poppler-*/Library/bin/pdftocairo.exe'))
    else:
        vendor_candidates = sorted(vendor.glob('poppler-*/bin/pdftocairo'))

    for candidate in vendor_candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return {'found': True, 'path': str(candidate)}

    return {
        'found': False,
        'message': 'Poppler (pdftocairo) introuvable. PDF non supporté sans Poppler.',
        'required_for': ['pdf_preview', 'pdf_conversion'],
        'optional': False,
    }


def check_pdf2image() -> dict:
    """Vérifie que pdf2image est disponible pour preview/conversion PDF."""
    try:
        import pdf2image  # noqa: F401
    except Exception as exc:
        return {
            'found': False,
            'message': f'pdf2image introuvable. PDF non supporté sans ce module Python : {exc}',
            'required_for': ['pdf_preview', 'pdf_conversion'],
            'optional': False,
        }
    return {'found': True}


def check_python() -> dict:
    """Vérifie la version Python."""
    version = sys.version_info
    ok = version >= (3, 11)
    return {
        'found': ok,
        'version': f'{version.major}.{version.minor}.{version.micro}',
        'message': None if ok else f'Python 3.11+ requis, trouvé {version.major}.{version.minor}',
    }


if __name__ == '__main__':
    results = {
        'python': check_python(),
        'inkstitch': check_inkstitch(),
        'poppler': check_poppler(),
        'pdf2image': check_pdf2image(),
    }
    print(json.dumps(results, indent=2))
    # Exit code 1 si une dépendance critique manque
    critical_missing = not results['python']['found'] or not results['inkstitch']['found']
    sys.exit(1 if critical_missing else 0)
