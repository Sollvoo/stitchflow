"""
Tests de rate limiting : UnifiedUploadView (10/min) et Analyze*View (30/min).
Requiert RatelimitMiddleware pour convertir Ratelimited → 429.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x11\x00\x01]\x85U(\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _ratelimit_settings(settings, location: str):
    """Configure les settings pour activer le rate limiting dans les tests."""
    settings.RATELIMIT_ENABLE = True
    settings.RATELIMIT_USE_CACHE = "default"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": location,
        }
    }
    # RatelimitMiddleware convertit Ratelimited → 429
    mw = list(settings.MIDDLEWARE)
    if "django_ratelimit.middleware.RatelimitMiddleware" not in mw:
        mw.insert(0, "django_ratelimit.middleware.RatelimitMiddleware")
    settings.MIDDLEWARE = mw


@pytest.mark.django_db
def test_upload_rate_limit_triggered_on_11th_request(settings):
    """UnifiedUploadView : 10 requêtes/min par IP, la 11e doit retourner 429."""
    _ratelimit_settings(settings, "ratelimit-upload")
    client = Client(REMOTE_ADDR="192.168.1.1")
    for i in range(10):
        f = SimpleUploadedFile(f"file{i}.svg", MINIMAL_SVG, content_type="image/svg+xml")
        response = client.post(
            "/conversions/",
            {"original_file": f},
            REMOTE_ADDR="192.168.1.1",
        )
        assert response.status_code != 429, f"429 inattendu à la requête {i + 1}"

    f = SimpleUploadedFile("file11.svg", MINIMAL_SVG, content_type="image/svg+xml")
    response = client.post(
        "/conversions/",
        {"original_file": f},
        REMOTE_ADDR="192.168.1.1",
    )
    assert response.status_code == 429


@pytest.mark.django_db
def test_analyze_svg_rate_limit_triggered_on_31st_request(settings):
    """AnalyzeSVGView : 30 requêtes/min, la 31e doit retourner 429."""
    _ratelimit_settings(settings, "ratelimit-analyzesvg")
    client = Client(REMOTE_ADDR="192.168.2.1")
    for i in range(30):
        f = SimpleUploadedFile(f"svg{i}.svg", MINIMAL_SVG, content_type="image/svg+xml")
        response = client.post(
            "/conversions/analyze-svg/",
            {"original_file": f},
            REMOTE_ADDR="192.168.2.1",
        )
        assert response.status_code != 429, f"429 inattendu à la requête {i + 1}"

    f = SimpleUploadedFile("svg31.svg", MINIMAL_SVG, content_type="image/svg+xml")
    response = client.post(
        "/conversions/analyze-svg/",
        {"original_file": f},
        REMOTE_ADDR="192.168.2.1",
    )
    assert response.status_code == 429


@pytest.mark.django_db
def test_analyze_png_rate_limit_triggered_on_31st_request(settings):
    """AnalyzePNGView : 30 requêtes/min, la 31e doit retourner 429."""
    _ratelimit_settings(settings, "ratelimit-analyzepng")
    client = Client(REMOTE_ADDR="192.168.3.1")
    for i in range(30):
        f = SimpleUploadedFile(f"img{i}.png", MINIMAL_PNG, content_type="image/png")
        response = client.post(
            "/conversions/analyze-png/",
            {"original_file": f},
            REMOTE_ADDR="192.168.3.1",
        )
        assert response.status_code != 429, f"429 inattendu à la requête {i + 1}"

    f = SimpleUploadedFile("img31.png", MINIMAL_PNG, content_type="image/png")
    response = client.post(
        "/conversions/analyze-png/",
        {"original_file": f},
        REMOTE_ADDR="192.168.3.1",
    )
    assert response.status_code == 429
