"""
Tests d'intégration : UnifiedUploadView, FormFragmentView.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from conversions.models import ConversionJob
from conversions.views import UnifiedUploadView

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svg_file(name="test.svg"):
    return SimpleUploadedFile(name, MINIMAL_SVG, content_type="image/svg+xml")


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_upload_view_get_returns_200(client):
    response = client.get("/conversions/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST — upload SVG valide
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_upload_svg_creates_job(client, mocker):
    mocker.patch("conversions.views._dispatch")
    f = _svg_file()
    response = client.post("/conversions/", {"original_file": f}, follow=False)
    assert response.status_code == 302
    assert ConversionJob.objects.count() == 1
    job = ConversionJob.objects.first()
    assert job.status == ConversionJob.Status.PENDING
    assert job.source_format == "svg"


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_upload_svg_sets_original_filename(client, mocker):
    mocker.patch("conversions.views._dispatch")
    f = _svg_file("mon_design_broderie.svg")
    client.post("/conversions/", {"original_file": f}, follow=False)
    job = ConversionJob.objects.first()
    assert job.original_filename == "mon_design_broderie"


# ---------------------------------------------------------------------------
# _detect_format — détection par magic bytes
# ---------------------------------------------------------------------------


def test_detect_format_png_magic():
    from io import BytesIO
    from django.core.files import File
    data = b"\x89PNG\r\n\x1a\nSOMEDATA"
    f = File(BytesIO(data), name="img.png")
    assert UnifiedUploadView._detect_format(f) == "png"


def test_detect_format_pdf_magic():
    from io import BytesIO
    from django.core.files import File
    data = b"%PDF-1.4 some pdf content"
    f = File(BytesIO(data), name="doc.pdf")
    assert UnifiedUploadView._detect_format(f) == "pdf"


def test_detect_format_jpeg_magic():
    from io import BytesIO
    from django.core.files import File
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    f = File(BytesIO(data), name="photo.jpg")
    assert UnifiedUploadView._detect_format(f) == "jpeg"


def test_detect_format_svg_by_content():
    from io import BytesIO
    from django.core.files import File
    data = MINIMAL_SVG
    f = File(BytesIO(data), name="drawing.svg")
    assert UnifiedUploadView._detect_format(f) == "svg"


def test_detect_format_xml_header_svg():
    from io import BytesIO
    from django.core.files import File
    data = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
    f = File(BytesIO(data), name="drawing.svg")
    assert UnifiedUploadView._detect_format(f) == "svg"


def test_detect_format_unknown_extension_fallback():
    from io import BytesIO
    from django.core.files import File
    data = b"UNKNOWN FORMAT DATA UNKNOWN FORMAT DATA UNKNOWN FORMAT DATA"
    f = File(BytesIO(data), name="file.xyz")
    fmt = UnifiedUploadView._detect_format(f)
    assert fmt == "unknown"


def test_detect_format_webp_magic():
    from io import BytesIO
    from django.core.files import File
    data = b"RIFF\x00\x00\x00\x00WEBP"
    f = File(BytesIO(data), name="img.webp")
    assert UnifiedUploadView._detect_format(f) == "webp"


# ---------------------------------------------------------------------------
# POST — excluded_colors parsing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_excluded_colors_valid_stored(client, mocker):
    mocker.patch("conversions.views._dispatch")
    f = _svg_file()
    client.post(
        "/conversions/",
        {"original_file": f, "excluded_colors": "#ff0000,#00ff00"},
        follow=False,
    )
    job = ConversionJob.objects.order_by("-created_at").first()
    colors = (job.conversion_metadata or {}).get("excluded_colors", "")
    assert "#ff0000" in colors
    assert "#00ff00" in colors


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_excluded_colors_over_200_chars_ignored(client, mocker):
    mocker.patch("conversions.views._dispatch")
    f = _svg_file()
    long_colors = ",".join(["#ff0000"] * 50)  # >> 200 chars
    client.post(
        "/conversions/",
        {"original_file": f, "excluded_colors": long_colors},
        follow=False,
    )
    job = ConversionJob.objects.order_by("-created_at").first()
    colors = (job.conversion_metadata or {}).get("excluded_colors", "")
    assert colors == ""


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_excluded_colors_invalid_hex_filtered(client, mocker):
    mocker.patch("conversions.views._dispatch")
    f = _svg_file()
    client.post(
        "/conversions/",
        {"original_file": f, "excluded_colors": "#ff0000,#GGHH00,notahex"},
        follow=False,
    )
    job = ConversionJob.objects.order_by("-created_at").first()
    colors = (job.conversion_metadata or {}).get("excluded_colors", "")
    assert "#GGHH00" not in colors
    assert "notahex" not in colors


# ---------------------------------------------------------------------------
# POST — sans fichier
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_upload_no_file_returns_error(client):
    response = client.post("/conversions/", {})
    assert response.status_code == 200
    assert ConversionJob.objects.count() == 0


# ---------------------------------------------------------------------------
# FormFragmentView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_fragment_svg(client):
    response = client.get("/conversions/form/svg/")
    assert response.status_code == 200
    assert b"form" in response.content.lower()


@pytest.mark.django_db
def test_form_fragment_png(client):
    response = client.get("/conversions/form/png/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_form_fragment_unknown(client):
    response = client.get("/conversions/form/xyz/")
    assert response.status_code == 200
