"""
Script de vérification des dépendances au démarrage.
Appelé par Electron main.js avant de démarrer Django.
Retourne un JSON avec le statut de chaque dépendance.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def check_inkstitch() -> dict:
    """Vérifie qu'Ink/Stitch est installé et fonctionnel."""
    candidates = []
    if sys.platform == 'darwin':
        candidates = [
            Path.home() / '.config/inkscape/extensions/inkstitch/inkstitch',
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
        'install_url': 'https://inkstitch.org/docs/install/',
        'message': (
            'Ink/Stitch introuvable. Installez Inkscape puis l\'extension Ink/Stitch '
            'depuis https://inkstitch.org'
        ),
    }


def check_poppler() -> dict:
    """Vérifie que pdftocairo (Poppler) est disponible."""
    found = shutil.which('pdftocairo')
    if found:
        return {'found': True, 'path': found}

    # Chercher dans vendor/
    script_dir = Path(__file__).parent.parent
    vendor_candidates = sorted(script_dir.glob('vendor/poppler-*/Library/bin/pdftocairo*'))
    if vendor_candidates:
        return {'found': True, 'path': str(vendor_candidates[-1])}

    return {
        'found': False,
        'message': 'Poppler (pdftocairo) introuvable. PDF non supporté sans Poppler.',
        'optional': True,
    }


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
    }
    print(json.dumps(results, indent=2))
    # Exit code 1 si une dépendance critique manque
    critical_missing = not results['python']['found'] or not results['inkstitch']['found']
    sys.exit(1 if critical_missing else 0)
