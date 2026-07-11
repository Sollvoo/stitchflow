"""
Tests de performance basiques : durées d'exécution des services critiques.
Pas de framework de benchmark — simple assertion sur time.perf_counter().
"""
import io
import time
from pathlib import Path

import pytest
from PIL import Image


def _make_svg_with_n_paths(n: int, n_colors: int = 5) -> bytes:
    """Génère un SVG avec n paths de couleurs cycliques."""
    colors = [f"#{i * 50 % 255:02x}{(i * 30) % 255:02x}{(i * 70) % 255:02x}" for i in range(n_colors)]
    paths = "".join(
        f'<path fill="{colors[i % n_colors]}" d="M{i*2} 0 L{i*2+1} 0 L{i*2+1} 1 Z"/>'
        for i in range(n)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 200 10">'
        + paths
        + "</svg>"
    ).encode()


def _make_png_image(width: int, height: int) -> Path:
    """Crée un PNG en mémoire et le sauvegarde dans un fichier temporaire."""
    import tempfile
    img = Image.new("RGB", (width, height), color=(255, 128, 0))
    fd, path = tempfile.mkstemp(suffix=".png")
    import os
    os.close(fd)
    img.save(path, format="PNG")
    return Path(path)


# ---------------------------------------------------------------------------
# filter_micro_paths
# ---------------------------------------------------------------------------


def test_filter_micro_paths_100_paths_under_1s(tmp_path):
    from conversions.services.svg_utils import filter_micro_paths

    svg = tmp_path / "perf.svg"
    svg.write_bytes(_make_svg_with_n_paths(100, n_colors=5))

    t0 = time.perf_counter()
    filter_micro_paths(svg, target_width_mm=100)
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"filter_micro_paths 100 paths : {elapsed:.3f}s (seuil 1s)"


# ---------------------------------------------------------------------------
# force_max_svg_colors
# ---------------------------------------------------------------------------


def test_force_max_svg_colors_20_to_10_under_2s(tmp_path):
    from conversions.services.svg_utils import force_max_svg_colors

    svg = tmp_path / "colors.svg"
    svg.write_bytes(_make_svg_with_n_paths(20, n_colors=20))

    t0 = time.perf_counter()
    force_max_svg_colors(svg, max_colors=10)
    elapsed = time.perf_counter() - t0

    assert elapsed < 2.0, f"force_max_svg_colors 20→10 : {elapsed:.3f}s (seuil 2s)"


# ---------------------------------------------------------------------------
# normalize_stroke_only_paths
# ---------------------------------------------------------------------------


def test_normalize_stroke_only_50_paths_under_1s(tmp_path):
    from conversions.services.svg_utils import normalize_stroke_only_paths

    paths = "".join(
        f'<path fill="none" stroke="#ff0000" d="M{i} 0 L{i+0.5} 0 L{i+0.5} 0.5 Z"/>'
        for i in range(50)
    )
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 10">'
        + paths
        + "</svg>"
    )
    svg = tmp_path / "strokes.svg"
    svg.write_text(content, encoding="utf-8")

    t0 = time.perf_counter()
    normalize_stroke_only_paths(svg)
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"normalize_stroke_only_paths 50 paths : {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# get_svg_dimensions_mm
# ---------------------------------------------------------------------------


def test_get_svg_dimensions_fast(tmp_path):
    from conversions.services.svg_utils import get_svg_dimensions_mm

    svg = tmp_path / "dims.svg"
    svg.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="360mm" height="200mm" viewBox="0 0 360 200">'
        b'<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
    )

    t0 = time.perf_counter()
    w, h = get_svg_dimensions_mm(svg)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.1, f"get_svg_dimensions_mm : {elapsed:.3f}s (seuil 0.1s)"
    assert w == pytest.approx(360.0, abs=1.0)
    assert h == pytest.approx(200.0, abs=1.0)


# ---------------------------------------------------------------------------
# validate_png
# ---------------------------------------------------------------------------


def test_validate_png_large_image_under_3s():
    from conversions.services.png_processing import validate_png

    path = _make_png_image(4999, 4999)
    try:
        t0 = time.perf_counter()
        validate_png(path)
        elapsed = time.perf_counter() - t0
        assert elapsed < 3.0, f"validate_png 4999x4999 : {elapsed:.3f}s (seuil 3s)"
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# preprocess_image
# ---------------------------------------------------------------------------


def test_preprocess_image_2000x2000_under_5s():
    from conversions.services.png_processing import preprocess_image

    path = _make_png_image(2000, 2000)
    try:
        t0 = time.perf_counter()
        result = preprocess_image(path)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"preprocess_image 2000x2000 : {elapsed:.3f}s (seuil 5s)"
        if result != path and result.exists():
            result.unlink(missing_ok=True)
    finally:
        path.unlink(missing_ok=True)
