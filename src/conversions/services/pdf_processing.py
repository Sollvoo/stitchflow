"""
Pipeline d'extraction vectorielle depuis un PDF via pdftocairo (poppler).
Utilisé pour les PDFs vectoriels (logos, designs graphiques) qui ne doivent
pas passer par la rasterisation → revectorisation.
"""

import logging
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

_SVG_NS = "http://www.w3.org/2000/svg"
_PT_TO_MM = 25.4 / 72


class PDFExtractionError(Exception):
    """Échec de l'extraction SVG depuis le PDF."""

    pass


class GradientNotSupportedError(Exception):
    """Le PDF contient des dégradés de couleur, non brodables en aplats."""

    pass


def _find_pdftocairo() -> str | None:
    """Cherche pdftocairo dans PATH puis dans le vendor adapté à la plateforme."""
    found = shutil.which("pdftocairo")
    if found:
        return found
    try:
        from django.conf import settings as djsettings

        vendor_bin = getattr(djsettings, "POPPLER_BIN_PATH", None)
        if vendor_bin:
            exe_name = "pdftocairo.exe" if sys.platform == "win32" else "pdftocairo"
            candidate = Path(vendor_bin) / exe_name
            if candidate.exists():
                return str(candidate)
    except Exception:
        pass
    return None


def extract_vector_svg_from_pdf(pdf_path: Path, output_svg: Path) -> None:
    """
    Extrait les vecteurs du PDF en SVG via pdftocairo (poppler).
    Première page uniquement. Timeout 30s.
    """
    pdftocairo = _find_pdftocairo()
    if not pdftocairo:
        raise PDFExtractionError(
            "pdftocairo introuvable. "
            "macOS : brew install poppler | "
            "Windows : choco install poppler (admin) ou placer les binaires dans vendor/poppler-*/Library/bin/"
        )

    result = subprocess.run(
        [pdftocairo, "-svg", "-f", "1", "-l", "1", str(pdf_path), str(output_svg)],
        capture_output=True,
        timeout=30,
    )

    if (
        result.returncode != 0
        or not output_svg.exists()
        or output_svg.stat().st_size == 0
    ):
        stderr = result.stderr.decode(errors="replace").strip()
        raise PDFExtractionError(
            f'Extraction SVG depuis le PDF échouée : {stderr or "erreur inconnue"}'
        )

    logger.info(
        "[pdf] extraction SVG via pdftocairo : %s (%d Ko)",
        pdf_path.name,
        output_svg.stat().st_size // 1024,
    )


def is_vector_pdf_svg(svg_path: Path) -> bool:
    """
    Détecte si le SVG extrait contient des vecteurs (PDF vectoriel)
    ou uniquement des images raster (PDF scanné).
    Un PDF scanné embarque un <image>, un PDF vectoriel a des <path>.
    """
    try:
        content = svg_path.read_text(encoding="utf-8", errors="replace")
        path_count = content.count("<path ")
        image_count = content.count("<image ")
        logger.info(
            "[pdf] analyse SVG : %d paths, %d images embarquées",
            path_count,
            image_count,
        )
        return path_count >= 5 and image_count == 0
    except OSError:
        return False


def normalize_svg_dimensions_to_mm(svg_path: Path) -> tuple[float, float] | None:
    """
    pdftocairo émet width/height sans unité (ex : `width="225"`) — convention poppler :
    ce sont des points PDF (1/72 in), pas des pixels CSS. Sans cette normalisation,
    `_parse_length_mm` (svg_utils.py) traite un nombre sans unité comme des px (96 dpi),
    ce qui fausse silencieusement la taille physique du design de ~25% (72 vs 96 dpi)
    dès que l'utilisateur ne fixe pas de largeur cible explicite.

    Réécrit width/height en mm explicites en place (viewBox inchangé — le ratio
    unité-utilisateur → mm reste cohérent pour Ink/Stitch et scale_svg_to_width_mm).

    Retourne (width_mm, height_mm) ou None si les attributs sont absents/déjà unitisés.
    """
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    w_raw = root.get("width", "").strip()
    h_raw = root.get("height", "").strip()
    m_w = re.match(r"^([0-9.]+)$", w_raw)
    m_h = re.match(r"^([0-9.]+)$", h_raw)
    if not (m_w and m_h):
        return None

    width_mm = round(float(m_w.group(1)) * _PT_TO_MM, 2)
    height_mm = round(float(m_h.group(1)) * _PT_TO_MM, 2)
    root.set("width", f"{width_mm}mm")
    root.set("height", f"{height_mm}mm")
    tree.write(svg_path, encoding="unicode", xml_declaration=True)
    logger.info(
        "[pdf] dimensions normalisées : %spt×%spt → %smm×%smm",
        m_w.group(1), m_h.group(1), width_mm, height_mm,
    )
    return width_mm, height_mm


def postprocess_vector_svg(svg_path: Path) -> None:
    """
    Prépare le SVG vectoriel extrait d'un PDF pour Ink/Stitch :
    1. Normalise width/height (points poppler → mm explicites)
    2. Détecte les dégradés (non brodables) → GradientNotSupportedError
    3. Supprime les strokes (évite des satin-stitches parasites sur les contours)
    4. Simplifie les nœuds via Inkscape pour réduire la densité de points

    Modifie le fichier en place.
    """
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    normalize_svg_dimensions_to_mm(svg_path)

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        raise PDFExtractionError(f"SVG invalide après extraction PDF : {exc}") from exc

    # 1. Détecter les dégradés → erreur explicite
    for el in root.iter():
        tag_local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag_local in ("linearGradient", "radialGradient"):
            raise GradientNotSupportedError(
                "Ce design contient des dégradés de couleur qui ne sont pas brodables. "
                "Convertissez les dégradés en aplats de couleur dans un logiciel vectoriel "
                "(Illustrator, Inkscape) avant de relancer."
            )

    # 2. Supprimer les strokes sur tous les éléments
    # pdftocairo réplique le stroke avec la même couleur que le fill → satin-stitches parasites
    _stroke_attrs = (
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
    )
    changed = False
    for el in root.iter():
        if el.get("stroke") and el.get("stroke") != "none":
            el.set("stroke", "none")
            for attr in _stroke_attrs[1:]:
                el.attrib.pop(attr, None)
            changed = True

    if changed:
        tree.write(svg_path, encoding="unicode", xml_declaration=True)
        logger.info("[pdf] strokes supprimés du SVG vectoriel")

    # 2b. Normaliser les couleurs rgb(X%,...) → #RRGGBB
    # Ink/Stitch ne supporte pas la notation CSS pourcentages dans color.py
    _normalize_percentage_colors(svg_path)

    # 2c. Supprimer le fond de page PDF (premier élément couvrant > 90% du viewBox)
    # pdftocairo insère parfois un rect/path de fond coloré qui se brode comme un fil
    _remove_pdf_page_background(svg_path)

    # 3. Simplification des nœuds Inkscape (silencieux si absent ou timeout)
    _simplify_pdf_svg(svg_path)


def _remove_pdf_page_background(svg_path: Path) -> int:
    """
    Supprime le fond de page PDF : premier rect ou path enfant direct du root
    dont le bounding box couvre > 90% du viewBox, quelle que soit sa couleur.
    pdftocairo insère souvent ce fond coloré en premier élément du SVG.
    Retourne le nombre d'éléments supprimés (0 ou 1).
    """
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return 0

    vb = root.get("viewBox", "")
    vb_parts = vb.split() if vb else []
    if len(vb_parts) != 4:
        return 0
    try:
        vb_w, vb_h = float(vb_parts[2]), float(vb_parts[3])
    except ValueError:
        return 0
    if vb_w <= 0 or vb_h <= 0:
        return 0

    viewbox_area = vb_w * vb_h
    ns_path = f"{{{_SVG_NS}}}path"
    ns_rect = f"{{{_SVG_NS}}}rect"
    _coord_re = re.compile(r"[-+]?\d*\.?\d+")

    # Inspecter uniquement les premiers éléments directs du root (fond = premier)
    candidates = [ch for ch in root if ch.tag in (ns_rect, "rect", ns_path, "path")]
    if not candidates:
        return 0

    first = candidates[0]
    fill = first.get("fill", "")
    if not fill or fill in ("none", "transparent"):
        return 0

    if first.tag in (ns_rect, "rect"):
        try:
            rw = float(first.get("width", 0))
            rh = float(first.get("height", 0))
            coverage = (rw * rh) / viewbox_area
        except ValueError:
            return 0
    else:
        d = first.get("d", "")
        nums = [float(m) for m in _coord_re.findall(d)]
        if len(nums) < 4:
            return 0
        xs, ys = nums[0::2], nums[1::2]
        if not xs or not ys:
            return 0
        bbox_w = max(xs) - min(xs)
        bbox_h = max(ys) - min(ys)
        coverage = (bbox_w * bbox_h) / viewbox_area

    if coverage > 0.90:
        try:
            root.remove(first)
            tree.write(svg_path, encoding="unicode", xml_declaration=True)
            logger.info(
                "[pdf] fond de page supprimé (coverage=%.0f%%, fill=%s)",
                coverage * 100,
                fill,
            )
            return 1
        except ValueError:
            pass
    return 0


def _normalize_percentage_colors(svg_path: Path) -> None:
    """
    Convertit les couleurs rgb(X%,Y%,Z%) → #RRGGBB dans le SVG.
    pdftocairo émet des pourcentages CSS que Ink/Stitch ne sait pas parser.
    """

    def _to_hex(m: re.Match) -> str:
        r = min(255, round(float(m.group(1)) * 255 / 100))
        g = min(255, round(float(m.group(2)) * 255 / 100))
        b = min(255, round(float(m.group(3)) * 255 / 100))
        return f"#{r:02X}{g:02X}{b:02X}"

    content = svg_path.read_text(encoding="utf-8", errors="replace")
    _pct_color_re = re.compile(r"rgb\(([0-9.]+)%,\s*([0-9.]+)%,\s*([0-9.]+)%\)")
    new_content, count = _pct_color_re.subn(_to_hex, content)
    if count:
        svg_path.write_text(new_content, encoding="utf-8")
        logger.info("[pdf] %d couleur(s) rgb(%%) → hex dans le SVG", count)


def _simplify_pdf_svg(svg_path: Path) -> None:
    """
    Réduit le nombre de nœuds via Inkscape object-to-path + path-simplify.
    Silencieux en cas d'échec : le SVG original reste utilisable.
    """
    from .svg_utils import find_inkscape

    inkscape = find_inkscape()
    if not inkscape:
        return

    before_kb = svg_path.stat().st_size // 1024
    try:
        result = subprocess.run(
            [
                inkscape,
                "--actions=select-all;object-to-path;path-simplify;export-do",
                "--export-plain-svg",
                f"--export-filename={svg_path}",
                str(svg_path),
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0 and svg_path.exists() and svg_path.stat().st_size > 0:
            after_kb = svg_path.stat().st_size // 1024
            logger.info(
                "[pdf] SVG simplifié par Inkscape : %d Ko → %d Ko", before_kb, after_kb
            )
        else:
            logger.warning(
                "[pdf] Inkscape simplify échoué (code %d) — SVG utilisé tel quel",
                result.returncode,
            )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("[pdf] Inkscape simplify %s — SVG utilisé tel quel", exc)
