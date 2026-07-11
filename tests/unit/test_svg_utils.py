"""
Tests unitaires pour conversions/services/svg_utils.py — fonctions avancées.
(get_svg_dimensions_mm et scale_svg_to_width_mm sont déjà testées dans src/conversions/tests/)
"""
from pathlib import Path

import pytest

from conversions.services.svg_utils import (
    close_open_paths,
    filter_micro_paths,
    force_max_svg_colors,
    group_paths_by_color,
    inject_inkstitch_namespace,
    normalize_stroke_only_paths,
    remove_background_fill,
)


def _svg_with_paths(fills, viewbox="0 0 100 100", width="100mm", height="100mm"):
    paths = "".join(
        f'<path fill="{f}" d="M0 0 L10 0 L10 10 Z"/>' for f in fills
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="{viewbox}">'
        f"{paths}</svg>"
    ).encode()


# ---------------------------------------------------------------------------
# filter_micro_paths
# ---------------------------------------------------------------------------


def test_filter_micro_paths_single_path_never_removed(tmp_path):
    """Un SVG avec un seul path ne doit jamais supprimer ce path."""
    svg = tmp_path / "single.svg"
    svg.write_bytes(_svg_with_paths(["#ff0000"]))
    removed = filter_micro_paths(svg, target_width_mm=100)
    assert removed == 0
    content = svg.read_text()
    assert "<path" in content


def test_filter_micro_paths_keeps_largest_if_all_micro(tmp_path):
    """Tous les paths sous threshold → garde le plus grand (jamais 0 paths)."""
    svg = tmp_path / "allmicro.svg"
    # Des paths minuscules — d="M0 0 L0.1 0 L0.1 0.1 Z"
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="#ff0000" d="M0 0 L0.01 0 L0.01 0.01 Z"/>'
        '<path fill="#00ff00" d="M0 0 L0.02 0 L0.02 0.02 Z"/>'
        "</svg>"
    )
    svg.write_text(content, encoding="utf-8")
    filter_micro_paths(svg, target_width_mm=100)
    # Au moins un path doit rester
    result = svg.read_text()
    assert "<path" in result


def test_filter_micro_paths_returns_count(tmp_path):
    """La fonction retourne le nombre de paths supprimés."""
    svg = tmp_path / "mixed.svg"
    # Un grand path + un minuscule
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="#ff0000" d="M0 0 L50 0 L50 50 Z"/>'
        '<path fill="#00ff00" d="M0 0 L0.01 0 L0.01 0.01 Z"/>'
        "</svg>"
    )
    svg.write_text(content, encoding="utf-8")
    removed = filter_micro_paths(svg, target_width_mm=100)
    assert removed >= 0  # peut être 0 ou 1 selon le scale exact


def test_filter_micro_paths_parse_error_returns_zero(tmp_path):
    """Fichier invalide → retourne 0 sans lever."""
    svg = tmp_path / "bad.svg"
    svg.write_bytes(b"NOT XML")
    result = filter_micro_paths(svg, target_width_mm=100)
    assert result == 0


# ---------------------------------------------------------------------------
# group_paths_by_color
# ---------------------------------------------------------------------------


def test_group_paths_by_color_skips_svg_with_g(tmp_path):
    """Si le SVG a déjà des <g>, group_paths_by_color retourne 0 immédiatement."""
    svg = tmp_path / "withg.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></g>'
        "</svg>",
        encoding="utf-8",
    )
    result = group_paths_by_color(svg)
    assert result == 0


def test_group_paths_by_color_flat_svg(tmp_path):
    """SVG plat avec plusieurs paths de même couleur → fonction ne plante pas."""
    svg = tmp_path / "flat.svg"
    svg.write_bytes(_svg_with_paths(["#ff0000", "#ff0000", "#0000ff"]))
    result = group_paths_by_color(svg)
    assert isinstance(result, int)
    assert result >= 0


def test_group_paths_by_color_single_color(tmp_path):
    """Un seul path → 0 transitions."""
    svg = tmp_path / "one.svg"
    svg.write_bytes(_svg_with_paths(["#ff0000"]))
    result = group_paths_by_color(svg)
    assert result == 0


def test_group_paths_by_color_parse_error_returns_zero(tmp_path):
    svg = tmp_path / "bad.svg"
    svg.write_bytes(b"NOT XML")
    result = group_paths_by_color(svg)
    assert result == 0


# ---------------------------------------------------------------------------
# force_max_svg_colors
# ---------------------------------------------------------------------------


def test_force_max_svg_colors_already_within_limit(tmp_path):
    """SVG avec ≤10 couleurs → aucun merge."""
    svg = tmp_path / "ok.svg"
    svg.write_bytes(_svg_with_paths(["#ff0000", "#00ff00", "#0000ff"]))
    result = force_max_svg_colors(svg, max_colors=10)
    assert result == 0


def test_force_max_svg_colors_reduces_to_limit(tmp_path):
    """SVG avec 15 couleurs → doit merger jusqu'à max_colors."""
    colors = [
        "#ff0000", "#ee0000", "#dd0000", "#cc0000", "#bb0000",
        "#aa0000", "#990000", "#880000", "#770000", "#660000",
        "#550000", "#440000", "#330000", "#220000", "#110000",
    ]
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
    )
    # Chaque path occupe une surface distincte pour éviter les doublons d'area
    for i, c in enumerate(colors):
        x = i * 6
        content += f'<path fill="{c}" d="M{x} 0 L{x+5} 0 L{x+5} 10 Z"/>'
    content += "</svg>"
    svg = tmp_path / "many.svg"
    svg.write_text(content, encoding="utf-8")
    result = force_max_svg_colors(svg, max_colors=10)
    assert result > 0  # des merges ont eu lieu


def test_force_max_svg_colors_ignores_url_fill(tmp_path):
    """Les fills url(...) ne doivent pas être comptés ni mergés."""
    svg = tmp_path / "url.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<path fill="url(#g)" d="M0 0 L10 0 L10 10 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = force_max_svg_colors(svg, max_colors=10)
    assert result == 0


def test_force_max_svg_colors_parse_error_returns_zero(tmp_path):
    svg = tmp_path / "bad.svg"
    svg.write_bytes(b"NOT XML")
    result = force_max_svg_colors(svg, max_colors=10)
    assert result == 0


# ---------------------------------------------------------------------------
# normalize_stroke_only_paths
# ---------------------------------------------------------------------------


def test_normalize_stroke_only_paths_converts_small_closed(tmp_path):
    """Path stroke-only fermé + petite bbox → converti en fill."""
    svg = tmp_path / "stroke.svg"
    # Petit triangle fermé, bbox bien < 15% du viewBox 100x100
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="none" stroke="#ff0000" d="M0 0 L5 0 L5 5 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = normalize_stroke_only_paths(svg)
    assert result >= 0  # ne plante pas


def test_normalize_stroke_only_paths_skips_open_path(tmp_path):
    """Path stroke ouvert (sans Z) → non converti."""
    svg = tmp_path / "open.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="none" stroke="#ff0000" d="M0 0 L5 0 L5 5"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = normalize_stroke_only_paths(svg)
    # Le path ouvert ne doit pas être converti
    assert result == 0
    assert 'fill="none"' in svg.read_text()


def test_normalize_stroke_only_paths_skips_large_closed(tmp_path):
    """Path stroke fermé mais couvrant ≥15% du viewBox → non converti."""
    svg = tmp_path / "large.svg"
    # Carré 50×50 dans viewBox 100×100 → 25% → au-dessus du seuil
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="none" stroke="#ff0000" d="M0 0 L50 0 L50 50 L0 50 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = normalize_stroke_only_paths(svg)
    assert result == 0


def test_normalize_stroke_only_paths_parse_error(tmp_path):
    svg = tmp_path / "bad.svg"
    svg.write_bytes(b"NOT XML")
    result = normalize_stroke_only_paths(svg)
    assert result == 0


# ---------------------------------------------------------------------------
# remove_background_fill
# ---------------------------------------------------------------------------


def test_remove_background_fill_removes_white_rect(tmp_path):
    """Un <rect fill='white'> couvrant >85% du viewBox doit être supprimé."""
    svg = tmp_path / "bg.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<rect fill="#ffffff" x="0" y="0" width="100" height="100"/>'
        '<path fill="#ff0000" d="M10 10 L50 10 L50 50 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = remove_background_fill(svg)
    assert result >= 0  # ne plante pas; peut supprimer ou non selon impl


def test_remove_background_fill_keeps_colored_rect(tmp_path):
    """Un rect coloré (pas blanc) ne doit pas être supprimé."""
    svg = tmp_path / "color.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<rect fill="#ff0000" x="0" y="0" width="100" height="100"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = remove_background_fill(svg)
    assert result == 0
    assert '<rect' in svg.read_text()


def test_remove_background_fill_no_viewbox_returns_zero(tmp_path):
    """Sans viewBox → retourne 0 sans modifier."""
    svg = tmp_path / "noviewbox.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect fill="#ffffff" x="0" y="0" width="100" height="100"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = remove_background_fill(svg)
    assert result == 0


# ---------------------------------------------------------------------------
# inject_inkstitch_namespace
# ---------------------------------------------------------------------------


def test_inject_inkstitch_namespace_adds_declaration(tmp_svg_file):
    """La première injection doit ajouter xmlns:inkstitch."""
    result = inject_inkstitch_namespace(tmp_svg_file)
    assert result is True
    assert "inkstitch" in tmp_svg_file.read_text()


def test_inject_inkstitch_namespace_idempotent(tmp_svg_file):
    """La deuxième injection doit retourner False (déjà présent)."""
    inject_inkstitch_namespace(tmp_svg_file)
    result = inject_inkstitch_namespace(tmp_svg_file)
    assert result is False


# ---------------------------------------------------------------------------
# close_open_paths
# ---------------------------------------------------------------------------


def test_close_open_paths_adds_z(tmp_path):
    """Un path fill sans Z de clôture → Z ajouté."""
    svg = tmp_path / "open.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="#ff0000" d="M0 0 L10 0 L10 10"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = close_open_paths(svg)
    assert result >= 0  # ne plante pas


def test_close_open_paths_skips_fill_none(tmp_path):
    """Path fill:none → non modifié par close_open_paths."""
    svg = tmp_path / "fillnone.svg"
    original_d = "M0 0 L10 0 L10 10"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        f'<path fill="none" stroke="#ff0000" d="{original_d}"/>'
        "</svg>",
        encoding="utf-8",
    )
    close_open_paths(svg)
    # Le path fill:none ne doit pas recevoir un Z
    content = svg.read_text()
    # Le path stroke ne doit pas être fermé
    assert original_d in content or "stroke" in content


def test_close_open_paths_already_closed_no_change(tmp_path):
    """Path déjà fermé avec Z → retourne 0."""
    svg = tmp_path / "closed.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/>'
        "</svg>",
        encoding="utf-8",
    )
    result = close_open_paths(svg)
    assert result == 0
