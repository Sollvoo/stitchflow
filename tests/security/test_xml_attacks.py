"""
Tests de sécurité : attaques XML (XXE, billion laughs) bloquées par defusedxml.
"""
import io

import pytest
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings

from conversions.services.validation import (
    SVGValidationError,
    validate_svg_structure,
)


XXE_PAYLOAD = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z">&xxe;</path>
</svg>"""

BILLION_LAUGHS = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ff0000" d="&lol4;"/></svg>"""

VALID_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'


# ---------------------------------------------------------------------------
# validate_svg_structure — bloque les attaques XML
# ---------------------------------------------------------------------------


def test_xxe_blocked_by_validate_svg_structure(tmp_path):
    """SVG avec entité SYSTEM → ValidationError (defusedxml bloque le DTD)."""
    svg = tmp_path / "xxe.svg"
    svg.write_bytes(XXE_PAYLOAD)
    with pytest.raises((ValidationError, Exception)) as exc_info:
        validate_svg_structure(svg)
    # defusedxml lève DTDForbidden, ParseError, ou similaire → capturé comme ValidationError
    # On vérifie juste que ça n'a pas réussi silencieusement
    assert exc_info.value is not None


def test_billion_laughs_blocked(tmp_path):
    """SVG billion laughs → levée d'exception (DTD interdit)."""
    svg = tmp_path / "bilion.svg"
    svg.write_bytes(BILLION_LAUGHS)
    with pytest.raises((ValidationError, Exception)):
        validate_svg_structure(svg)


def test_valid_svg_accepted(tmp_path):
    """SVG normal sans DOCTYPE → validé sans problème."""
    svg = tmp_path / "ok.svg"
    svg.write_bytes(VALID_SVG)
    validate_svg_structure(svg)  # ne doit pas lever


# ---------------------------------------------------------------------------
# AnalyzeSVGView — attaque XXE via POST HTTP
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_analyze_svg_view_xxe_no_crash(client):
    """POST avec SVG XXE → ne doit pas retourner 500 ni exposer /etc/passwd."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    f = SimpleUploadedFile("evil.svg", XXE_PAYLOAD, content_type="image/svg+xml")
    response = client.post(
        "/conversions/analyze-svg/",
        {"original_file": f},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code in (200, 429)
    content = response.content.decode(errors="ignore")
    # Ne doit pas exposer le contenu de /etc/passwd ou un traceback Python
    assert "root:x:0:" not in content
    assert "Traceback" not in content


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_analyze_svg_view_billion_laughs_no_crash(client):
    """POST avec billion laughs → réponse vide ou 200, jamais 500."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    f = SimpleUploadedFile("laughs.svg", BILLION_LAUGHS, content_type="image/svg+xml")
    response = client.post(
        "/conversions/analyze-svg/",
        {"original_file": f},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code in (200, 429)


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_analyze_svg_view_valid_svg(client):
    """POST avec SVG valide → réponse HTML (fragment suggestions) ou vide."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    f = SimpleUploadedFile("valid.svg", VALID_SVG, content_type="image/svg+xml")
    response = client.post(
        "/conversions/analyze-svg/",
        {"original_file": f},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code in (200, 429)
