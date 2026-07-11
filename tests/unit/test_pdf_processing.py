"""
Tests unitaires pour conversions/services/pdf_processing.py
"""
from pathlib import Path

import pytest

from conversions.services.pdf_processing import (
    GradientNotSupportedError,
    PDFExtractionError,
    _normalize_percentage_colors,
    extract_vector_svg_from_pdf,
    is_vector_pdf_svg,
    normalize_svg_dimensions_to_mm,
    postprocess_vector_svg,
)


# ---------------------------------------------------------------------------
# is_vector_pdf_svg
# ---------------------------------------------------------------------------


def test_is_vector_pdf_svg_enough_paths(tmp_path):
    """5 paths sans image → vectoriel."""
    svg = tmp_path / "vec.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path d="M0 0"/><path d="M1 1"/><path d="M2 2"/><path d="M3 3"/><path d="M4 4"/>'
        "</svg>",
        encoding="utf-8",
    )
    assert is_vector_pdf_svg(svg) is True


def test_is_vector_pdf_svg_too_few_paths(tmp_path):
    """4 paths → considéré non-vectoriel (seuil = 5)."""
    svg = tmp_path / "few.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path d="M0 0"/><path d="M1 1"/><path d="M2 2"/><path d="M3 3"/>'
        "</svg>",
        encoding="utf-8",
    )
    assert is_vector_pdf_svg(svg) is False


def test_is_vector_pdf_svg_has_embedded_image(tmp_path):
    """Paths + image embarquée → considéré raster."""
    svg = tmp_path / "raster.svg"
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        + '<path d="M0 0"/>' * 10
        + '<image href="data:image/png;base64,abc"/>'
        + "</svg>"
    )
    svg.write_text(content, encoding="utf-8")
    assert is_vector_pdf_svg(svg) is False


def test_is_vector_pdf_svg_missing_file(tmp_path):
    """Fichier absent → retourne False (silencieux)."""
    assert is_vector_pdf_svg(tmp_path / "nonexistent.svg") is False


def test_is_vector_pdf_svg_empty_file(tmp_path):
    """SVG vide (0 paths) → False."""
    svg = tmp_path / "empty.svg"
    svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    assert is_vector_pdf_svg(svg) is False


# ---------------------------------------------------------------------------
# normalize_svg_dimensions_to_mm
# ---------------------------------------------------------------------------


def test_normalize_svg_dimensions_plain_numbers(tmp_path):
    """width/height en nombres nus (points PDF) → convertis en mm."""
    svg = tmp_path / "pts.svg"
    # 595 pt ≈ 209.9mm, 842 pt ≈ 297.0mm (A4)
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842" viewBox="0 0 595 842">'
        "<path/></svg>",
        encoding="utf-8",
    )
    result = normalize_svg_dimensions_to_mm(svg)
    assert result is not None
    w_mm, h_mm = result
    assert 209 < w_mm < 211
    assert 296 < h_mm < 298

    content = svg.read_text()
    assert "mm" in content


def test_normalize_svg_dimensions_already_unitized(tmp_path):
    """width déjà avec unité → retourne None sans modifier."""
    svg = tmp_path / "units.svg"
    original = '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm"><path/></svg>'
    svg.write_text(original, encoding="utf-8")
    result = normalize_svg_dimensions_to_mm(svg)
    assert result is None
    assert svg.read_text() == original


def test_normalize_svg_dimensions_absent_attrs(tmp_path):
    """width/height absents → retourne None."""
    svg = tmp_path / "nosize.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 595 842"><path/></svg>',
        encoding="utf-8",
    )
    result = normalize_svg_dimensions_to_mm(svg)
    assert result is None


def test_normalize_svg_dimensions_parse_error(tmp_path):
    """XML invalide → retourne None sans lever."""
    svg = tmp_path / "bad.svg"
    svg.write_bytes(b"NOT XML AT ALL")
    result = normalize_svg_dimensions_to_mm(svg)
    assert result is None


# ---------------------------------------------------------------------------
# _normalize_percentage_colors
# ---------------------------------------------------------------------------


def test_normalize_percentage_colors_basic(tmp_path):
    svg = tmp_path / "pct.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path fill="rgb(100%,0%,0%)"/>'
        "</svg>",
        encoding="utf-8",
    )
    _normalize_percentage_colors(svg)
    content = svg.read_text()
    # rgb(100%,0%,0%) → #FF0000
    assert "#FF0000" in content
    assert "rgb(" not in content


def test_normalize_percentage_colors_mixed(tmp_path):
    svg = tmp_path / "mixed.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path fill="rgb(0%,100%,0%)"/>'
        '<path fill="#ff0000"/>'
        "</svg>",
        encoding="utf-8",
    )
    _normalize_percentage_colors(svg)
    content = svg.read_text()
    assert "#00FF00" in content
    assert "#ff0000" in content  # préservé tel quel


def test_normalize_percentage_colors_noop(tmp_path):
    svg = tmp_path / "noop.svg"
    original = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path fill="#ff0000"/>'
        "</svg>"
    )
    svg.write_text(original, encoding="utf-8")
    _normalize_percentage_colors(svg)
    assert svg.read_text() == original


# ---------------------------------------------------------------------------
# postprocess_vector_svg — gradient detection
# ---------------------------------------------------------------------------


def test_postprocess_raises_on_linear_gradient(tmp_path):
    svg = tmp_path / "grad.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        "<defs>"
        '<linearGradient id="lg"><stop offset="0%" stop-color="#f00"/></linearGradient>'
        "</defs>"
        '<path fill="url(#lg)" d="M0 0 L10 0 L10 10 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    with pytest.raises(GradientNotSupportedError, match="dégradés"):
        postprocess_vector_svg(svg)


def test_postprocess_raises_on_radial_gradient(tmp_path):
    svg = tmp_path / "radgrad.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        "<defs>"
        '<radialGradient id="rg"><stop offset="0%" stop-color="#00f"/></radialGradient>'
        "</defs>"
        '<path fill="url(#rg)" d="M0 0 L10 0 L10 10 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    with pytest.raises(GradientNotSupportedError):
        postprocess_vector_svg(svg)


def test_postprocess_removes_stroke(tmp_path):
    """Les strokes doivent être supprimés après postprocess."""
    svg = tmp_path / "stroke.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="#ff0000" stroke="#000000" stroke-width="2" d="M0 0 L10 0 L10 10 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    postprocess_vector_svg(svg)
    content = svg.read_text()
    assert 'stroke="none"' in content or "stroke" not in content or 'stroke-width' not in content


# ---------------------------------------------------------------------------
# extract_vector_svg_from_pdf — subprocess mocké
# ---------------------------------------------------------------------------


def test_extract_vector_svg_missing_binary(tmp_path, monkeypatch):
    """pdftocairo absent → PDFExtractionError."""
    import conversions.services.pdf_processing as pdf_mod
    monkeypatch.setattr(pdf_mod, "_find_pdftocairo", lambda: None)

    with pytest.raises(PDFExtractionError, match="pdftocairo introuvable"):
        extract_vector_svg_from_pdf(tmp_path / "dummy.pdf", tmp_path / "out.svg")


def test_extract_vector_svg_subprocess_failure(tmp_path, monkeypatch):
    """subprocess returncode ≠ 0 → PDFExtractionError."""
    import subprocess
    import conversions.services.pdf_processing as pdf_mod

    monkeypatch.setattr(pdf_mod, "_find_pdftocairo", lambda: "/usr/bin/pdftocairo")

    class FakeResult:
        returncode = 1
        stderr = b"error: bad pdf"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    with pytest.raises(PDFExtractionError, match="Extraction SVG"):
        extract_vector_svg_from_pdf(tmp_path / "dummy.pdf", tmp_path / "out.svg")


def test_extract_vector_svg_empty_output(tmp_path, monkeypatch):
    """subprocess réussit mais le fichier de sortie est vide → PDFExtractionError."""
    import subprocess
    import conversions.services.pdf_processing as pdf_mod

    monkeypatch.setattr(pdf_mod, "_find_pdftocairo", lambda: "/usr/bin/pdftocairo")
    out_svg = tmp_path / "out.svg"
    out_svg.write_bytes(b"")  # vide

    class FakeResult:
        returncode = 0
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    with pytest.raises(PDFExtractionError):
        extract_vector_svg_from_pdf(tmp_path / "dummy.pdf", out_svg)
