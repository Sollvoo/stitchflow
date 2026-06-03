"""
Service de traitement d'images PNG pour la vectorisation broderie.
Pipeline : validation → nettoyage → suppression fond → quantization → vectorisation SVG.
"""
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

PNG_MAGIC = b'\x89PNG'
PNG_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 Mo
PNG_MAX_DIMENSION = 5000

# Script helper pour isoler les crashes natifs de vtracer (SIGSEGV sur ARM64)
_VTRACER_HELPER = Path(__file__).parent / '_vtracer_helper.py'


class PNGValidationError(Exception):
    """Erreur levée quand le PNG est invalide pour le pipeline broderie."""
    pass


def validate_png(path: Path) -> None:
    """
    Vérifie que le fichier est un PNG valide avec des dimensions raisonnables.
    Lève PNGValidationError si invalide.
    """
    if path.stat().st_size > PNG_MAX_FILE_SIZE:
        raise PNGValidationError(
            f'Fichier trop volumineux. Maximum : {PNG_MAX_FILE_SIZE // (1024 * 1024)} Mo.'
        )

    with path.open('rb') as f:
        header = f.read(4)
    if header != PNG_MAGIC:
        raise PNGValidationError(
            'Le fichier ne semble pas être un PNG valide (signature incorrecte).'
        )

    try:
        with Image.open(path) as img:
            w, h = img.size
    except Exception as exc:
        raise PNGValidationError(f'Impossible de lire l\'image PNG : {exc}') from exc

    if w == 0 or h == 0:
        raise PNGValidationError('L\'image PNG a des dimensions nulles.')

    if w > PNG_MAX_DIMENSION or h > PNG_MAX_DIMENSION:
        raise PNGValidationError(
            f'Image trop grande ({w}×{h} px). Maximum : {PNG_MAX_DIMENSION} px par côté.'
        )


def remove_background(path: Path) -> Path:
    """
    Supprime le fond de l'image via rembg (IA) si disponible,
    sinon fallback sur un seuillage Pillow simple pour les fonds blancs.
    Retourne le chemin d'un fichier temporaire PNG RGBA (à supprimer par l'appelant).
    """
    try:
        import rembg
        with path.open('rb') as f:
            input_data = f.read()
        output_data = rembg.remove(input_data)
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.write(output_data)
        tmp.close()
        logger.info("Suppression fond rembg : %s", path.name)
        return Path(tmp.name)
    except Exception as exc:
        logger.warning("rembg indisponible ou erreur (%s), fallback seuillage Pillow.", exc)
        return _remove_background_pillow(path)


def _remove_background_pillow(path: Path) -> Path:
    """Fallback : supprime les pixels proches du blanc via seuillage simple."""
    with Image.open(path).convert('RGBA') as img:
        data = img.getdata()
        new_data = []
        for r, g, b, a in data:
            if r > 230 and g > 230 and b > 230:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((r, g, b, a))
        img.putdata(new_data)
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        img.save(tmp.name, 'PNG')
        tmp.close()
    return Path(tmp.name)


def preprocess_image(path: Path) -> Path:
    """
    Prépare l'image pour la vectorisation : améliore le contraste et la netteté.
    Ne quantifie PAS les couleurs ici — c'est le rôle de _vectorize_potrace.
    Retourne le chemin d'un fichier temporaire PNG à supprimer par l'appelant.
    """
    with Image.open(path) as img:
        working = img.convert('RGB')

        working = ImageEnhance.Contrast(working).enhance(1.3)
        working = ImageEnhance.Sharpness(working).enhance(1.5)
        working = working.filter(ImageFilter.SMOOTH)

        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        working.save(tmp.name, 'PNG')
        tmp.close()

    return Path(tmp.name)


def _flatten_alpha(path: Path) -> Path:
    """Convertit une image RGBA en RGB sur fond blanc avant vectorisation."""
    with Image.open(path) as img:
        if img.mode not in ('RGBA', 'LA', 'P'):
            return path
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode in ('RGBA', 'LA'):
            background.paste(img.convert('RGB'), mask=img.split()[-1])
        else:
            background.paste(img.convert('RGB'))
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        background.save(tmp.name, 'PNG')
        tmp.close()
    return Path(tmp.name)


def vectorize_to_svg(png_path: Path, n_colors: int = 6) -> Path:
    """
    Vectorise un PNG en SVG.
    Essaie d'abord VTracer (subprocess isolé pour éviter SIGSEGV ARM64),
    puis Inkscape object-trace en fallback si VTracer échoue.
    Retourne le chemin d'un fichier SVG temporaire à supprimer par l'appelant.
    """
    flattened_path = _flatten_alpha(png_path)
    flattened_tmp = flattened_path if flattened_path != png_path else None

    tmp_svg = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
    tmp_svg.close()
    svg_path = Path(tmp_svg.name)

    try:
        result = subprocess.run(
            [sys.executable, str(_VTRACER_HELPER), str(flattened_path), str(svg_path), str(n_colors)],
            capture_output=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Vectorisation VTracer terminée : %s", png_path.name)
            return svg_path

        # VTracer a échoué (SIGSEGV sur ARM64, etc.) — tentative potrace
        stderr = result.stderr.decode(errors='replace').strip()
        logger.warning("VTracer échoué (code %d%s), tentative potrace.", result.returncode,
                       f' : {stderr}' if stderr else '')
        try:
            return _vectorize_potrace(flattened_path, svg_path, n_colors)
        except RuntimeError as potrace_err:
            logger.warning('potrace échoué (%s), fallback Inkscape.', potrace_err)
        return _vectorize_inkscape(flattened_path, svg_path, n_colors)

    except subprocess.TimeoutExpired:
        svg_path.unlink(missing_ok=True)
        raise RuntimeError('La vectorisation VTracer a dépassé le délai (120s).')
    finally:
        if flattened_tmp:
            flattened_tmp.unlink(missing_ok=True)


def _vectorize_inkscape(png_path: Path, svg_path: Path, n_colors: int = 6) -> Path:
    """Fallback : vectorisation via Inkscape object-trace (potrace multi-couleurs)."""
    inkscape = shutil.which('inkscape')
    if not inkscape:
        svg_path.unlink(missing_ok=True)
        raise RuntimeError(
            'La vectorisation a échoué : ni VTracer ni Inkscape ne sont disponibles.'
        )

    scans = min(max(n_colors, 2), 16)
    # smooth=true, stack=true, remove_background=true — paramètres potrace multi-scan
    actions = (
        f'file-open:{png_path};'
        f'select-all;'
        f'object-trace:{scans},true,true,true,2,0.3,0.2;'
        f'export-filename:{svg_path};'
        f'export-do'
    )
    result = subprocess.run(
        [inkscape, f'--actions={actions}'],
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0 or not svg_path.exists() or svg_path.stat().st_size == 0:
        svg_path.unlink(missing_ok=True)
        stderr = result.stderr.decode(errors='replace').strip()
        raise RuntimeError(f'La vectorisation Inkscape a échoué : {stderr}')

    # Nettoyer le SVG Inkscape pour Ink/Stitch :
    # - supprimer l'image raster embedded (inutile pour la broderie)
    # - convertir style="fill:..." en attribut fill= direct (meilleure compat Ink/Stitch)
    _normalize_inkscape_svg(svg_path)

    logger.info("Vectorisation Inkscape terminée : %s", png_path.name)
    return svg_path


def _normalize_inkscape_svg(svg_path: Path) -> None:
    """
    Post-traitement du SVG généré par Inkscape trace :
    1. Supprime les éléments <image> (raster embedded, inutile pour broderie)
    2. Convertit style="fill:COLOR;..." en attribut fill="COLOR" direct
       pour garantir que Ink/Stitch lit les couleurs correctement.
    Modifie le fichier en place.
    """
    import xml.etree.ElementTree as ET

    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
    ET.register_namespace('sodipodi', 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
    ET.register_namespace('cc', 'http://creativecommons.org/ns#')
    ET.register_namespace('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    ET.register_namespace('svg', 'http://www.w3.org/2000/svg')

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return  # Laisser le SVG tel quel si parse échoue

    SVG_NS_URI = 'http://www.w3.org/2000/svg'
    XLINK_NS_URI = 'http://www.w3.org/1999/xlink'

    # 1. Supprimer tous les éléments <image> à n'importe quel niveau
    for parent in root.iter():
        to_remove = [
            child for child in parent
            if child.tag in (
                f'{{{SVG_NS_URI}}}image',
                'image',
                f'{{{XLINK_NS_URI}}}image',
            )
        ]
        for child in to_remove:
            parent.remove(child)

    # 2. Convertir style="fill:COLOR" → attribut fill="COLOR" direct
    for element in root.iter():
        style_str = element.get('style', '')
        if not style_str:
            continue
        css = {}
        for part in style_str.split(';'):
            part = part.strip()
            if ':' in part:
                k, _, v = part.partition(':')
                css[k.strip().lower()] = v.strip()

        # Promouvoir fill et stroke comme attributs directs si non déjà définis
        changed = False
        remaining = {}
        for prop, val in css.items():
            if prop == 'fill' and not element.get('fill'):
                element.set('fill', val)
                changed = True
            elif prop == 'stroke' and not element.get('stroke'):
                element.set('stroke', val)
                changed = True
            else:
                remaining[prop] = val

        if changed:
            # Reconstruire style sans fill/stroke déplacés en attributs
            new_style = ';'.join(f'{k}:{v}' for k, v in remaining.items())
            if new_style:
                element.set('style', new_style)
            else:
                del element.attrib['style']

    tree.write(svg_path, encoding='unicode', xml_declaration=True)


def _color_to_pbm(mask: Image.Image, pbm_path: Path) -> None:
    """Écrit un masque Pillow mode '1' en fichier PBM P4 (attendu par potrace)."""
    mask.save(pbm_path)


def _extract_potrace_paths(svg_path: Path) -> list[str]:
    """Parse un SVG potrace et retourne la liste des attributs d= de tous les <path>."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError:
        return []
    return [el.get('d') for el in root.iter() if el.tag.endswith('path') and el.get('d')]


def _build_svg(paths_with_colors: list[tuple[list[str], str]], width: int, height: int) -> str:
    """
    Assemble un SVG final avec un <g fill="#color"> par couleur.
    Le transform Y-flip compense le système de coordonnées interne de potrace.
    """
    import xml.etree.ElementTree as ET
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    root = ET.Element(
        '{http://www.w3.org/2000/svg}svg',
        attrib={
            'width': str(width),
            'height': str(height),
            'viewBox': f'0 0 {width} {height}',
        },
    )
    transform = f'translate(0,{height}) scale(1,-1)'
    for path_list, hex_color in paths_with_colors:
        g = ET.SubElement(
            root,
            '{http://www.w3.org/2000/svg}g',
            attrib={'transform': transform, 'stroke': 'none'},
        )
        for d in path_list:
            # fill sur chaque <path> directement (pas seulement sur le <g>)
            # la validation SVG cherche fill sur l'élément lui-même, pas via héritage
            ET.SubElement(g, '{http://www.w3.org/2000/svg}path', attrib={'d': d, 'fill': hex_color})
    return ET.tostring(root, encoding='unicode', xml_declaration=True)


def _cluster_exact_colors(
    unique_colors: list[tuple[int, tuple[int, int, int]]],
    total_pixels: int,
    n_colors: int,
    threshold: int = 30,
) -> list[tuple[tuple[int, int, int], set[tuple[int, int, int]]]]:
    """
    Regroupe les couleurs exactes par proximité (distance euclidienne RGB).
    Retourne les N clusters dominants non-blancs sous la forme (couleur_centre, ensemble_couleurs_membres).
    """
    import math

    significant = sorted(
        [
            (count, color)
            for count, color in unique_colors
            if not (color[0] > 230 and color[1] > 230 and color[2] > 230)
            and count / total_pixels >= 0.001
        ],
        key=lambda x: -x[0],
    )

    clusters: list[list] = []  # [center, pixel_set, total_count]
    for count, color in significant:
        assigned = False
        for cluster in clusters:
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip(color, cluster[0])))
            if d < threshold:
                cluster[1].add(color)
                cluster[2] += count
                assigned = True
                break
        if not assigned:
            clusters.append([color, {color}, count])

    clusters.sort(key=lambda x: -x[2])
    return [(c[0], c[1]) for c in clusters[:n_colors]]


def _vectorize_potrace(png_path: Path, svg_path: Path, n_colors: int = 6) -> Path:
    """
    Vectorise PNG → SVG multi-couleurs via potrace.
    Utilise getcolors() exact pour les logos/aplats (fidélité couleurs garantie),
    MEDIANCUT en fallback pour les photos et images complexes.
    Lève RuntimeError si potrace absent ou si aucun chemin produit.
    """
    from collections import Counter

    potrace_bin = shutil.which('potrace')
    if not potrace_bin:
        raise RuntimeError('potrace introuvable. Installer avec : brew install potrace')

    with Image.open(png_path) as img:
        rgb = img.convert('RGB')
        width, height = rgb.size

    total_pixels = width * height
    unique_colors = rgb.getcolors(maxcolors=total_pixels)

    logger.info('[DEBUG potrace] n_colors=%d, image=%dx%d, unique_colors=%s',
                n_colors, width, height,
                f'{len(unique_colors)} couleurs exactes' if unique_colors is not None else 'trop nombreuses → MEDIANCUT')

    paths_with_colors: list[tuple[list[str], str]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        if unique_colors is not None:
            # Approche exacte : logos, aplats, images vectorielles
            # Couleurs 100% fidèles car extraites pixel par pixel
            clusters = _cluster_exact_colors(unique_colors, total_pixels, n_colors)
            logger.info('[DEBUG potrace] clusters détectés : %s',
                        [(f'#{r:02x}{g:02x}{b:02x}', len(cs)) for (r, g, b), cs in clusters])
            pixel_data = list(rgb.getdata())

            for idx, (center, color_set) in enumerate(clusters):
                r, g_val, b = center
                hex_color = f'#{r:02x}{g_val:02x}{b:02x}'
                black_count = sum(1 for p in pixel_data if p in color_set)
                logger.info('[DEBUG potrace] cluster %d : %s → %d pixels noirs', idx, hex_color, black_count)

                mask_data = [0 if p in color_set else 255 for p in pixel_data]
                mask = Image.new('L', (width, height))
                mask.putdata(mask_data)
                mask_1bit = mask.convert('1')

                pbm_path = tmpdir_path / f'mask_{idx}.pbm'
                potrace_svg = tmpdir_path / f'out_{idx}.svg'
                _color_to_pbm(mask_1bit, pbm_path)

                result = subprocess.run(
                    [potrace_bin, '--svg', '--unit', '1', '--output', str(potrace_svg), str(pbm_path)],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode != 0 or not potrace_svg.exists():
                    logger.warning('[DEBUG potrace] potrace échoué pour %s (code %d, stderr=%s)',
                                   hex_color, result.returncode, result.stderr.decode()[:200])
                    continue

                d_paths = _extract_potrace_paths(potrace_svg)
                logger.info('[DEBUG potrace] paths potrace pour %s : %d path(s)', hex_color, len(d_paths))
                if d_paths:
                    paths_with_colors.append((d_paths, hex_color))

        else:
            # Fallback MEDIANCUT : photos, dégradés, images avec nombreuses nuances
            quantized = rgb.quantize(colors=n_colors + 1, method=Image.Quantize.MEDIANCUT)
            palette = quantized.getpalette()
            counts = Counter(quantized.get_flattened_data())

            for color_idx, _ in counts.most_common():
                r = palette[color_idx * 3]
                g_val = palette[color_idx * 3 + 1]
                b = palette[color_idx * 3 + 2]

                if r > 230 and g_val > 230 and b > 230:
                    continue

                hex_color = f'#{r:02x}{g_val:02x}{b:02x}'
                lut = [0 if i == color_idx else 255 for i in range(256)]
                mask_1bit = quantized.point(lut, mode='L').convert('1')

                pbm_path = tmpdir_path / f'mask_{color_idx}.pbm'
                potrace_svg = tmpdir_path / f'out_{color_idx}.svg'
                _color_to_pbm(mask_1bit, pbm_path)

                result = subprocess.run(
                    [potrace_bin, '--svg', '--unit', '1', '--output', str(potrace_svg), str(pbm_path)],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode != 0 or not potrace_svg.exists():
                    logger.warning('potrace échoué pour couleur %s (code %d)', hex_color, result.returncode)
                    continue

                d_paths = _extract_potrace_paths(potrace_svg)
                if d_paths:
                    paths_with_colors.append((d_paths, hex_color))

    if not paths_with_colors:
        raise RuntimeError("potrace n'a produit aucun chemin valide.")

    svg_path.write_text(_build_svg(paths_with_colors, width, height), encoding='utf-8')
    logger.info('Vectorisation potrace : %d couleur(s) → %s', len(paths_with_colors), svg_path.name)
    return svg_path
