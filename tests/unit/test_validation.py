"""
Tests unitaires pour conversions/services/validation.py
"""
import pytest
from django.core.exceptions import ValidationError

from conversions.services.validation import (
    SVGValidationError,
    validate_svg_content,
    validate_svg_structure,
)


# ---------------------------------------------------------------------------
# validate_svg_structure
# ---------------------------------------------------------------------------


def test_validate_structure_valid_svg(tmp_svg_file):
    validate_svg_structure(tmp_svg_file)  # ne doit pas lever


def test_validate_structure_malformed_xml(tmp_path):
    f = tmp_path / "bad.svg"
    f.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'><path UNCLOSED")
    with pytest.raises(ValidationError, match="SVG invalide"):
        validate_svg_structure(f)


def test_validate_structure_not_svg_root(tmp_path):
    f = tmp_path / "nosvg.xml"
    f.write_bytes(b'<?xml version="1.0"?><root><child/></root>')
    with pytest.raises(ValidationError, match="élément SVG valide"):
        validate_svg_structure(f)


def test_validate_structure_namespaced_svg(tmp_path):
    f = tmp_path / "ns.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm">'
        b'<path fill="#ff0000" d="M0 0 L1 0 L1 1 Z"/></svg>'
    )
    validate_svg_structure(f)  # ne doit pas lever


def test_validate_structure_accepts_html_like_svg(tmp_path):
    """Un SVG sans déclaration XML mais avec balise <svg> doit être accepté."""
    f = tmp_path / "plain.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<path fill="#abc123" d="M0 0 L5 0 L5 5 Z"/></svg>'
    )
    validate_svg_structure(f)


# ---------------------------------------------------------------------------
# validate_svg_content — dimensions nulles
# ---------------------------------------------------------------------------


def test_validate_content_valid_svg(tmp_svg_file):
    validate_svg_content(tmp_svg_file)  # ne doit pas lever


def test_validate_content_zero_width_mm(tmp_zero_width_svg):
    with pytest.raises(SVGValidationError, match="dimension nulle"):
        validate_svg_content(tmp_zero_width_svg)


def test_validate_content_zero_width_no_unit(tmp_path):
    f = tmp_path / "zeronounit.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="0" height="100">'
        b'<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
    )
    with pytest.raises(SVGValidationError, match="dimension nulle"):
        validate_svg_content(f)


def test_validate_content_zero_height(tmp_path):
    f = tmp_path / "zeroh.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="0mm">'
        b'<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
    )
    with pytest.raises(SVGValidationError, match="dimension nulle"):
        validate_svg_content(f)


def test_validate_content_zero_as_float(tmp_path):
    f = tmp_path / "zerofloat.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="0.0" height="100">'
        b'<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
    )
    with pytest.raises(SVGValidationError, match="dimension nulle"):
        validate_svg_content(f)


# ---------------------------------------------------------------------------
# validate_svg_content — éléments brodables
# ---------------------------------------------------------------------------


def test_validate_content_no_brodable_fill_none_stroke_none(tmp_no_brodable_svg):
    with pytest.raises(SVGValidationError, match="éléments brodables"):
        validate_svg_content(tmp_no_brodable_svg)


def test_validate_content_empty_fill(tmp_path):
    f = tmp_path / "emptyfill.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">'
        b'<path fill="" stroke="" d="M0 0 L10 0 L10 10 Z"/></svg>'
    )
    with pytest.raises(SVGValidationError, match="éléments brodables"):
        validate_svg_content(f)


def test_validate_content_style_fill_valid(tmp_style_fill_svg):
    """Un fill passé via style= CSS doit être reconnu comme valide."""
    validate_svg_content(tmp_style_fill_svg)  # ne doit pas lever


def test_validate_content_stroke_only_path(tmp_path):
    """Un path sans fill mais avec stroke est brodable."""
    f = tmp_path / "strokeonly.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">'
        b'<path fill="none" stroke="#ff0000" d="M0 0 L10 0 L10 10"/></svg>'
    )
    validate_svg_content(f)  # ne doit pas lever


def test_validate_content_text_only_not_brodable(tmp_path):
    """Un SVG avec seulement <text> ne contient aucun tag brodable."""
    f = tmp_path / "textonly.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">'
        b'<text fill="#000000">Hello</text></svg>'
    )
    with pytest.raises(SVGValidationError, match="éléments brodables"):
        validate_svg_content(f)


def test_validate_content_parse_error_is_silent(tmp_path):
    """Un XML malformé dans validate_svg_content doit retourner silencieusement."""
    f = tmp_path / "malformed.svg"
    f.write_bytes(b"<svg xmlns='x'><path fill='#f00' UNCLOSED")
    # Doit retourner sans lever (validate_svg_structure aurait levé avant)
    validate_svg_content(f)


def test_validate_content_rect_with_fill(tmp_path):
    """Un <rect> avec fill doit être reconnu comme brodable."""
    f = tmp_path / "rect.svg"
    f.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">'
        b'<rect fill="#0000ff" x="0" y="0" width="10" height="10"/></svg>'
    )
    validate_svg_content(f)  # ne doit pas lever
