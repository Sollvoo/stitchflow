"""
Utilitaires pour la manipulation de fichiers SVG.
"""

import logging
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# Facteurs de conversion vers mm
_UNITS_TO_MM: dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "in": 25.4,
    "pt": 25.4 / 72,
    "pc": 25.4 / 6,
    "px": 25.4 / 96,
}

# Namespaces SVG courants à enregistrer pour préserver les préfixes à l'écriture
_SVG_NAMESPACES = {
    "": "http://www.w3.org/2000/svg",
    "xlink": "http://www.w3.org/1999/xlink",
    "dc": "http://purl.org/dc/elements/1.1/",
    "cc": "http://creativecommons.org/ns#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "inkstitch": "http://inkstitch.org/namespace",
}

_INKSTITCH_NS = "http://inkstitch.org/namespace"
_INKSTITCH_ROW_SPACING = f"{{{_INKSTITCH_NS}}}row_spacing_mm"
_INKSTITCH_STROKE_METHOD = f"{{{_INKSTITCH_NS}}}stroke_method"

_SNAPSHOT_SUBDIR = "conversions/snapshots"
_SNAPSHOT_MAX = 20

# Couleurs CSS nommées (sous-ensemble HTML/CSS courant) → #rrggbb
_CSS_NAMED_COLORS: dict[str, str] = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000",
    "lime": "#00ff00", "blue": "#0000ff", "yellow": "#ffff00",
    "cyan": "#00ffff", "magenta": "#ff00ff", "silver": "#c0c0c0",
    "gray": "#808080", "grey": "#808080", "maroon": "#800000",
    "olive": "#808000", "green": "#008000", "purple": "#800080",
    "teal": "#008080", "navy": "#000080", "fuchsia": "#ff00ff",
    "aqua": "#00ffff", "orange": "#ffa500", "pink": "#ffc0cb",
    "brown": "#a52a2a", "coral": "#ff7f50", "gold": "#ffd700",
    "indigo": "#4b0082", "ivory": "#fffff0", "khaki": "#f0e68c",
    "lavender": "#e6e6fa", "crimson": "#dc143c", "turquoise": "#40e0d0",
    "violet": "#ee82ee",
}

# Propriétés CSS à extraire du style= pour les poser comme attributs SVG explicites
_CSS_PROPS_TO_INLINE: frozenset[str] = frozenset([
    "fill", "stroke", "opacity", "display", "visibility",
    "fill-opacity", "stroke-opacity", "fill-rule",
])


def _register_svg_namespaces() -> None:
    for prefix, uri in _SVG_NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def _parse_length_mm(value: str) -> float | None:
    """Convertit une longueur SVG (ex : '100mm', '50', '2in') en millimètres."""
    v = value.strip().lower()
    for unit, factor in sorted(_UNITS_TO_MM.items(), key=lambda x: -len(x[0])):
        if v.endswith(unit):
            try:
                numeric = v[: -len(unit)] if unit else v
                return float(numeric) * factor
            except ValueError:
                return None
    try:
        return float(v) * _UNITS_TO_MM["px"]  # sans unité = px par défaut
    except ValueError:
        return None


def get_svg_dimensions_mm(svg_path: Path) -> tuple[float | None, float | None]:
    """
    Retourne (width_mm, height_mm) depuis un fichier SVG.
    Retourne (None, None) si les dimensions ne peuvent pas être déterminées.
    """
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()

        w_attr = root.get("width", "")
        h_attr = root.get("height", "")

        if "%" not in w_attr and "%" not in h_attr and w_attr and h_attr:
            w_mm = _parse_length_mm(w_attr)
            h_mm = _parse_length_mm(h_attr)
            if w_mm and h_mm:
                return round(w_mm, 1), round(h_mm, 1)

        # Fallback : viewBox en pixels
        vb = root.get("viewBox")
        if vb:
            parts = vb.split()
            if len(parts) == 4:
                vb_w = float(parts[2])
                vb_h = float(parts[3])
                return (
                    round(vb_w * _UNITS_TO_MM["px"], 1),
                    round(vb_h * _UNITS_TO_MM["px"], 1),
                )
    except Exception:
        pass
    return None, None


_COORD_RE = re.compile(r"[-+]?\d*\.?\d+")
_SVG_NS = "http://www.w3.org/2000/svg"


def _path_centroid(d: str) -> tuple[float, float] | None:
    """Centre du bounding box des coordonnées d'un attribut d SVG. Retourne None si aucun nombre."""
    nums = [float(m) for m in _COORD_RE.findall(d or "")]
    if not nums:
        return None
    xs = nums[0::2]
    ys = nums[1::2]
    if not xs or not ys:
        return None
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _path_bbox_area(d: str) -> float:
    """Aire du bounding box des coordonnées d'un attribut d SVG."""
    nums = [float(m) for m in _COORD_RE.findall(d or "")]
    if len(nums) < 4:
        return 0.0
    xs = nums[0::2]
    ys = nums[1::2]
    if not xs or not ys:
        return 0.0
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _greedy_nn(items: list, centroid_fn) -> list:
    """Greedy nearest-neighbor depuis (0, 0). Retourne items réordonnés."""
    if len(items) <= 1:
        return items
    remaining = list(items)
    ordered = []
    cx, cy = 0.0, 0.0
    while remaining:
        best_i, best_d = 0, float("inf")
        for i, item in enumerate(remaining):
            c = centroid_fn(item)
            if c is None:
                c = (0.0, 0.0)
            d = (c[0] - cx) ** 2 + (c[1] - cy) ** 2
            if d < best_d:
                best_d, best_i = d, i
        chosen = remaining.pop(best_i)
        c = centroid_fn(chosen)
        if c:
            cx, cy = c
        ordered.append(chosen)
    return ordered


def reorder_svg_paths_for_minimal_jumps(svg_path: Path) -> None:
    """
    Réordonne les paths SVG via nearest-neighbor pour minimiser les déplacements à vide.
    Modifie le fichier en place.
    - Réordonne les <path> DANS chaque parent (<g> ou root)
    - Réordonne les <g> directs du root entre eux
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return

    root = tree.getroot()
    total_paths = 0

    def _path_centroid_el(el: ET.Element) -> tuple[float, float] | None:
        return _path_centroid(el.get("d", ""))

    def _group_centroid(g: ET.Element) -> tuple[float, float] | None:
        cs = [_path_centroid_el(p) for p in g.iter() if p.tag.endswith("path")]
        valid = [c for c in cs if c is not None]
        if not valid:
            return None
        return sum(c[0] for c in valid) / len(valid), sum(c[1] for c in valid) / len(
            valid
        )

    ns_path = f"{{{_SVG_NS}}}path"
    ns_g = f"{{{_SVG_NS}}}g"

    # Réordonner les paths dans chaque <g> direct
    direct_groups = [ch for ch in root if ch.tag in (ns_g, "g")]
    for g in direct_groups:
        paths = [ch for ch in g if ch.tag in (ns_path, "path")]
        if len(paths) <= 1:
            continue
        reordered = _greedy_nn(paths, _path_centroid_el)
        for p in paths:
            g.remove(p)
        for p in reordered:
            g.append(p)
        total_paths += len(reordered)

    # Réordonner les <g> eux-mêmes dans le root
    if len(direct_groups) > 1:
        for g in direct_groups:
            root.remove(g)
        for g in _greedy_nn(direct_groups, _group_centroid):
            root.append(g)

    # Réordonner aussi les <path> directs sous la racine (VTracer flat)
    direct_paths = [ch for ch in root if ch.tag in (ns_path, "path")]
    if len(direct_paths) > 1:
        reordered = _greedy_nn(direct_paths, _path_centroid_el)
        for p in direct_paths:
            root.remove(p)
        for p in reordered:
            root.append(p)
        total_paths += len(reordered)

    logger.debug(
        "[6a] reordered %d paths, %d groups in %s",
        total_paths,
        len(direct_groups),
        svg_path.name,
    )
    tree.write(svg_path, encoding="unicode", xml_declaration=True)


def filter_micro_paths(
    svg_path: Path, target_width_mm: int, min_area_mm2: float = 0.1
) -> int:
    """
    Supprime les <path> dont la surface estimée est inférieure à min_area_mm2.
    Retourne le nombre de paths supprimés. Ne supprime jamais le dernier path.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()

    # Calcul du facteur d'échelle mm/unit
    vb = root.get("viewBox", "")
    vb_parts = vb.split() if vb else []
    mm_per_unit: float | None = None

    if target_width_mm > 0 and len(vb_parts) == 4:
        try:
            vb_w = float(vb_parts[2])
            if vb_w > 0:
                mm_per_unit = target_width_mm / vb_w
        except ValueError:
            pass

    if mm_per_unit is None:
        w_mm, _ = get_svg_dimensions_mm(svg_path)
        if w_mm and len(vb_parts) == 4:
            try:
                vb_w = float(vb_parts[2])
                if vb_w > 0:
                    mm_per_unit = w_mm / vb_w
            except ValueError:
                pass

    if mm_per_unit is None:
        mm_per_unit = 25.4 / 96  # fallback 96 dpi

    ns_path = f"{{{_SVG_NS}}}path"

    def _path_area_mm2(el: ET.Element) -> float:
        nums = [float(m) for m in _COORD_RE.findall(el.get("d", ""))]
        if len(nums) < 2:
            return 0.0
        xs, ys = nums[0::2], nums[1::2]
        if not xs or not ys:
            return 0.0
        bbox_w = (max(xs) - min(xs)) * mm_per_unit
        bbox_h = (max(ys) - min(ys)) * mm_per_unit
        return bbox_w * bbox_h

    # Collecter tous les paths avec leur parent et leur aire
    path_records: list[tuple[ET.Element, ET.Element, float]] = (
        []
    )  # (path, parent, area)
    for parent in [root] + list(root.iter()):
        for child in list(parent):
            if child.tag in (ns_path, "path"):
                path_records.append((child, parent, _path_area_mm2(child)))

    n_total = len(path_records)
    if n_total == 0:
        return 0

    to_remove = [
        (path, parent) for path, parent, area in path_records if area <= min_area_mm2
    ]
    n_remove = len(to_remove)

    # Garde anti-vide : conserver au moins 1 path
    if n_remove >= n_total:
        logger.warning(
            "[6b] tous les %d paths seraient supprimés → conservation du plus grand",
            n_total,
        )
        largest = max(path_records, key=lambda x: x[2])
        to_remove = [(p, par) for p, par, _ in path_records if p is not largest[0]]
        n_remove = len(to_remove)

    if n_remove == 0:
        return 0

    if n_remove / n_total > 0.10:
        logger.warning(
            "[6b] %d/%d paths supprimés (>10%%) — vectorisation potentiellement dégradée dans %s",
            n_remove,
            n_total,
            svg_path.name,
        )

    for path, parent in to_remove:
        try:
            parent.remove(path)
        except ValueError:
            pass

    tree.write(svg_path, encoding="unicode", xml_declaration=True)
    return n_remove


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int] | None:
    """Convertit '#rrggbb' ou '#rgb' en (R, G, B). Retourne None si invalide."""
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def _rgb_to_lab_utils(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Conversion RGB → CIE Lab (D65, 2°) sans dépendance externe."""

    def _linearize(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    lr, lg, lb = _linearize(r), _linearize(g), _linearize(b)
    x = (lr * 0.4124 + lg * 0.3576 + lb * 0.1805) / 0.95047
    y = (lr * 0.2126 + lg * 0.7152 + lb * 0.0722) / 1.00000
    z = (lr * 0.0193 + lg * 0.1192 + lb * 0.9505) / 1.08883

    def _f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = _f(x), _f(y), _f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _lab_dist_utils(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _is_near_white_fill(fill: str) -> bool:
    """Retourne True si le fill est une couleur quasi-blanche (L* > 92 en Lab)."""
    names = {
        "white": (255, 255, 255),
        "snow": (255, 250, 250),
        "ivory": (255, 255, 240),
    }
    if fill.lower() in names:
        rgb = names[fill.lower()]
    else:
        rgb = _hex_to_rgb(fill)
    if rgb is None:
        return False
    L, _, _ = _rgb_to_lab_utils(*rgb)
    return L > 92.0


def remove_background_fill(svg_path: Path) -> int:
    """
    Supprime les fills blanc/quasi-blanc (L* > 92) qui couvrent plus de 85% de la surface SVG.
    Utile pour supprimer les fonds blancs issus de la vectorisation PNG.
    Retourne le nombre d'éléments supprimés.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()

    # Résoudre les dimensions : viewBox prioritaire, sinon width/height direct
    vb_w: float | None = None
    vb_h: float | None = None
    vb = root.get("viewBox", "")
    vb_parts = vb.split() if vb else []
    if len(vb_parts) == 4:
        try:
            vb_w, vb_h = float(vb_parts[2]), float(vb_parts[3])
        except ValueError:
            pass

    if vb_w is None or vb_h is None:
        # Fallback : width/height directs (SVG VTracer sans viewBox)
        try:
            w_attr = root.get("width", "")
            h_attr = root.get("height", "")
            if w_attr and h_attr:
                w_mm = _parse_length_mm(w_attr)
                h_mm = _parse_length_mm(h_attr)
                if w_mm and h_mm:
                    vb_w, vb_h = w_mm, h_mm
        except Exception:
            pass

    if not vb_w or not vb_h or vb_w <= 0 or vb_h <= 0:
        return 0

    viewbox_area = vb_w * vb_h
    ns_path = f"{{{_SVG_NS}}}path"
    ns_rect = f"{{{_SVG_NS}}}rect"
    ns_g = f"{{{_SVG_NS}}}g"

    to_remove: list[tuple[ET.Element, ET.Element]] = []

    def _check_element(el: ET.Element, parent: ET.Element) -> None:
        fill = el.get("fill", "") or ""
        if not fill or fill in ("none", "transparent"):
            return
        if not _is_near_white_fill(fill):
            return

        if el.tag in (ns_rect, "rect"):
            try:
                rw = float(el.get("width", 0))
                rh = float(el.get("height", 0))
                rect_area = rw * rh
                coverage = rect_area / viewbox_area
                if coverage > 0.85:
                    to_remove.append((el, parent))
            except ValueError:
                pass
        elif el.tag in (ns_path, "path"):
            d = el.get("d", "")
            # Ne supprimer que les paths simples (≤ 12 commandes SVG) — rectangles approximatifs.
            # Les formes complexes (hexagones, étoiles, silhouettes) sont des éléments de design.
            segment_count = len(re.findall(r"[MmLlHhVvCcSsQqTtAaZz]", d))
            if segment_count > 12:
                return
            nums = [float(m) for m in _COORD_RE.findall(d)]
            if len(nums) < 4:
                return
            xs, ys = nums[0::2], nums[1::2]
            if not xs or not ys:
                return
            bbox_w = max(xs) - min(xs)
            bbox_h = max(ys) - min(ys)
            coverage = (bbox_w * bbox_h) / viewbox_area
            if coverage > 0.85:
                to_remove.append((el, parent))

    for child in list(root):
        if child.tag in (ns_g, "g"):
            for grandchild in list(child):
                _check_element(grandchild, child)
        _check_element(child, root)

    if not to_remove:
        return 0

    removed = 0
    for el, parent in to_remove:
        try:
            parent.remove(el)
            removed += 1
        except ValueError:
            pass

    if removed:
        logger.info("[bg] %d fond(s) blanc supprimé(s) dans %s", removed, svg_path.name)
        tree.write(svg_path, encoding="unicode", xml_declaration=True)

    return removed


def force_max_svg_colors(svg_path: Path, max_colors: int = 10) -> int:
    """
    Garantit que le SVG n'a pas plus de max_colors couleurs de fill distinctes.
    Fusionne itérativement les deux couleurs Lab les plus proches jusqu'à atteindre max_colors.
    Retourne le nombre de couleurs fusionnées (0 si déjà dans la limite).
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    ns_path = f"{{{_SVG_NS}}}path"

    all_elements = list(root.iter())
    fill_elements: list[ET.Element] = [
        el
        for el in all_elements
        if el.tag in (ns_path, "path")
        and el.get("fill", "") not in ("", "none", "transparent")
        and not el.get("fill", "").startswith("url(")
    ]

    if not fill_elements:
        return 0

    fills = [el.get("fill", "") for el in fill_elements]
    unique_fills = list(dict.fromkeys(fills))

    if len(unique_fills) <= max_colors:
        return 0

    fill_surface_area: dict[str, float] = {}
    for el in fill_elements:
        f = el.get("fill", "")
        fill_surface_area[f] = fill_surface_area.get(f, 0.0) + _path_bbox_area(
            el.get("d", "")
        )

    fill_to_rgb: dict[str, tuple[int, int, int] | None] = {
        f: _hex_to_rgb(f) for f in unique_fills
    }
    fill_to_lab: dict[str, tuple[float, float, float] | None] = {
        f: (_rgb_to_lab_utils(*rgb) if rgb else None) for f, rgb in fill_to_rgb.items()
    }

    current_fills = list(unique_fills)
    n_merged = 0

    # Pré-pass : éliminer les couleurs parasites (anti-aliasing, artefacts minuscules)
    # avant la fusion itérative. Seuil relatif à la surface des éléments colorés réels
    # (pas au viewBox total qui peut inclure un fond vide de grande taille).
    viewbox_parts = root.get("viewBox", "").split()
    total_area = 0.0
    if len(viewbox_parts) == 4:
        try:
            total_area = float(viewbox_parts[2]) * float(viewbox_parts[3])
        except ValueError:
            pass
    active_area = sum(fill_surface_area.values())
    dust_threshold = active_area * 0.005 if active_area > 0 else total_area * 0.005

    if dust_threshold > 0:
        for dust_f in list(current_fills):
            if fill_surface_area.get(dust_f, 0.0) >= dust_threshold:
                continue
            dust_lab = fill_to_lab.get(dust_f)
            if dust_lab is None:
                continue
            best_dist, best_target = float("inf"), None
            for other_f in current_fills:
                if other_f == dust_f:
                    continue
                other_lab = fill_to_lab.get(other_f)
                if other_lab is None:
                    continue
                d = _lab_dist_utils(dust_lab, other_lab)
                if d < best_dist:
                    best_dist, best_target = d, other_f
            if best_target is None:
                continue
            fill_surface_area[best_target] = fill_surface_area.get(
                best_target, 0.0
            ) + fill_surface_area.get(dust_f, 0.0)
            fill_surface_area.pop(dust_f, None)
            for el in fill_elements:
                if el.get("fill") == dust_f:
                    el.set("fill", best_target)
            current_fills.remove(dust_f)
            n_merged += 1

    while len(current_fills) > max(max_colors, 1):
        best_dist = float("inf")
        best_i, best_j = 0, 1

        for i in range(len(current_fills)):
            lab_i = fill_to_lab.get(current_fills[i])
            if lab_i is None:
                continue
            for j in range(i + 1, len(current_fills)):
                lab_j = fill_to_lab.get(current_fills[j])
                if lab_j is None:
                    continue
                d = _lab_dist_utils(lab_i, lab_j)
                if d < best_dist:
                    best_dist = d
                    best_i, best_j = i, j

        fi, fj = current_fills[best_i], current_fills[best_j]
        # Garder la couleur qui couvre le plus de surface, remplacer l'autre
        if fill_surface_area.get(fi, 0.0) >= fill_surface_area.get(fj, 0.0):
            kept, merged = fi, fj
        else:
            kept, merged = fj, fi

        fill_surface_area[kept] = fill_surface_area.get(
            kept, 0.0
        ) + fill_surface_area.get(merged, 0.0)
        fill_surface_area.pop(merged, None)

        for el in fill_elements:
            if el.get("fill") == merged:
                el.set("fill", kept)

        current_fills.remove(merged)
        n_merged += 1

    if n_merged > 0:
        logger.info(
            "[colors] %d couleur(s) fusionnées → %d fils max dans %s",
            n_merged,
            len(current_fills),
            svg_path.name,
        )
        tree.write(svg_path, encoding="unicode", xml_declaration=True)

    return n_merged


def group_paths_by_color(svg_path: Path) -> int:
    """
    Regroupe les <path> plats (directs sous root, sortie VTracer) par couleur de fill.
    Réduit les changements de couleur séquentiels qu'Ink/Stitch interprète comme des fils.
    Ne touche pas aux SVGs déjà structurés en <g> (sortie potrace).
    Retourne le nombre de changements de couleur réduits.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    ns_path = f"{{{_SVG_NS}}}path"
    ns_g = f"{{{_SVG_NS}}}g"

    # Si le SVG a déjà des <g> (sortie potrace, potrace-snap), skip — déjà structuré par couleur
    has_color_groups = any(ch.tag in (ns_g, "g") for ch in root)
    if has_color_groups:
        return 0

    flat_paths: list[tuple[ET.Element, str]] = [
        (ch, ch.get("fill", "") or "")
        for ch in list(root)
        if ch.tag in (ns_path, "path")
    ]

    if len(flat_paths) <= 1:
        return 0

    # Ordre d'apparition des couleurs (pour conserver l'ordre relatif des couleurs)
    seen_colors: list[str] = []
    for _, fill in flat_paths:
        key = fill.lower().strip()
        if key and key not in seen_colors:
            seen_colors.append(key)

    if len(seen_colors) <= 1:
        return 0

    changes_before = sum(
        1 for i in range(1, len(flat_paths)) if flat_paths[i][1] != flat_paths[i - 1][1]
    )

    by_color: dict[str, list[ET.Element]] = {c: [] for c in seen_colors}
    ungrouped: list[ET.Element] = []

    for path, fill in flat_paths:
        key = fill.lower().strip()
        if key in by_color:
            by_color[key].append(path)
        else:
            ungrouped.append(path)

    # Réordonner les groupes couleur par centroïde NN pour minimiser les sauts entre fils
    def _color_group_centroid(color: str) -> tuple[float, float] | None:
        paths = by_color.get(color, [])
        cs = [_path_centroid(p.get("d", "")) for p in paths]
        valid = [c for c in cs if c is not None]
        if not valid:
            return None
        return sum(c[0] for c in valid) / len(valid), sum(c[1] for c in valid) / len(
            valid
        )

    seen_colors = _greedy_nn(seen_colors, _color_group_centroid)

    for path, _ in flat_paths:
        try:
            root.remove(path)
        except ValueError:
            pass

    for color in seen_colors:
        for path in by_color[color]:
            root.append(path)
    for path in ungrouped:
        root.append(path)

    fills_after = [ch.get("fill", "") for ch in root if ch.tag in (ns_path, "path")]
    changes_after = sum(
        1 for i in range(1, len(fills_after)) if fills_after[i] != fills_after[i - 1]
    )

    reduced = changes_before - changes_after
    logger.info(
        "[group] %d→%d changements couleur séquentiels dans %s",
        changes_before + 1,
        changes_after + 1,
        svg_path.name,
    )
    tree.write(svg_path, encoding="unicode", xml_declaration=True)
    return reduced


def _count_svg_unique_fills(svg_path: Path) -> int:
    try:
        root = ET.parse(svg_path).getroot()
        return len(
            {
                el.get("fill", "")
                for el in root.iter()
                if el.get("fill", "") not in ("", "none", "transparent")
                and not el.get("fill", "").startswith("url(")
            }
        )
    except Exception:
        return 0


def normalize_stroke_only_paths(svg_path: Path) -> int:
    """
    Convertit les paths stroke-only (fill absent ou 'none', stroke='#rrggbb') en fill='#rrggbb'.

    Ces paths représentent typiquement du texte vectorisé en contours ou des formes avec
    bordure colorée. Ink/Stitch ignore les paths sans fill — cette conversion les rend brodables.
    Le stroke est mis à 'none' après la conversion pour éviter les doubles stitches.

    Retourne le nombre de paths modifiés.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    ns_path = f"{{{_SVG_NS}}}path"
    modified = 0

    # Ratio unités SVG / mm pour évaluer l'épaisseur réelle du trait
    _svg_units_per_mm = 1.0
    width_attr = root.get("width", "")
    viewbox_attr = root.get("viewBox", "")
    if width_attr.endswith("mm") and viewbox_attr:
        try:
            vb_parts = viewbox_attr.split()
            if len(vb_parts) == 4:
                vb_w = float(vb_parts[2])
                target_mm = float(width_attr[:-2])
                if target_mm > 0:
                    _svg_units_per_mm = vb_w / target_mm
        except (ValueError, ZeroDivisionError):
            pass
    _MIN_STROKE_MM = 1.0

    for el in root.iter():
        if el.tag not in (ns_path, "path"):
            continue

        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip()

        # Style CSS inline : extraire fill et stroke si définis via style=
        style_str = el.get("style", "")
        if style_str:
            for part in style_str.split(";"):
                part = part.strip()
                if ":" in part:
                    k, _, v = part.partition(":")
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "fill" and not el.get("fill"):
                        fill = v.lower()
                    elif k == "stroke" and not el.get("stroke"):
                        stroke = v

        is_fill_none = fill in ("", "none", "transparent")
        is_stroke_color = stroke.startswith("#") and len(stroke) == 7

        if is_fill_none and is_stroke_color:
            try:
                sw_svg = float(el.get("stroke-width", "1").strip())
            except ValueError:
                sw_svg = 1.0
            sw_mm = sw_svg / _svg_units_per_mm
            if sw_mm < _MIN_STROKE_MM:
                logger.debug(
                    "[stroke-fix] stroke-width %.2fmm < 1mm → converti en fill quand même (Ink/Stitch ignore stroke-only) pour %s",
                    sw_mm,
                    svg_path.name,
                )

            el.set("fill", stroke)
            el.set("stroke", "none")
            # Nettoyer stroke du style CSS si présent
            if style_str:
                parts = [
                    p
                    for p in style_str.split(";")
                    if p.strip() and not p.strip().lower().startswith("stroke")
                ]
                new_style = ";".join(parts)
                if new_style:
                    el.set("style", new_style)
                elif el.get("style") is not None:
                    del el.attrib["style"]
            modified += 1

    if modified:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info(
            "[stroke-fix] %d paths stroke-only → fill dans %s", modified, svg_path.name
        )

    return modified


def scale_svg_to_width_mm(input_svg: Path, target_width_mm: int) -> Path:
    """
    Crée une copie temporaire du SVG redimensionnée à target_width_mm (ratio conservé).
    L'appelant est responsable de supprimer le fichier temporaire après usage.

    Args:
        input_svg: Chemin vers le SVG original.
        target_width_mm: Largeur cible en millimètres.

    Returns:
        Chemin vers le fichier SVG temporaire redimensionné.
    """
    _register_svg_namespaces()

    tree = ET.parse(input_svg)
    root = tree.getroot()

    # Déterminer le ratio d'aspect depuis viewBox ou width/height
    vb = root.get("viewBox")
    if vb:
        parts = vb.split()
        if len(parts) == 4:
            vb_w, vb_h = float(parts[2]), float(parts[3])
            aspect = vb_h / vb_w if vb_w else 1.0
        else:
            aspect = 1.0
    else:
        w_mm, h_mm = get_svg_dimensions_mm(input_svg)
        if w_mm and h_mm and w_mm > 0:
            aspect = h_mm / w_mm
            # Ajouter un viewBox pour préserver les positions des éléments
            w_attr = root.get("width", "100")
            h_attr = root.get("height", "100")
            w_px = (_parse_length_mm(w_attr) or 100) / _UNITS_TO_MM["px"]
            h_px = (_parse_length_mm(h_attr) or 100) / _UNITS_TO_MM["px"]
            root.set("viewBox", f"0 0 {w_px:.4f} {h_px:.4f}")
        else:
            aspect = 1.0

    target_height_mm = round(target_width_mm * aspect, 4)
    root.set("width", f"{target_width_mm}mm")
    root.set("height", f"{target_height_mm}mm")

    tmp = tempfile.NamedTemporaryFile(
        suffix=".svg", delete=False, mode="w", encoding="utf-8"
    )
    tmp.close()
    tree.write(tmp.name, encoding="unicode", xml_declaration=True)
    return Path(tmp.name)


def _normalize_css_color(val: str) -> str:
    """Normalise une valeur CSS couleur vers #rrggbb si possible."""
    v = val.strip().lower()
    if v in _CSS_NAMED_COLORS:
        return _CSS_NAMED_COLORS[v]
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    m = re.match(r"#([0-9a-f])([0-9a-f])([0-9a-f])$", v)
    if m:
        return f"#{m.group(1)*2}{m.group(2)*2}{m.group(3)*2}"
    return val


def _inline_svg_styles(root: ET.Element) -> int:
    """
    Convertit les propriétés CSS dans style= en attributs SVG explicites.
    Ex : style="fill:#f00;opacity:0.5" → fill="#f00" opacity="0.5".
    Retourne le nombre d'éléments modifiés.
    """
    _COLOR_PROPS = frozenset(["fill", "stroke"])
    _PASSTHROUGH = frozenset(["none", "transparent", "inherit", "currentcolor"])
    modified = 0
    for el in root.iter():
        style_val = el.get("style", "").strip()
        if not style_val:
            continue
        css: dict[str, str] = {}
        for m in re.finditer(r"([\w-]+)\s*:\s*([^;]+?)(?=\s*(?:;|$))", style_val):
            css[m.group(1).strip()] = m.group(2).strip()

        changed = False
        remaining: dict[str, str] = {}
        for prop, val in css.items():
            if prop not in _CSS_PROPS_TO_INLINE:
                remaining[prop] = val
                continue
            if prop in _COLOR_PROPS and val.lower() not in _PASSTHROUGH:
                val = _normalize_css_color(val)
            if el.get(prop) is None:
                el.set(prop, val)
                changed = True

        new_style = ";".join(f"{k}:{v}" for k, v in remaining.items())
        if new_style != style_val:
            if new_style:
                el.set("style", new_style)
            elif "style" in el.attrib:
                del el.attrib["style"]
            changed = True

        if changed:
            modified += 1
    return modified


def _remove_invisible_elements(root: ET.Element) -> int:
    """
    Supprime les éléments SVG qui ne produiront aucun point de broderie.
    Traitement bottom-up pour éviter les références brisées.
    Ne supprime jamais <svg>, <defs>, <style>, <metadata>.
    Retourne le nombre d'éléments supprimés.
    """
    _SVG_NS = "http://www.w3.org/2000/svg"
    _SAFE_LOCAL = frozenset(["svg", "defs", "style", "metadata", "title", "desc", "clippath", "mask", "symbol"])
    _CONTAINER_LOCAL = frozenset(["g", "svg", "defs", "clippath", "mask", "symbol"])

    def _local(tag: str) -> str:
        return (tag.split("}")[-1] if "}" in tag else tag).lower()

    def _is_invisible(el: ET.Element) -> bool:
        loc = _local(el.tag)
        if loc in _SAFE_LOCAL:
            return False
        display = el.get("display", "").strip().lower()
        if display == "none":
            return True
        visibility = el.get("visibility", "").strip().lower()
        if visibility == "hidden":
            return True
        try:
            if float(el.get("opacity", "1")) == 0.0:
                return True
        except ValueError:
            pass
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()
        fill_invisible = fill in ("none", "transparent", "")
        stroke_invisible = stroke in ("none", "transparent", "")
        if fill_invisible and stroke_invisible and loc not in _CONTAINER_LOCAL:
            return True
        return False

    def _remove_from(parent: ET.Element) -> int:
        count = 0
        to_remove = []
        for child in list(parent):
            count += _remove_from(child)
            if _is_invisible(child):
                to_remove.append(child)
        for el in to_remove:
            parent.remove(el)
            count += 1
        return count

    return _remove_from(root)


def _strip_clip_path_refs(root: ET.Element) -> int:
    """
    Retire les attributs clip-path et mask de tous les éléments.
    Les paths s'affichent sans clipping — tous leurs pixels sont brodables.
    Retourne le nombre d'attributs supprimés.
    """
    removed = 0
    for el in root.iter():
        if el.attrib.pop("clip-path", None) is not None:
            removed += 1
        if el.attrib.pop("mask", None) is not None:
            removed += 1
    return removed


def _annotate_fill_paths_for_inkstitch(root: ET.Element) -> int:
    """
    Ajoute inkstitch:fill_method="auto_fill" sur tous les paths remplis.

    Sans cet attribut, Ink/Stitch peut heuristiquement traiter des paths remplis
    en running_stitch (contours seulement) au lieu de tatami fill, surtout pour
    les paths complexes issus de vectorisation raster.
    Ne touche pas aux éléments déjà annotés ou en running_stitch intentionnel.
    Retourne le nombre d'éléments annotés.
    """
    _FILL_TAGS = frozenset([
        f"{{{_SVG_NS}}}path", "path",
        f"{{{_SVG_NS}}}rect", "rect",
        f"{{{_SVG_NS}}}circle", "circle",
        f"{{{_SVG_NS}}}ellipse", "ellipse",
        f"{{{_SVG_NS}}}polygon", "polygon",
    ])
    _FILL_METHOD_ATTR = f"{{{_INKSTITCH_NS}}}fill_method"
    _STROKE_METHOD_ATTR = f"{{{_INKSTITCH_NS}}}stroke_method"
    _NONE_FILLS = frozenset(["none", "transparent", ""])

    annotated = 0
    for el in root.iter():
        if el.tag not in _FILL_TAGS:
            continue
        fill = el.get("fill", "").strip().lower()
        if fill in _NONE_FILLS:
            continue
        if el.get(_STROKE_METHOD_ATTR):
            continue
        if el.get(_FILL_METHOD_ATTR):
            continue
        el.set(_FILL_METHOD_ATTR, "auto_fill")
        annotated += 1
    return annotated


def prepare_svg_for_inkstitch(svg_path: Path) -> dict[str, int]:
    """
    Normalise le SVG pour maximiser la compatibilité Ink/Stitch.

    Étape A — Inkscape CLI :
      textes/formes → paths, clones résolus, groupes aplatis (transforms appliqués),
      deuxième passe object-to-path, defs nettoyées.

    Étape B — Python :
      styles CSS inlinés en attributs explicites, éléments invisibles supprimés,
      clip-path et mask retirés, fills annotés inkstitch:fill_method=auto_fill.

    Retourne un dict de compteurs pour logging.
    """
    stats: dict[str, int] = {
        "inkscape_run": 0,
        "styles_inlined": 0,
        "invisible_removed": 0,
        "clips_stripped": 0,
        "fills_annotated": 0,
    }

    inkscape = shutil.which("inkscape")
    if inkscape:
        actions = (
            "select-all;object-to-path;"
            "select-all;clone-unlink;"
            "select-all;selection-ungroup;"
            "select-all;object-to-path;"
            "vacuum-defs"
        )
        try:
            result = subprocess.run(
                [
                    inkscape,
                    f"--actions={actions}",
                    "--export-type=svg",
                    f"--export-filename={svg_path}",
                    str(svg_path),
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.warning(
                    "[svg-prep] Inkscape exit %d : %s",
                    result.returncode,
                    result.stderr.decode(errors="replace")[:300],
                )
            else:
                stats["inkscape_run"] = 1
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("[svg-prep] Inkscape normalisation échouée : %s", exc)
    else:
        logger.warning("[svg-prep] Inkscape absent, normalisation CLI ignorée")

    try:
        _register_svg_namespaces()
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        logger.warning("[svg-prep] Parse SVG échoué après normalisation Inkscape : %s", exc)
        return stats

    stats["styles_inlined"] = _inline_svg_styles(root)
    stats["invisible_removed"] = _remove_invisible_elements(root)
    stats["clips_stripped"] = _strip_clip_path_refs(root)
    stats["fills_annotated"] = _annotate_fill_paths_for_inkstitch(root)

    if any(v > 0 for k, v in stats.items() if k != "inkscape_run"):
        tree.write(svg_path, encoding="unicode", xml_declaration=True)

    return stats


def get_svg_colors_with_count(svg_path: Path) -> list[dict]:
    """
    Retourne la liste des couleurs distinctes du SVG avec le nombre d'éléments par couleur.
    Inclut les éléments fill colorés ET les éléments stroke-only (running_stitch : fill=none, stroke=color).
    Résultat trié par count décroissant : [{'hex': '#rrggbb', 'count': N}, ...]
    """
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError:
        return []

    counts: dict[str, int] = {}
    for el in root.iter():
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()
        if fill and fill not in ("none", "transparent") and not fill.startswith("url("):
            counts[fill] = counts.get(fill, 0) + 1
        elif (not fill or fill in ("none", "transparent")) and stroke and stroke not in ("none", "") and not stroke.startswith("url("):
            # Éléments running_stitch : fill absent/none, couleur portée par stroke
            counts[stroke] = counts.get(stroke, 0) + 1

    return sorted(
        [{"hex": h, "count": c} for h, c in counts.items()],
        key=lambda x: -x["count"],
    )


def merge_svg_colors(svg_path: Path, source_hex: str, target_hex: str) -> int:
    """
    Remplace tous les fills source_hex par target_hex dans le SVG. Modifie le fichier en place.
    Retourne le nombre d'éléments modifiés.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    src = source_hex.strip().lower()
    tgt = target_hex.strip().lower()
    modified = 0

    for el in root.iter():
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()
        if fill == src:
            el.set("fill", tgt)
            modified += 1
        elif fill in ("none", "") and stroke == src:
            # Élément running_stitch : couleur portée par stroke
            el.set("stroke", tgt)
            modified += 1

    if modified:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info(
            "[editor] %d éléments %s → %s dans %s", modified, src, tgt, svg_path.name
        )

    return modified


def change_svg_color(svg_path: Path, old_hex: str, new_hex: str) -> int:
    """Remplace old_hex par new_hex (remappage vers un fil Brother choisi par l'utilisateur)."""
    return merge_svg_colors(svg_path, old_hex, new_hex)


def remove_excluded_colors_from_svg(svg_path: Path, excluded_hexes: list[str]) -> int:
    """
    Supprime tous les éléments SVG dont le fill correspond à l'une des couleurs exclues.
    Retourne le nombre d'éléments supprimés.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    excluded_lower = {h.lower() for h in excluded_hexes}
    removed = 0

    for parent in root.iter():
        for child in list(parent):
            fill = child.get("fill", "").strip().lower()
            if fill in excluded_lower:
                parent.remove(child)
                removed += 1

    if removed:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info(
            "[excluded] %d éléments couleur exclue supprimés dans %s",
            removed,
            svg_path.name,
        )

    return removed


# ---------------------------------------------------------------------------
# Phase 11 — Historique undo/redo (snapshots fichiers)
# ---------------------------------------------------------------------------


def save_svg_snapshot(svg_path: Path, media_root: Path, job_id: str, history: dict) -> dict:
    """
    Copie le SVG courant en snapshot avant une opération d'édition.
    Vide la pile 'future' (redo impossible après une nouvelle action).
    Retourne l'historique mis à jour : {'past': [...], 'future': []}.
    """
    snap_dir = media_root / _SNAPSHOT_SUBDIR / job_id
    snap_dir.mkdir(parents=True, exist_ok=True)

    past: list[str] = list(history.get("past", []))

    snap_index = len(past)
    snap_path = snap_dir / f"snap_{snap_index}.svg"
    shutil.copy2(svg_path, snap_path)

    past.append(str(snap_path.relative_to(media_root)))
    if len(past) > _SNAPSHOT_MAX:
        old_rel = past.pop(0)
        try:
            (media_root / old_rel).unlink(missing_ok=True)
        except OSError:
            pass

    return {"past": past, "future": []}


def undo_svg(svg_path: Path, media_root: Path, history: dict) -> tuple[bool, dict]:
    """
    Restaure le snapshot précédent (dernier élément de 'past').
    Pousse l'état courant dans 'future'.
    Retourne (success, new_history).
    """
    past: list[str] = list(history.get("past", []))
    future: list[str] = list(history.get("future", []))

    if not past:
        return False, history

    snap_rel = past.pop()
    snap_path = media_root / snap_rel
    if not snap_path.exists():
        return False, history

    # Sauvegarde l'état courant dans future avant d'écraser
    cur_index = len(past) + len(future)
    cur_snap_dir = snap_path.parent
    cur_snap_path = cur_snap_dir / f"cur_{cur_index}.svg"
    shutil.copy2(svg_path, cur_snap_path)
    future.insert(0, str(cur_snap_path.relative_to(media_root)))

    shutil.copy2(snap_path, svg_path)
    logger.info("[undo] Restauré snapshot %s", snap_rel)

    return True, {"past": past, "future": future}


def redo_svg(svg_path: Path, media_root: Path, history: dict) -> tuple[bool, dict]:
    """
    Restaure le snapshot suivant (premier élément de 'future').
    Pousse l'état courant dans 'past'.
    Retourne (success, new_history).
    """
    past: list[str] = list(history.get("past", []))
    future: list[str] = list(history.get("future", []))

    if not future:
        return False, history

    snap_rel = future.pop(0)
    snap_path = media_root / snap_rel
    if not snap_path.exists():
        return False, history

    cur_index = len(past)
    cur_snap_dir = snap_path.parent
    cur_snap_path = cur_snap_dir / f"snap_{cur_index}.svg"
    shutil.copy2(svg_path, cur_snap_path)
    past.append(str(cur_snap_path.relative_to(media_root)))

    shutil.copy2(snap_path, svg_path)
    logger.info("[redo] Restauré snapshot %s", snap_rel)

    return True, {"past": past, "future": future}


def reset_svg(svg_path: Path, media_root: Path, history: dict) -> tuple[bool, dict]:
    """
    Restaure le premier snapshot (état avant la première édition) et efface tout l'historique.
    Retourne (success, new_history).
    """
    past: list[str] = list(history.get("past", []))
    if not past:
        return False, history

    first_snap_path = media_root / past[0]
    if not first_snap_path.exists():
        return False, history

    shutil.copy2(first_snap_path, svg_path)
    logger.info("[reset] Restauré état initial %s", past[0])
    return True, {"past": [], "future": []}


# ---------------------------------------------------------------------------
# Phase 11 — Réordonner les couches (ordre de broderie)
# ---------------------------------------------------------------------------


def reorder_svg_colors(svg_path: Path, ordered_hexes: list[str]) -> None:
    """
    Réordonne les éléments SVG par couleur de fill selon ordered_hexes.
    Les éléments de la première couleur seront brodés en premier par Ink/Stitch.
    Les éléments sans fill dans ordered_hexes restent à la fin (arrière-plan).
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return

    root = tree.getroot()
    ordered_lower = [h.strip().lower() for h in ordered_hexes]

    def _elem_fill(el: ET.Element) -> str:
        return el.get("fill", "").strip().lower()

    children = list(root)

    def _color_rank(el: ET.Element) -> int:
        fill = _elem_fill(el)
        if fill in ordered_lower:
            return ordered_lower.index(fill)
        # Vérifier les enfants directs (groupe <g fill="...">)
        for child in el:
            fill = _elem_fill(child)
            if fill in ordered_lower:
                return ordered_lower.index(fill)
        return len(ordered_lower)

    children.sort(key=_color_rank)

    for child in list(root):
        root.remove(child)
    for child in children:
        root.append(child)

    tree.write(svg_path, encoding="unicode", xml_declaration=True)
    logger.info("[reorder] Couleurs réordonnées dans %s : %s", svg_path.name, ordered_lower)


# ---------------------------------------------------------------------------
# Phase 11 — Type de point par couleur (fill vs running stitch)
# ---------------------------------------------------------------------------


def get_stitch_types(svg_path: Path) -> dict[str, str]:
    """
    Retourne {hex_color: stitch_type} pour chaque couleur du SVG.
    stitch_type ∈ {'auto_fill', 'running_stitch'}
    """
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError:
        return {}

    result: dict[str, str] = {}
    for el in root.iter():
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()
        stroke_method = el.get(_INKSTITCH_STROKE_METHOD, "")

        if stroke and stroke not in ("none", "") and fill in ("none", ""):
            # Contour sans fill → running_stitch
            color = stroke
            result[color] = "running_stitch"
        elif fill and fill not in ("none", "transparent") and not fill.startswith("url("):
            if stroke_method == "running_stitch":
                result[fill] = "running_stitch"
            else:
                result.setdefault(fill, "auto_fill")

    return result


def set_stitch_type(svg_path: Path, hex_color: str, stitch_type: str) -> int:
    """
    Applique le type de point à tous les éléments de la couleur donnée.
    - 'auto_fill' : fill=color, supprime stroke et inkstitch:stroke_method
    - 'running_stitch' : fill=none, stroke=color, inkstitch:stroke_method=running_stitch
    Retourne le nombre d'éléments modifiés.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    color = hex_color.strip().lower()
    modified = 0

    for el in root.iter():
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()

        is_this_color = (fill == color) or (
            fill in ("none", "") and stroke == color
        )
        if not is_this_color:
            continue

        if stitch_type == "auto_fill":
            el.set("fill", color)
            el.attrib.pop("stroke", None)
            el.attrib.pop(_INKSTITCH_STROKE_METHOD, None)
        elif stitch_type == "running_stitch":
            el.set("fill", "none")
            el.set("stroke", color)
            el.set(_INKSTITCH_STROKE_METHOD, "running_stitch")

        modified += 1

    if modified:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info(
            "[stitch-type] %d éléments %s → %s dans %s",
            modified, color, stitch_type, svg_path.name,
        )

    return modified


# ---------------------------------------------------------------------------
# Phase 11 — Densité de point par couleur (inkstitch:row_spacing_mm)
# ---------------------------------------------------------------------------


def get_stitch_densities(svg_path: Path) -> dict[str, float]:
    """
    Retourne {hex_color: density_mm} pour chaque couleur.
    Défaut : 0.4 si l'attribut est absent.
    """
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError:
        return {}

    result: dict[str, float] = {}
    for el in root.iter():
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()
        color = fill if fill and fill not in ("none", "transparent") else stroke
        if not color or color in ("none", ""):
            continue
        raw = el.get(_INKSTITCH_ROW_SPACING, "")
        try:
            density = float(raw)
        except (ValueError, TypeError):
            density = 0.4
        result.setdefault(color, density)

    return result


def set_stitch_density(svg_path: Path, hex_color: str, density_mm: float) -> int:
    """
    Applique inkstitch:row_spacing_mm sur tous les éléments de la couleur.
    Retourne le nombre d'éléments modifiés.
    """
    _register_svg_namespaces()
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    color = hex_color.strip().lower()
    density_str = f"{density_mm:.2f}"
    modified = 0

    for el in root.iter():
        fill = el.get("fill", "").strip().lower()
        stroke = el.get("stroke", "").strip().lower()
        if fill == color or (fill in ("none", "") and stroke == color):
            el.set(_INKSTITCH_ROW_SPACING, density_str)
            modified += 1

    if modified:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info(
            "[density] %d éléments %s → %.2f mm dans %s",
            modified, color, density_mm, svg_path.name,
        )

    return modified
