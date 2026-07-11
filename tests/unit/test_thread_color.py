"""
Tests unitaires pour conversions/services/thread_color.py
"""
import math
from pathlib import Path

import pytest

from conversions.services.thread_color import (
    classify_color_drift,
    hex_delta_e,
    _rgb_to_lab,
    _lab_distance,
    _parse_gpl,
    snap_svg_colors_to_brother_palette,
    get_snap_preview,
    LIGHT_DELTA_E_THRESHOLD,
    NOTABLE_DELTA_E_THRESHOLD,
)


# ---------------------------------------------------------------------------
# _rgb_to_lab
# ---------------------------------------------------------------------------


def test_rgb_to_lab_black():
    L, a, b = _rgb_to_lab(0, 0, 0)
    assert L == pytest.approx(0.0, abs=0.5)
    assert a == pytest.approx(0.0, abs=1.0)
    assert b == pytest.approx(0.0, abs=1.0)


def test_rgb_to_lab_white():
    L, a, b = _rgb_to_lab(255, 255, 255)
    assert L == pytest.approx(100.0, abs=0.5)
    assert a == pytest.approx(0.0, abs=1.0)
    assert b == pytest.approx(0.0, abs=1.0)


def test_rgb_to_lab_red():
    L, a, b = _rgb_to_lab(255, 0, 0)
    # Rouge pur : L ≈ 53, a ≈ 80, b ≈ 67
    assert 50 < L < 56
    assert a > 70
    assert b > 55


def test_rgb_to_lab_same_color_zero_distance():
    lab = _rgb_to_lab(128, 64, 200)
    assert _lab_distance(lab, lab) == 0.0


# ---------------------------------------------------------------------------
# hex_delta_e
# ---------------------------------------------------------------------------


def test_hex_delta_e_identical():
    assert hex_delta_e("#ff0000", "#ff0000") == 0.0


def test_hex_delta_e_black_white():
    d = hex_delta_e("#000000", "#ffffff")
    assert d > 80.0


def test_hex_delta_e_invalid_input():
    assert hex_delta_e("invalid", "#ff0000") == 0.0
    assert hex_delta_e("#ff0000", "bad") == 0.0
    assert hex_delta_e("", "") == 0.0


def test_hex_delta_e_similar_colors():
    # Rouge vs rouge légèrement plus foncé — ΔE modéré
    d = hex_delta_e("#ff0000", "#ee0000")
    assert 0 < d < 15


def test_hex_delta_e_very_different():
    d = hex_delta_e("#ff0000", "#0000ff")
    assert d > 40


# ---------------------------------------------------------------------------
# classify_color_drift
# ---------------------------------------------------------------------------


def test_classify_fidele():
    assert classify_color_drift(0.0) == "fidèle"
    assert classify_color_drift(9.9) == "fidèle"
    assert classify_color_drift(LIGHT_DELTA_E_THRESHOLD - 0.1) == "fidèle"


def test_classify_leger_ecart():
    assert classify_color_drift(10.0) == "léger écart"
    assert classify_color_drift(15.0) == "léger écart"
    assert classify_color_drift(19.9) == "léger écart"


def test_classify_ecart_notable():
    assert classify_color_drift(20.0) == "écart notable"
    assert classify_color_drift(NOTABLE_DELTA_E_THRESHOLD) == "écart notable"
    assert classify_color_drift(100.0) == "écart notable"


# ---------------------------------------------------------------------------
# _parse_gpl
# ---------------------------------------------------------------------------


def test_parse_gpl_basic(tmp_path):
    gpl = tmp_path / "test.gpl"
    gpl.write_text(
        "GIMP Palette\nName: Test\nColumns: 4\n#\n"
        "255 0 0 Red Color\n"
        "0 255 0 Green\n"
        "0 0 255 Blue With Spaces\n"
        "128 128 128\n",
        encoding="utf-8",
    )
    colors = _parse_gpl(gpl)
    assert len(colors) == 4
    assert colors[0] == (255, 0, 0, "Red Color")
    assert colors[1] == (0, 255, 0, "Green")
    assert colors[2] == (0, 0, 255, "Blue With Spaces")
    assert colors[3] == (128, 128, 128, "")


def test_parse_gpl_ignores_invalid_lines(tmp_path):
    gpl = tmp_path / "bad.gpl"
    gpl.write_text(
        "GIMP Palette\nName: X\n"
        "not_a_number 0 0 Bad\n"
        "255 0 0 Valid\n",
        encoding="utf-8",
    )
    colors = _parse_gpl(gpl)
    assert len(colors) == 1
    assert colors[0][0] == 255


# ---------------------------------------------------------------------------
# snap_svg_colors_to_brother_palette
# ---------------------------------------------------------------------------


def test_snap_ignores_none_fill(tmp_path):
    """fill:none ne doit pas être snappé (pas de modification)."""
    svg = tmp_path / "nosnap.svg"
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path fill="none" stroke="#ff0000" d="M0 0 L10 0"/>'
        "</svg>"
    )
    svg.write_text(content, encoding="utf-8")
    original = svg.read_text()

    # Si la palette est absente, la fonction est silencieuse
    snap_svg_colors_to_brother_palette(svg)

    # Le fill:none ne doit jamais être transformé
    after = svg.read_text()
    assert 'fill="none"' in after or original == after


def test_snap_ignores_url_fill(tmp_path):
    """fill:url(...) ne doit pas être snappé."""
    svg = tmp_path / "urlsnap.svg"
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path fill="url(#gradient)" d="M0 0 L10 0"/>'
        "</svg>"
    )
    svg.write_text(content, encoding="utf-8")
    snap_svg_colors_to_brother_palette(svg)
    assert "url(#gradient)" in svg.read_text()


def test_snap_silent_with_missing_palette(tmp_path):
    """Sans palette installée, snap ne doit pas planter."""
    svg = tmp_path / "nopalette.svg"
    svg.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/>'
        b"</svg>"
    )
    snap_svg_colors_to_brother_palette(svg)  # ne doit pas lever


def test_snap_with_synthetic_palette(tmp_path, monkeypatch):
    """Avec une palette synthétique injectée, le snap doit remplacer les couleurs."""
    from conversions.services import thread_color

    fake_palette = [(255, 0, 0, "Brother Red"), (0, 0, 255, "Brother Blue")]

    monkeypatch.setattr(thread_color, "_BROTHER_PALETTE", fake_palette)
    monkeypatch.setattr(thread_color, "_PALETTE_LOADED", True)

    svg = tmp_path / "snap.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path fill="#ff1100" d="M0 0 L10 0 L10 10 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    snap_svg_colors_to_brother_palette(svg)
    result = svg.read_text()
    # La couleur proche du rouge (#ff1100) doit être snappée vers #ff0000
    assert "#ff0000" in result


# ---------------------------------------------------------------------------
# get_snap_preview
# ---------------------------------------------------------------------------


def test_get_snap_preview_empty_when_no_palette(monkeypatch):
    from conversions.services import thread_color
    monkeypatch.setattr(thread_color, "_BROTHER_PALETTE", None)
    monkeypatch.setattr(thread_color, "_PALETTE_LOADED", True)
    assert get_snap_preview(["#ff0000"]) == []


def test_get_snap_preview_collision(tmp_path, monkeypatch):
    """Deux couleurs SVG très proches → même fil Brother → collision=True."""
    from conversions.services import thread_color

    fake_palette = [(255, 0, 0, "Red")]
    monkeypatch.setattr(thread_color, "_BROTHER_PALETTE", fake_palette)
    monkeypatch.setattr(thread_color, "_PALETTE_LOADED", True)

    results = get_snap_preview(["#ff0000", "#ff0010"])
    assert len(results) == 2
    brother_hexes = [r["brother_hex"] for r in results]
    # Les deux mappent vers le même fil
    assert brother_hexes[0] == brother_hexes[1]
    # Le deuxième doit avoir collision=True
    assert results[1]["collision"] is True
    assert results[0]["collision"] is False


def test_get_snap_preview_invalid_hex(monkeypatch):
    from conversions.services import thread_color
    fake_palette = [(255, 0, 0, "Red")]
    monkeypatch.setattr(thread_color, "_BROTHER_PALETTE", fake_palette)
    monkeypatch.setattr(thread_color, "_PALETTE_LOADED", True)

    results = get_snap_preview(["not_a_hex"])
    assert len(results) == 1
    assert results[0]["collision"] is False
    assert results[0]["brother_hex"] == "not_a_hex"  # passthrough


def test_get_snap_preview_has_delta_e(monkeypatch):
    from conversions.services import thread_color
    fake_palette = [(255, 0, 0, "Red")]
    monkeypatch.setattr(thread_color, "_BROTHER_PALETTE", fake_palette)
    monkeypatch.setattr(thread_color, "_PALETTE_LOADED", True)

    results = get_snap_preview(["#ff0000"])
    assert "delta_e" in results[0]
    assert results[0]["delta_e"] == 0.0
