"""
Pipeline d'extraction vectorielle depuis un PDF via pdftocairo (poppler).
Utilisé pour les PDFs vectoriels (logos, designs graphiques) qui ne doivent
pas passer par la rasterisation → revectorisation.
"""
import logging
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

_SVG_NS = 'http://www.w3.org/2000/svg'


class PDFExtractionError(Exception):
    """Échec de l'extraction SVG depuis le PDF."""
    pass


class GradientNotSupportedError(Exception):
    """Le PDF contient des dégradés de couleur, non brodables en aplats."""
    pass


def extract_vector_svg_from_pdf(pdf_path: Path, output_svg: Path) -> None:
    """
    Extrait les vecteurs du PDF en SVG via pdftocairo (poppler, déjà installé).
    Première page uniquement. Timeout 30s.
    """
    pdftocairo = shutil.which('pdftocairo')
    if not pdftocairo:
        raise PDFExtractionError(
            'pdftocairo introuvable. Installez poppler : brew install poppler'
        )

    result = subprocess.run(
        [pdftocairo, '-svg', '-f', '1', '-l', '1', str(pdf_path), str(output_svg)],
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0 or not output_svg.exists() or output_svg.stat().st_size == 0:
        stderr = result.stderr.decode(errors='replace').strip()
        raise PDFExtractionError(
            f'Extraction SVG depuis le PDF échouée : {stderr or "erreur inconnue"}'
        )

    logger.info('[pdf] extraction SVG via pdftocairo : %s (%d Ko)',
                pdf_path.name, output_svg.stat().st_size // 1024)


def is_vector_pdf_svg(svg_path: Path) -> bool:
    """
    Détecte si le SVG extrait contient des vecteurs (PDF vectoriel)
    ou uniquement des images raster (PDF scanné).
    Un PDF scanné embarque un <image>, un PDF vectoriel a des <path>.
    """
    try:
        content = svg_path.read_text(encoding='utf-8', errors='replace')
        path_count = content.count('<path ')
        image_count = content.count('<image ')
        logger.info('[pdf] analyse SVG : %d paths, %d images embarquées', path_count, image_count)
        return path_count >= 5 and image_count == 0
    except OSError:
        return False


def postprocess_vector_svg(svg_path: Path) -> None:
    """
    Prépare le SVG vectoriel extrait d'un PDF pour Ink/Stitch :
    1. Détecte les dégradés (non brodables) → GradientNotSupportedError
    2. Supprime les strokes (évite des satin-stitches parasites sur les contours)
    3. Simplifie les nœuds via Inkscape pour réduire la densité de points

    Modifie le fichier en place.
    """
    ET.register_namespace('', _SVG_NS)
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        raise PDFExtractionError(f'SVG invalide après extraction PDF : {exc}') from exc

    # 1. Détecter les dégradés → erreur explicite
    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if tag_local in ('linearGradient', 'radialGradient'):
            raise GradientNotSupportedError(
                'Ce design contient des dégradés de couleur qui ne sont pas brodables. '
                'Convertissez les dégradés en aplats de couleur dans un logiciel vectoriel '
                '(Illustrator, Inkscape) avant de relancer.'
            )

    # 2. Supprimer les strokes sur tous les éléments
    # pdftocairo réplique le stroke avec la même couleur que le fill → satin-stitches parasites
    _stroke_attrs = ('stroke', 'stroke-width', 'stroke-opacity',
                     'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit')
    changed = False
    for el in root.iter():
        if el.get('stroke') and el.get('stroke') != 'none':
            el.set('stroke', 'none')
            for attr in _stroke_attrs[1:]:
                el.attrib.pop(attr, None)
            changed = True

    if changed:
        tree.write(svg_path, encoding='unicode', xml_declaration=True)
        logger.info('[pdf] strokes supprimés du SVG vectoriel')

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
    ET.register_namespace('', _SVG_NS)
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return 0

    vb = root.get('viewBox', '')
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
    ns_path = f'{{{_SVG_NS}}}path'
    ns_rect = f'{{{_SVG_NS}}}rect'
    _coord_re = re.compile(r'[-+]?\d*\.?\d+')

    # Inspecter uniquement les premiers éléments directs du root (fond = premier)
    candidates = [ch for ch in root if ch.tag in (ns_rect, 'rect', ns_path, 'path')]
    if not candidates:
        return 0

    first = candidates[0]
    fill = first.get('fill', '')
    if not fill or fill in ('none', 'transparent'):
        return 0

    if first.tag in (ns_rect, 'rect'):
        try:
            rw = float(first.get('width', 0))
            rh = float(first.get('height', 0))
            coverage = (rw * rh) / viewbox_area
        except ValueError:
            return 0
    else:
        d = first.get('d', '')
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
            tree.write(svg_path, encoding='unicode', xml_declaration=True)
            logger.info('[pdf] fond de page supprimé (coverage=%.0f%%, fill=%s)', coverage * 100, fill)
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
        return f'#{r:02X}{g:02X}{b:02X}'

    content = svg_path.read_text(encoding='utf-8', errors='replace')
    _pct_color_re = re.compile(r'rgb\(([0-9.]+)%,\s*([0-9.]+)%,\s*([0-9.]+)%\)')
    new_content, count = _pct_color_re.subn(_to_hex, content)
    if count:
        svg_path.write_text(new_content, encoding='utf-8')
        logger.info('[pdf] %d couleur(s) rgb(%%) → hex dans le SVG', count)


def _simplify_pdf_svg(svg_path: Path) -> None:
    """
    Réduit le nombre de nœuds via Inkscape object-to-path + path-simplify.
    Silencieux en cas d'échec : le SVG original reste utilisable.
    """
    inkscape = shutil.which('inkscape')
    if not inkscape:
        return

    before_kb = svg_path.stat().st_size // 1024
    try:
        result = subprocess.run(
            [inkscape,
             f'--actions=select-all;object-to-path;path-simplify;export-do',
             '--export-plain-svg',
             f'--export-filename={svg_path}',
             str(svg_path)],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0 and svg_path.exists() and svg_path.stat().st_size > 0:
            after_kb = svg_path.stat().st_size // 1024
            logger.info('[pdf] SVG simplifié par Inkscape : %d Ko → %d Ko', before_kb, after_kb)
        else:
            logger.warning('[pdf] Inkscape simplify échoué (code %d) — SVG utilisé tel quel',
                           result.returncode)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning('[pdf] Inkscape simplify %s — SVG utilisé tel quel', exc)
