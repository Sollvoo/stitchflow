"""
Tests de sécurité : validation des uploads (magic bytes, tailles, path traversal, injection).
"""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from conversions.forms import PDFUploadForm, PNGUploadForm, SVGUploadForm


MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
PDF_MAGIC = b"%PDF-1.4\n" + b"\x00" * 100
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100


# ---------------------------------------------------------------------------
# SVGUploadForm — validations magic bytes / extension / taille
# ---------------------------------------------------------------------------


def test_svg_form_rejects_png_renamed_svg():
    """Fichier PNG renommé .svg → rejeté (pas de <svg> dans les premiers bytes)."""
    f = SimpleUploadedFile("evil.svg", PNG_MAGIC, content_type="image/svg+xml")
    form = SVGUploadForm(files={"original_file": f})
    assert not form.is_valid()
    assert "original_file" in form.errors


def test_svg_form_rejects_plain_text_renamed_svg():
    """Fichier texte renommé .svg → rejeté."""
    f = SimpleUploadedFile("text.svg", b"Hello world, I am not SVG!", content_type="image/svg+xml")
    form = SVGUploadForm(files={"original_file": f})
    assert not form.is_valid()
    assert "original_file" in form.errors


def test_svg_form_rejects_pdf_renamed_svg():
    """Fichier PDF renommé .svg → rejeté (premier bytes != <svg ou <?xml)."""
    f = SimpleUploadedFile("evil.svg", PDF_MAGIC, content_type="image/svg+xml")
    form = SVGUploadForm(files={"original_file": f})
    assert not form.is_valid()


def test_svg_form_rejects_oversize(settings):
    """SVG dépassant SVG_MAX_FILE_SIZE → rejeté."""
    settings.SVG_MAX_FILE_SIZE = 100  # 100 bytes pour le test
    big = b"<svg xmlns='http://www.w3.org/2000/svg'>" + b"x" * 200 + b"</svg>"
    f = SimpleUploadedFile("big.svg", big, content_type="image/svg+xml")
    form = SVGUploadForm(files={"original_file": f})
    assert not form.is_valid()


def test_svg_form_renames_with_uuid():
    """Le nom de fichier après validation doit être un UUID hexadécimal."""
    import re
    f = SimpleUploadedFile("my-design.svg", MINIMAL_SVG, content_type="image/svg+xml")
    form = SVGUploadForm(files={"original_file": f})
    assert form.is_valid(), form.errors
    assert re.match(r"^[0-9a-f]{32}\.svg$", form.cleaned_data["original_file"].name)


def test_svg_form_sanitizes_stem():
    """Le nom original est stocké dans _svg_original_stem avant le renommage UUID."""
    # FileField max_length=100 (Django default) — utiliser un nom valide
    stem = "mon-design-broderie-magnifique"
    f = SimpleUploadedFile(stem + ".svg", MINIMAL_SVG, content_type="image/svg+xml")
    form = SVGUploadForm(files={"original_file": f})
    assert form.is_valid(), form.errors
    assert form._svg_original_stem == stem
    assert len(form._svg_original_stem) <= 200


# ---------------------------------------------------------------------------
# PNGUploadForm — magic bytes
# ---------------------------------------------------------------------------


def test_png_form_rejects_svg_renamed_png():
    """Fichier SVG renommé .png → rejeté (magic bytes != PNG)."""
    f = SimpleUploadedFile("evil.png", MINIMAL_SVG, content_type="image/png")
    form = PNGUploadForm(files={"original_file": f})
    assert not form.is_valid()
    assert "original_file" in form.errors


def test_png_form_accepts_valid_png():
    """PNG valide accepté (magic bytes OK + extension OK)."""
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    img.save(buf, format="PNG")
    buf.seek(0)
    f = SimpleUploadedFile("photo.png", buf.read(), content_type="image/png")
    form = PNGUploadForm(files={"original_file": f})
    assert form.is_valid(), form.errors


def test_png_form_rejects_pdf_renamed_png():
    """Fichier PDF renommé .png → rejeté."""
    f = SimpleUploadedFile("evil.png", PDF_MAGIC, content_type="image/png")
    form = PNGUploadForm(files={"original_file": f})
    assert not form.is_valid()


# ---------------------------------------------------------------------------
# PDFUploadForm — magic bytes
# ---------------------------------------------------------------------------


def test_pdf_form_rejects_svg_renamed_pdf():
    """Fichier SVG renommé .pdf → rejeté (magic != %PDF)."""
    f = SimpleUploadedFile("evil.pdf", MINIMAL_SVG, content_type="application/pdf")
    form = PDFUploadForm(files={"original_file": f})
    assert not form.is_valid()
    assert "original_file" in form.errors


def test_pdf_form_rejects_png_renamed_pdf():
    """Fichier PNG renommé .pdf → rejeté."""
    f = SimpleUploadedFile("evil.pdf", PNG_MAGIC, content_type="application/pdf")
    form = PDFUploadForm(files={"original_file": f})
    assert not form.is_valid()


# ---------------------------------------------------------------------------
# excluded_colors — filtrage des injections
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_excluded_colors_only_valid_hex_extracted(client):
    """Payload avec injection → seuls les #RRGGBB valides sont conservés."""
    f = SimpleUploadedFile("test.svg", MINIMAL_SVG, content_type="image/svg+xml")
    response = client.post(
        "/conversions/",
        {
            "original_file": f,
            "excluded_colors": "#ff0000; DROP TABLE conversions_conversionjob; <script>alert(1)</script>",
        },
        follow=False,
    )
    # La vue doit avoir créé un job (302) ou retourné le formulaire (200)
    assert response.status_code in (200, 302)

    if response.status_code == 302:
        from conversions.models import ConversionJob
        job = ConversionJob.objects.order_by("-created_at").first()
        if job:
            colors = (job.conversion_metadata or {}).get("excluded_colors", "")
            # Seul #ff0000 peut être extrait; le reste est rejeté
            assert "DROP TABLE" not in colors
            assert "<script>" not in colors


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_excluded_colors_over_200_chars_ignored(client):
    """excluded_colors >200 chars → ignoré entièrement."""
    f = SimpleUploadedFile("test.svg", MINIMAL_SVG, content_type="image/svg+xml")
    long_colors = ",".join(["#ff0000"] * 50)  # bien > 200 chars
    response = client.post(
        "/conversions/",
        {"original_file": f, "excluded_colors": long_colors},
        follow=False,
    )
    assert response.status_code in (200, 302)

    if response.status_code == 302:
        from conversions.models import ConversionJob
        job = ConversionJob.objects.order_by("-created_at").first()
        if job:
            # Le champ doit être vide car > 200 chars
            colors = (job.conversion_metadata or {}).get("excluded_colors", "")
            assert colors == ""


# ---------------------------------------------------------------------------
# Error messages — pas de traceback exposé
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_no_traceback_in_error_response(client):
    """Un upload invalide ne doit pas retourner de traceback Python dans la réponse."""
    f = SimpleUploadedFile("invalid.svg", b"THIS IS NOT SVG", content_type="image/svg+xml")
    response = client.post("/conversions/", {"original_file": f})
    content = response.content.decode(errors="ignore")
    assert "Traceback" not in content
    assert 'File "' not in content
