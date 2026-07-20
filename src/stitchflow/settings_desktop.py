"""
Settings desktop — overrides de settings.py pour l'app Electron.

Importé via DJANGO_SETTINGS_MODULE=stitchflow.settings_desktop
Electron passe les variables d'environnement :
  - STITCH_USERDATA  : app.getPath('userData') → stockage SQLite + media
  - STITCH_VENDOR_PATH : chemin vers vendor/ bundlé dans le .app
  - STITCH_PORT      : port Django (détecté automatiquement par Electron)
"""
import os
import sys
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'stitchflow-desktop-local-only-key-not-a-secret')

from .settings import *  # noqa: F401,F403

# ── Chemins desktop ───────────────────────────────────────────────────────────

_USERDATA = Path(os.environ.get('STITCH_USERDATA', Path.home() / 'Library' / 'Application Support' / 'StitchFlow'))
_USERDATA.mkdir(parents=True, exist_ok=True)

_VENDOR = Path(os.environ.get('STITCH_VENDOR_PATH', BASE_DIR.parent / 'vendor'))  # noqa: F405

# ── Django core ───────────────────────────────────────────────────────────────

DEBUG = True
SECRET_KEY = 'stitchflow-desktop-local-only-key-not-a-secret'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '::1', 'stitchflow.localhost']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False

# Email desktop : console par défaut, SMTP réel si variables fournies.
_EMAIL_HOST_USER = os.environ.get('STITCH_EMAIL_HOST_USER') or os.environ.get('EMAIL_HOST_USER', '')
_EMAIL_HOST_PASSWORD = os.environ.get('STITCH_EMAIL_HOST_PASSWORD') or os.environ.get('EMAIL_HOST_PASSWORD', '')
if _EMAIL_HOST_USER and _EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('STITCH_EMAIL_HOST') or os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('STITCH_EMAIL_PORT') or os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = (
        os.environ.get('STITCH_EMAIL_USE_TLS') or os.environ.get('EMAIL_USE_TLS', 'true')
    ).lower() in ('1', 'true', 'yes', 'on')
    EMAIL_HOST_USER = _EMAIL_HOST_USER
    EMAIL_HOST_PASSWORD = _EMAIL_HOST_PASSWORD
    DEFAULT_FROM_EMAIL = os.environ.get('STITCH_DEFAULT_FROM_EMAIL') or os.environ.get(
        'DEFAULT_FROM_EMAIL',
        f'StitchFlow <{_EMAIL_HOST_USER}>',
    )
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Base de données dans userData ─────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': _USERDATA / 'db.sqlite3',
    }
}

# ── Media dans userData ───────────────────────────────────────────────────────

MEDIA_ROOT = _USERDATA / 'media'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# ── Celery supprimé (remplacé par threading.Thread) ───────────────────────────
# Retirer les apps Celery pour éviter les erreurs d'import

INSTALLED_APPS = [app for app in INSTALLED_APPS if 'celery' not in app.lower()]  # noqa: F405

USE_CELERY = False
DESKTOP_MODE = True
DESKTOP_PENDING_TIMEOUT_SECONDS = int(os.environ.get('DESKTOP_PENDING_TIMEOUT_SECONDS', '90'))

# Cache en mémoire locale — Redis non disponible en mode desktop
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_SAVE_EVERY_REQUEST = True

# ── Vite — toujours en mode production (assets pré-buildés) ──────────────────

DJANGO_VITE = {
    'default': {
        'dev_mode': False,
        'static_url_prefix': 'dist/',
        'manifest_path': BASE_DIR / 'frontend' / 'static' / 'dist' / '.vite' / 'manifest.json',  # noqa: F405
        'app_client_class': 'core.vite.ReloadingDjangoViteAppClient',
    }
}

# ── Ink/Stitch — détection automatique selon OS ──────────────────────────────

def _find_inkstitch() -> str:
    """Cherche inkstitch dans les emplacements standards de chaque OS."""
    import shutil as _shutil

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
        appdata = Path(os.environ.get('APPDATA', ''))
        candidates = [
            appdata / 'inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe',
            appdata / 'inkscape/extensions/inkstitch/bin/inkstitch.exe',
            Path('C:/Program Files/Inkscape/share/inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe'),
        ]

    for p in candidates:
        if p.exists():
            return str(p)

    # Fallback : chercher dans le PATH
    found = _shutil.which('inkstitch')
    return found or 'inkstitch'


INKSTITCH_EXECUTABLE = os.environ.get('INKSTITCH_EXECUTABLE', _find_inkstitch())
INKSTITCH_TIMEOUT = 300

# ── VTracer vendorisé ─────────────────────────────────────────────────────────

import platform as _platform
_arch = _platform.machine().lower()

if sys.platform == 'darwin':
    _vtracer_bin = _VENDOR / 'vtracer'
elif sys.platform == 'win32':
    _vtracer_bin = _VENDOR / 'vtracer.exe'
else:
    _vtracer_bin = _VENDOR / 'vtracer'

if _vtracer_bin.exists():
    os.environ.setdefault('VTRACER_EXECUTABLE', str(_vtracer_bin))

# ── Poppler vendorisé ─────────────────────────────────────────────────────────

def _find_poppler_bin_path() -> Path | None:
    import shutil as _shutil2

    if sys.platform == 'darwin':
        versioned_bins = sorted(_VENDOR.glob('poppler-*/bin')) if _VENDOR.exists() else []
        vendor_candidates = [
            _VENDOR / 'poppler-macos' / 'bin',
            *versioned_bins,
        ]
        for candidate in vendor_candidates:
            if (candidate / 'pdftocairo').exists():
                return candidate
        _pdftocairo = _shutil2.which('pdftocairo')
        return Path(_pdftocairo).parent if _pdftocairo else None

    if sys.platform == 'win32':
        vendor_candidates = sorted(_VENDOR.glob('poppler-*/Library/bin')) if _VENDOR.exists() else []
        for candidate in vendor_candidates:
            if (candidate / 'pdftocairo.exe').exists():
                return candidate

    return None


POPPLER_BIN_PATH = _find_poppler_bin_path()

# ── Logs ──────────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(_USERDATA / 'stitchflow.log'),
            'formatter': 'simple',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'formatters': {
        'simple': {'format': '%(levelname)s %(name)s: %(message)s'},
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'conversions': {'level': 'DEBUG', 'propagate': True},
    },
}
