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


def convert_pdf_to_png(path: Path, dpi: int = 300) -> Path:
    """
    Rasterise la première page d'un PDF en PNG 300dpi via pdf2image + poppler.
    Retourne le chemin d'un fichier PNG temporaire (à supprimer par l'appelant).
    Lève PNGValidationError si pdf2image est absent ou si le PDF est illisible.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise PNGValidationError(
            'Le service de conversion PDF est indisponible. '
            'Installez poppler (brew install poppler) et pdf2image (pip install pdf2image).'
        ) from exc

    try:
        pages = convert_from_path(str(path), dpi=dpi, first_page=1, last_page=1)
    except Exception as exc:
        raise PNGValidationError(f'Impossible de lire le PDF : {exc}') from exc

    if not pages:
        raise PNGValidationError('Le PDF ne contient aucune page lisible.')

    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    pages[0].save(tmp.name, 'PNG')
    tmp.close()
    return Path(tmp.name)


def convert_to_png(path: Path) -> Path:
    """
    Convertit un fichier JPEG ou WebP en PNG temporaire via Pillow.
    Retourne le chemin d'un fichier PNG temporaire (à supprimer par l'appelant).
    """
    with Image.open(path) as img:
        rgb = img.convert('RGB')
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        rgb.save(tmp.name, 'PNG')
        tmp.close()
    return Path(tmp.name)


def remove_background(path: Path) -> Path:
    """
    Supprime le fond de l'image via rembg (IA) si disponible,
    sinon fallback sur un seuillage Pillow simple pour les fonds blancs.
    Retourne le chemin d'un fichier temporaire PNG RGBA (à supprimer par l'appelant).
    """
    try:
        # onnxruntime est le backend requis par rembg — on l'importe en premier pour
        # détecter son absence via ImportError propre, évitant le sys.exit(1) de rembg
        # qui tuerait le worker Celery entier sans être attrapable par except Exception.
        import onnxruntime  # noqa: F401
        import rembg
        with path.open('rb') as f:
            input_data = f.read()
        output_data = rembg.remove(input_data)
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.write(output_data)
        tmp.close()
        logger.info("Suppression fond rembg : %s", path.name)
        return Path(tmp.name)
    except (ImportError, SystemExit, Exception) as exc:
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
    Adaptatif : logos (peu de couleurs) → traitement léger ; photos → traitement complet.
    Ne quantifie PAS les couleurs ici — c'est le rôle de _vectorize_potrace.
    Retourne le chemin d'un fichier temporaire PNG à supprimer par l'appelant.
    """
    with Image.open(path) as img:
        # Aplatir le canal alpha sur fond blanc avant convert('RGB') :
        # sans ça, les pixels transparents deviennent noirs (bug fond noir SVG).
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            rgba = img.convert('RGBA')
            bg.paste(rgba.convert('RGB'), mask=rgba.split()[3])
            working = bg
        else:
            working = img.convert('RGB')

        # Détecter logo (≤200 couleurs exactes) vs photo
        is_logo = working.getcolors(maxcolors=200) is not None
        if is_logo:
            # Logos : bords déjà nets, contraste léger uniquement
            working = ImageEnhance.Contrast(working).enhance(1.1)
        else:
            # Photos / images complexes : contraste + netteté
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


_ENTROPY_LOGO_MAX = 60.0   # variance locale ≤ 60 → logo (aplats francs)
_ENTROPY_PHOTO_MIN = 200.0  # variance locale ≥ 200 → photo (dégradés, bruit)


def _compute_local_variance(img: Image.Image, block_size: int = 8) -> float:
    """Variance moyenne des blocs block_size×block_size en niveaux de gris. Proxy d'entropie locale."""
    gray = img.convert('L')
    w, h = gray.size
    pixels = list(gray.getdata())
    variances = []
    for y in range(0, h - block_size + 1, block_size):
        for x in range(0, w - block_size + 1, block_size):
            block = [pixels[(y + by) * w + (x + bx)]
                     for by in range(block_size) for bx in range(block_size)]
            mean = sum(block) / len(block)
            variances.append(sum((p - mean) ** 2 for p in block) / len(block))
    return sum(variances) / len(variances) if variances else 0.0


def _detect_image_type(path: Path, n_colors: int) -> str:
    """
    Classe l'image en 'logo' (aplats solides) ou 'photo' (dégradés, antialiasing).
    Utilise la variance locale (blocs 8×8) comme critère principal,
    getcolors comme fallback sur la zone ambiguë [60, 200].
    """
    with Image.open(path) as img:
        variance = _compute_local_variance(img)
        if variance <= _ENTROPY_LOGO_MAX:
            logger.debug('[routing] entropie=%.1f → logo (seuil≤%.0f)', variance, _ENTROPY_LOGO_MAX)
            return 'logo'
        if variance >= _ENTROPY_PHOTO_MIN:
            logger.debug('[routing] entropie=%.1f → photo (seuil≥%.0f)', variance, _ENTROPY_PHOTO_MIN)
            return 'photo'
        max_colors = min(200, n_colors * 20)
        result = 'logo' if img.convert('RGB').getcolors(maxcolors=max_colors) is not None else 'photo'
        logger.debug('[routing] entropie=%.1f ambiguë → getcolors=%s', variance, result)
        return result


def _find_vtracer_binary() -> str | None:
    """Retourne le chemin du binaire vtracer CLI (vendor/ prioritaire, puis PATH)."""
    if _VTRACER_VENDOR.exists():
        return str(_VTRACER_VENDOR)
    return shutil.which('vtracer')


def _consolidate_svg_colors(svg_path: Path, n_colors: int) -> None:
    """
    Fusionne les couleurs similaires du SVG VTracer en max n_colors clusters.
    VTracer crée de nombreuses nuances dues à l'anti-aliasing ; pour la broderie
    on veut des aplats francs avec peu de couleurs distinctes.
    """
    import math
    import xml.etree.ElementTree as ET

    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return

    root = tree.getroot()
    fill_counts: dict[str, int] = {}
    for el in root.iter():
        fill = el.get('fill', '')
        if fill.startswith('#') and len(fill) == 7:
            fill_counts[fill] = fill_counts.get(fill, 0) + 1

    if not fill_counts:
        return

    def hex_to_rgb(h: str) -> tuple[int, int, int]:
        return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))

    def rgb_to_hex(r: int, g: int, b: int) -> str:
        return f'#{r:02x}{g:02x}{b:02x}'

    def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
        def linearize(c: float) -> float:
            c /= 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        rl, gl, bl = linearize(r), linearize(g), linearize(b)
        X = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047
        Y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
        Z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883
        def f(t: float) -> float:
            return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
        L = 116 * f(Y) - 16
        a = 500 * (f(X) - f(Y))
        b_lab = 200 * (f(Y) - f(Z))
        return L, a, b_lab

    def lab_dist(c1: tuple[float, float, float], c2: tuple[float, float, float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(c1, c2)))

    # Pré-calculer Lab pour chaque couleur unique
    color_lab: dict[str, tuple[float, float, float]] = {
        h: rgb_to_lab(*hex_to_rgb(h)) for h in fill_counts
    }

    # Clustering par distance CIE Lab (seuil 22 ≈ couleurs proches perceptuellement)
    _LAB_CLUSTER_THRESH = 22.0
    colors_by_count = sorted(fill_counts.items(), key=lambda x: -x[1])
    clusters: list[tuple[tuple[int, int, int], tuple[float, float, float], list[str]]] = []

    for hex_color, _ in colors_by_count:
        lab = color_lab[hex_color]
        assigned = False
        for center_rgb, center_lab, members in clusters:
            if lab_dist(lab, center_lab) < _LAB_CLUSTER_THRESH:
                members.append(hex_color)
                assigned = True
                break
        if not assigned:
            clusters.append((hex_to_rgb(hex_color), lab, [hex_color]))

    clusters.sort(key=lambda c: -sum(fill_counts.get(h, 0) for h in c[2]))
    kept = clusters[:n_colors]

    replacement: dict[str, str] = {}
    for center_rgb, _center_lab, members in kept:
        center_hex = rgb_to_hex(*center_rgb)
        for old_hex in members:
            replacement[old_hex] = center_hex

    for hex_color in fill_counts:
        if hex_color not in replacement:
            hex_lab = color_lab[hex_color]
            best = min(kept, key=lambda c: lab_dist(hex_lab, c[1]))
            replacement[hex_color] = rgb_to_hex(*best[0])

    changed = False
    for el in root.iter():
        fill = el.get('fill', '')
        if fill in replacement and replacement[fill] != fill:
            el.set('fill', replacement[fill])
            changed = True

    if changed:
        tree.write(svg_path, encoding='unicode', xml_declaration=True)
        unique_after = len({v for v in replacement.values()})
        logger.info('[vtracer] %d couleurs → %d clusters (max %d)', len(fill_counts), unique_after, n_colors)


def _vectorize_vtracer_cli(
    png_path: Path, svg_path: Path, n_colors: int, vtracer_bin: str,
    fine_details: bool = False,
) -> bool:
    """
    Vectorise PNG → SVG via le binaire CLI VTracer (ARM64-safe, sans SIGSEGV Python bindings).
    Retourne True si réussi, False sinon (l'appelant basculera sur potrace).
    """
    gradient_step = max(8, 256 // max(n_colors, 1))
    if fine_details:
        # Texte fin / détails nets : speckle minimal, précision maximale, coins francs
        filter_speckle = 1
        color_precision = 8
        path_precision = 6
    else:
        filter_speckle = 2 if n_colors > 8 else 4
        color_precision = 8 if n_colors > 8 else 6
        path_precision = 4 if n_colors > 8 else 3
    result = subprocess.run(
        [
            vtracer_bin,
            '--input', str(png_path),
            '--output', str(svg_path),
            '--colormode', 'color',
            '--hierarchical', 'stacked',
            '--mode', 'spline',
            '--filter_speckle', str(filter_speckle),
            '--color_precision', str(color_precision),
            '--gradient_step', str(gradient_step),
            '--corner_threshold', '60',
            '--segment_length', '4.0',
            '--splice_threshold', '45',
            '--path_precision', str(path_precision),
        ],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0 or not svg_path.exists() or svg_path.stat().st_size == 0:
        logger.warning('[vtracer CLI] échoué (code %d): %s',
                       result.returncode, result.stderr.decode(errors='replace')[:200])
        return False

    _consolidate_svg_colors(svg_path, n_colors)
    _simplify_svg_nodes(svg_path)
    logger.info('[vtracer CLI] vectorisation terminée : %s', png_path.name)
    return True


def _quantize_to_n_colors(path: Path, n_colors: int) -> Path:
    """
    Réduit l'image à exactement n_colors avant vectorisation.
    Élimine l'antialiasing à la source : un rouge #FF0000 ne génère plus 30 nuances de rose.
    dither=NONE est critique — Floyd-Steinberg créerait encore plus de pixels de transition.
    Retourne le path original si l'image a déjà ≤ n_colors couleurs distinctes.
    """
    with Image.open(path) as img:
        rgb = img.convert('RGB')
        if rgb.getcolors(maxcolors=n_colors) is not None:
            return path  # déjà ≤ n_colors couleurs, pas de quantification nécessaire
        quantized = rgb.quantize(n_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        rgb_back = quantized.convert('RGB')
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        rgb_back.save(tmp.name, 'PNG')
        tmp.close()
    logger.info('[quantize] %s → %d couleurs max (sans dithering)', path.name, n_colors)
    return Path(tmp.name)


def _detect_fine_details(img: Image.Image) -> bool:
    """Retourne True si l'image contient du texte fin ou des détails à bords nets."""
    gray = img.convert('L')
    edges = gray.filter(ImageFilter.FIND_EDGES)
    pixels = list(edges.getdata())
    edge_ratio = sum(1 for p in pixels if p > 30) / max(1, len(pixels))
    return edge_ratio > 0.15


def vectorize_to_svg(png_path: Path, n_colors: int = 6) -> Path:
    """
    Vectorise un PNG en SVG via un routeur logo/photo.
    Logos (≤ n_colors*20 couleurs distinctes) → potrace (couleurs exactes garanties).
    Photos/complexes → VTracer CLI → VTracer Python → potrace → Inkscape.
    Retourne le chemin d'un fichier SVG temporaire à supprimer par l'appelant.
    """
    flattened_path = _flatten_alpha(png_path)
    flattened_tmp = flattened_path if flattened_path != png_path else None
    quantized_tmp: Path | None = None

    tmp_svg = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
    tmp_svg.close()
    svg_path = Path(tmp_svg.name)

    try:
        with Image.open(flattened_path) as _img_fd:
            _img_for_detection = _img_fd.copy()
        fine_details = _detect_fine_details(_img_for_detection)
        if fine_details:
            logger.info('[routing] détails fins détectés dans %s — paramètres précision max', png_path.name)

        image_type = _detect_image_type(flattened_path, n_colors)
        logger.info('[routing] %s → %s (n_colors=%d)', png_path.name, image_type, n_colors)

        if image_type == 'logo':
            # Logos : potrace en priorité, couleurs extraites pixel par pixel sans quantification.
            try:
                return _vectorize_potrace(flattened_path, svg_path, n_colors, fine_details=fine_details)
            except RuntimeError as potrace_err:
                logger.warning('[routing] potrace échoué pour logo (%s), fallback VTracer.', potrace_err)
            # Potrace absent ou échoué → cascade VTracer ci-dessous

        # Photos et fallback logos : quantize → VTracer CLI → VTracer Python → potrace → Inkscape
        quantized_path = _quantize_to_n_colors(flattened_path, n_colors)
        quantized_tmp = quantized_path if quantized_path != flattened_path else None

        vtracer_bin = _find_vtracer_binary()
        if vtracer_bin and _vectorize_vtracer_cli(quantized_path, svg_path, n_colors, vtracer_bin, fine_details=fine_details):
            return svg_path

        _preexec = None
        if sys.platform != 'win32':
            import resource as _resource
            def _preexec():
                _resource.setrlimit(_resource.RLIMIT_CORE, (0, 0))

        result = subprocess.run(
            [sys.executable, str(_VTRACER_HELPER), str(quantized_path), str(svg_path), str(n_colors)],
            capture_output=True,
            timeout=120,
            preexec_fn=_preexec,
        )
        if result.returncode == 0:
            logger.info("Vectorisation VTracer Python terminée : %s", png_path.name)
            return svg_path

        stderr = result.stderr.decode(errors='replace').strip()
        logger.warning("VTracer Python échoué (code %d%s), tentative potrace.", result.returncode,
                       f' : {stderr}' if stderr else '')

        try:
            return _vectorize_potrace(quantized_path, svg_path, n_colors, fine_details=fine_details)
        except RuntimeError as potrace_err:
            logger.warning('potrace échoué (%s), fallback Inkscape.', potrace_err)

        return _vectorize_inkscape(quantized_path, svg_path, n_colors)

    except subprocess.TimeoutExpired:
        svg_path.unlink(missing_ok=True)
        raise RuntimeError('La vectorisation VTracer a dépassé le délai (120s).')
    finally:
        if flattened_tmp:
            flattened_tmp.unlink(missing_ok=True)
        if quantized_tmp:
            quantized_tmp.unlink(missing_ok=True)


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


_POTRACE_MIN_DIM = 600  # upscale si la plus petite dimension est sous ce seuil
_VTRACER_VENDOR = Path(__file__).parents[3] / 'vendor' / 'vtracer'


def _smooth_mask_to_1bit(mask: 'Image.Image') -> 'Image.Image':
    """Applique un léger flou gaussien avant la conversion 1-bit pour lisser les bords pixels."""
    blurred = mask.filter(ImageFilter.GaussianBlur(radius=0.5))
    return blurred.point(lambda x: 0 if x < 128 else 255).convert('1')


def _vectorize_potrace(png_path: Path, svg_path: Path, n_colors: int = 6, fine_details: bool = False) -> Path:
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

    # Upscale si image trop petite (3× max) → plus de données pour potrace = meilleures courbes
    if min(width, height) < _POTRACE_MIN_DIM:
        scale = min(3.0, _POTRACE_MIN_DIM / min(width, height))
        new_w = int(width * scale)
        new_h = int(height * scale)
        rgb = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
        width, height = new_w, new_h
        logger.info('[DEBUG potrace] upscale %.1f× → %dx%d', scale, width, height)

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
                mask_1bit = _smooth_mask_to_1bit(mask)

                pbm_path = tmpdir_path / f'mask_{idx}.pbm'
                potrace_svg = tmpdir_path / f'out_{idx}.svg'
                _color_to_pbm(mask_1bit, pbm_path)

                if fine_details:
                    turdsize, opttolerance, alphamax = '1', '0.05', '0.0'
                else:
                    turdsize = '1' if n_colors > 8 else '2'
                    opttolerance = '0.1' if n_colors > 8 else '0.2'
                    alphamax = '0.1'
                result = subprocess.run(
                    [potrace_bin, '--svg',
                     '--unit', '1',
                     '--alphamax', alphamax,
                     '--turdsize', turdsize,
                     '--opttolerance', opttolerance,
                     '--output', str(potrace_svg), str(pbm_path)],
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
            quantized = rgb.quantize(colors=n_colors + 1, method=Image.Quantize.FASTOCTREE)
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
                mask_gray = quantized.point(lut, mode='L')
                mask_1bit = _smooth_mask_to_1bit(mask_gray)

                pbm_path = tmpdir_path / f'mask_{color_idx}.pbm'
                potrace_svg = tmpdir_path / f'out_{color_idx}.svg'
                _color_to_pbm(mask_1bit, pbm_path)

                if fine_details:
                    turdsize, opttolerance, alphamax = '1', '0.05', '0.0'
                else:
                    turdsize = '1' if n_colors > 8 else '2'
                    opttolerance = '0.1' if n_colors > 8 else '0.2'
                    alphamax = '0.1'
                result = subprocess.run(
                    [potrace_bin, '--svg',
                     '--unit', '1',
                     '--alphamax', alphamax,
                     '--turdsize', turdsize,
                     '--opttolerance', opttolerance,
                     '--output', str(potrace_svg), str(pbm_path)],
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
    svg_size_kb = svg_path.stat().st_size // 1024
    logger.info('Vectorisation potrace : %d couleur(s) → %s (%d KB)', len(paths_with_colors), svg_path.name, svg_size_kb)

    # Simplifier systématiquement les nœuds avant inkstitch —
    # la broderie n'a pas besoin de précision sub-pixel.
    _simplify_svg_nodes(svg_path)

    return svg_path


def _simplify_svg_nodes(svg_path: Path) -> None:
    """
    Réduit le nombre de nœuds du SVG via Inkscape path-simplify.
    Silencieux si Inkscape absent. Modifie le fichier en place.
    La broderie n'a pas besoin de précision sub-pixel : simplifier améliore les perfs inkstitch.
    """
    inkscape = shutil.which('inkscape')
    if not inkscape:
        return

    before_kb = svg_path.stat().st_size // 1024
    try:
        result = subprocess.run(
            [inkscape,
             f'--actions=select-all;path-simplify;export-do',
             f'--export-filename={svg_path}',
             str(svg_path)],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and svg_path.exists() and svg_path.stat().st_size > 0:
            after_kb = svg_path.stat().st_size // 1024
            logger.info('[DEBUG potrace] SVG simplifié par Inkscape : %d KB → %d KB', before_kb, after_kb)
        else:
            logger.warning('[DEBUG potrace] Inkscape simplify échoué (code %d)', result.returncode)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning('[DEBUG potrace] Inkscape simplify exception : %s', exc)
