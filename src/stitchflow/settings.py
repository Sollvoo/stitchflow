from pathlib import Path
from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_vite',
    'core',
    'conversions',
    'users',
]

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/conversions/'
LOGOUT_REDIRECT_URL = '/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'core.middleware.NoStoreHtmlMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stitchflow.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stitchflow.wsgi.application'

# Database — SQLite for MVP, switch to PostgreSQL via DATABASE_URL in .env
# BASE_DIR.parent = project root, keeps db.sqlite3 outside src/
DATABASE_URL = config('DATABASE_URL', default=f'sqlite:///{BASE_DIR.parent}/db.sqlite3')
DATABASES = {
    'default': {
        **dj_database_url.parse(DATABASE_URL),
        'CONN_MAX_AGE': 60,
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'frontend' / 'static',
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Media files (uploads and conversion outputs) — kept at project root
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR.parent / 'media'

# File upload limits (10 MB max)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Vite integration — manifest at src/frontend/static/dist/.vite/manifest.json
# VITE_DEV_MODE=True dans .env uniquement quand Vite dev server tourne (npm run dev)
# Par défaut False : utilise les fichiers buildés (npm run build)
DJANGO_VITE = {
    'default': {
        'dev_mode': config('VITE_DEV_MODE', default=False, cast=bool),
        'dev_server_port': 5174,
        'static_url_prefix': 'dist/',
        'manifest_path': BASE_DIR / 'frontend' / 'static' / 'dist' / '.vite' / 'manifest.json',
        'app_client_class': 'core.vite.ReloadingDjangoViteAppClient',
    }
}

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
# Windows : le prefork n'est pas supporté, forcer le pool solo
CELERY_WORKER_POOL = 'solo'

# Ink/Stitch — path to the inkstitch executable
# On macOS after installation: typically ~/.config/inkscape/extensions/inkstitch/inkstitch
# or the path configured after installing the Ink/Stitch extension
INKSTITCH_EXECUTABLE = config('INKSTITCH_EXECUTABLE', default='inkstitch')
INKSTITCH_TIMEOUT = config('INKSTITCH_TIMEOUT', default=300, cast=int)

# Poppler (pdftocairo) — chemin vers les binaires vendored (Windows)
# Fallback automatique : vendor/poppler-*/Library/bin/ si pdftocairo absent du PATH
_poppler_vendor = BASE_DIR.parent / 'vendor'
_poppler_candidates = sorted(_poppler_vendor.glob('poppler-*/Library/bin')) if _poppler_vendor.exists() else []
POPPLER_BIN_PATH: Path | None = config(
    'POPPLER_BIN_PATH',
    default=str(_poppler_candidates[-1]) if _poppler_candidates else '',
    cast=lambda v: Path(v) if v else None,
)

# Email — Gmail SMTP (configurer EMAIL_HOST_USER + EMAIL_HOST_PASSWORD dans .env)
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='StitchFlow <noreply@stitchflow.app>')
PASSWORD_RESET_TIMEOUT = 86400  # 24h

USE_CELERY = True

# Sessions — "remember me" fonctionne sur 30 jours glissants
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 jours
SESSION_SAVE_EVERY_REQUEST = False

# Cache Redis — réutilise l'infra déjà disponible pour Celery (DB 1 séparée)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Sécurité HTTPS — actif uniquement en production (DEBUG=False)
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# SVG conversion settings
SVG_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
