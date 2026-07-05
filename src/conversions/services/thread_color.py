"""
Snap des couleurs SVG vers la palette de fils Brother réels avant envoi à Ink/Stitch.
Utilise la distance perceptuelle CIE Lab pour trouver le fil le plus proche.
"""

import logging
import math
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# Seuils de classification ΔE (CIE76, D65) pour l'écart perceptuel entre une couleur
# source et le fil Brother snappé. Repères usuels : ΔE<10 = non perceptible en usage
# courant, 10-20 = différence visible mais tolérable, ≥20 = écart net (ex: bleu-violet
# rendu "Purple"). Calibré avec l'utilisatrice beta (session fidélité couleur).
LIGHT_DELTA_E_THRESHOLD = 10.0
NOTABLE_DELTA_E_THRESHOLD = 20.0

# Cache module-level : chargé une seule fois par process worker
_BROTHER_PALETTE: list[tuple[int, int, int, str]] | None = None
_PALETTE_LOADED = False

_PALETTES_SEARCH_PATHS = [
    # macOS — installation .app Inkstitch bundle
    Path.home()
    / "Library"
    / "Application Support"
    / "org.inkscape.Inkscape"
    / "config"
    / "inkscape"
    / "extensions"
    / "inkstitch"
    / "inkstitch.app"
    / "Contents"
    / "Resources"
    / "palettes",
    # Linux — extensions Inkscape utilisateur
    Path.home() / ".config" / "inkscape" / "extensions" / "inkstitch" / "palettes",
    # Linux — extensions Inkscape système
    Path("/usr/share/inkscape/extensions/inkstitch/palettes"),
]

_BROTHER_PALETTE_NAME = "InkStitch Brother Embroidery.gpl"


def _find_brother_palette() -> Path | None:
    """
    Cherche le fichier GPL de la palette Brother Embroidery dans l'installation Ink/Stitch.
    Tente aussi de dériver le chemin depuis INKSTITCH_EXECUTABLE si configuré.
    """
    # Dériver depuis la variable d'environnement Django si disponible
    try:
        from django.conf import settings

        executable = getattr(settings, "INKSTITCH_EXECUTABLE", "")
        if executable:
            exe_path = Path(executable)
            # Remonter depuis l'exécutable vers le dossier palettes du bundle
            for candidate in [
                exe_path.parent.parent / "Resources" / "palettes",
                exe_path.parent.parent.parent / "Resources" / "palettes",
                exe_path.parent / "palettes",
                # Windows — layout inkstitch\bin\inkstitch.exe → inkstitch\palettes
                exe_path.parent.parent / "palettes",
            ]:
                p = candidate / _BROTHER_PALETTE_NAME
                if p.exists():
                    return p
    except Exception:
        pass

    for palettes_dir in _PALETTES_SEARCH_PATHS:
        p = palettes_dir / _BROTHER_PALETTE_NAME
        if p.exists():
            return p

    return None


def _parse_gpl(path: Path) -> list[tuple[int, int, int, str]]:
    """Parse un fichier GIMP Palette (.gpl) et retourne la liste (R, G, B, name)."""
    colors: list[tuple[int, int, int, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if (
            not line
            or line.startswith("#")
            or line.startswith("GIMP")
            or line.startswith("Name")
            or line.startswith("Columns")
        ):
            continue
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            name = parts[3].strip() if len(parts) > 3 else ""
            colors.append((r, g, b, name))
        except ValueError:
            continue
    return colors


def _rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """
    Conversion RGB → CIE Lab (D65, observateur 2°).
    Stdlib Python uniquement (math).
    """

    def _linearize(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = _linearize(r), _linearize(g), _linearize(b)

    # sRGB → XYZ D65
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041

    # Normaliser par illuminant D65
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    fx = x / xn
    fy = y / yn
    fz = z / zn

    eps = 0.008856
    kappa = 903.3

    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > eps else (kappa * t + 16.0) / 116.0

    fx, fy, fz = _f(fx), _f(fy), _f(fz)

    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b_val = 200.0 * (fy - fz)
    return L, a, b_val


def _lab_distance(
    c1: tuple[float, float, float], c2: tuple[float, float, float]
) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def classify_color_drift(delta_e: float) -> str:
    """Classifie un écart ΔE Lab en label lisible pour l'utilisatrice."""
    if delta_e >= NOTABLE_DELTA_E_THRESHOLD:
        return "écart notable"
    if delta_e >= LIGHT_DELTA_E_THRESHOLD:
        return "léger écart"
    return "fidèle"


def hex_delta_e(hex1: str, hex2: str) -> float:
    """
    Distance perceptuelle CIE Lab entre deux couleurs hex '#rrggbb'.
    Retourne 0.0 si l'une des deux couleurs est invalide (pas de couleur à comparer).
    """
    try:
        r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
        r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    except (ValueError, IndexError):
        return 0.0
    return _lab_distance(_rgb_to_lab(r1, g1, b1), _rgb_to_lab(r2, g2, b2))


def _load_palette() -> list[tuple[int, int, int, str]] | None:
    global _BROTHER_PALETTE, _PALETTE_LOADED
    if _PALETTE_LOADED:
        return _BROTHER_PALETTE
    _PALETTE_LOADED = True
    path = _find_brother_palette()
    if path is None:
        logger.warning(
            "[thread_color] Palette Brother Embroidery introuvable — snap désactivé."
        )
        return None
    _BROTHER_PALETTE = _parse_gpl(path)
    logger.info(
        "[thread_color] Palette Brother chargée : %d fils depuis %s",
        len(_BROTHER_PALETTE),
        path.name,
    )
    return _BROTHER_PALETTE


def snap_svg_colors_to_brother_palette(svg_path: Path) -> None:
    """
    Remplace chaque couleur fill='#rrggbb' du SVG par la couleur du fil Brother
    perceptuellement le plus proche (distance CIE Lab). Modifie le fichier en place.
    Silencieux si la palette est absente ou si le fichier est invalide.
    """
    palette = _load_palette()
    if not palette:
        return

    # Pré-calculer les Lab pour toute la palette une fois
    palette_lab = [(_rgb_to_lab(r, g, b), name, r, g, b) for r, g, b, name in palette]

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return

    root = tree.getroot()
    replacements: dict[str, str] = {}

    def _snap(hex_color: str) -> str:
        if hex_color in replacements:
            return replacements[hex_color]
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
        except ValueError:
            return hex_color
        src_lab = _rgb_to_lab(r, g, b)
        best_lab, best_name, br, bg, bb = min(
            palette_lab, key=lambda e: _lab_distance(src_lab, e[0])
        )
        snapped = f"#{br:02x}{bg:02x}{bb:02x}"
        if snapped != hex_color:
            logger.info("[thread_color] %s → %s (%s)", hex_color, snapped, best_name)
        replacements[hex_color] = snapped
        return snapped

    changed = False
    for el in root.iter():
        fill = el.get("fill", "")
        if fill.startswith("#") and len(fill) == 7:
            snapped = _snap(fill)
            if snapped != fill:
                el.set("fill", snapped)
                changed = True

        stroke = el.get("stroke", "")
        if stroke.startswith("#") and len(stroke) == 7:
            snapped = _snap(stroke)
            if snapped != stroke:
                el.set("stroke", snapped)
                changed = True

    if changed:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info(
            "[thread_color] %d couleur(s) snappée(s) vers palette Brother dans %s",
            sum(1 for k, v in replacements.items() if k != v),
            svg_path.name,
        )


def get_brother_palette() -> list[dict]:
    """Retourne la palette Brother sous forme [{hex, name}]. Vide si palette absente."""
    palette = _load_palette()
    if not palette:
        return []
    return [
        {"hex": f"#{r:02x}{g:02x}{b:02x}", "name": name}
        for r, g, b, name in palette
    ]


def get_snap_preview(hex_colors: list[str]) -> list[dict]:
    """
    Pour chaque couleur SVG hex, retourne le fil Brother le plus proche.
    Marque collision=True si deux couleurs SVG différentes mapperaient vers le même fil.
    Format : [{'svg_hex': '#rrggbb', 'brother_hex': '#rrggbb', 'brother_name': str, 'collision': bool}]
    Retourne liste vide si palette absente.
    """
    palette = _load_palette()
    if not palette:
        return []

    palette_lab = [(_rgb_to_lab(r, g, b), name, r, g, b) for r, g, b, name in palette]

    results: list[dict] = []
    brother_hex_to_svg: dict[str, str] = {}

    for hex_color in hex_colors:
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
        except (ValueError, IndexError):
            results.append({"svg_hex": hex_color, "brother_hex": hex_color, "brother_name": "", "collision": False})
            continue

        src_lab = _rgb_to_lab(r, g, b)
        best_lab, best_name, br, bg, bb = min(palette_lab, key=lambda e: _lab_distance(src_lab, e[0]))
        brother_hex = f"#{br:02x}{bg:02x}{bb:02x}"
        delta_e = _lab_distance(src_lab, best_lab)

        # Détection collision : ce fil Brother est-il déjà assigné à une autre couleur SVG ?
        collision = brother_hex in brother_hex_to_svg and brother_hex_to_svg[brother_hex] != hex_color
        if not collision:
            brother_hex_to_svg[brother_hex] = hex_color

        results.append({
            "svg_hex": hex_color,
            "brother_hex": brother_hex,
            "brother_name": best_name,
            "collision": collision,
            "delta_e": round(delta_e, 1),
            "notable_drift": delta_e >= NOTABLE_DELTA_E_THRESHOLD,
        })

    return results
