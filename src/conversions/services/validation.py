"""
Validation supplémentaire des fichiers SVG.
Utilisé en complément de la validation du formulaire.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from django.core.exceptions import ValidationError

SVG_NS = 'http://www.w3.org/2000/svg'
BRODABLE_TAGS = {'path', 'rect', 'circle', 'ellipse', 'polygon', 'line', 'polyline'}


def _parse_css_style(style: str) -> dict[str, str]:
    """Parse un attribut style CSS inline ('fill:#xxx;stroke:none') en dict."""
    result: dict[str, str] = {}
    for part in style.split(';'):
        part = part.strip()
        if ':' in part:
            key, _, val = part.partition(':')
            result[key.strip().lower()] = val.strip().lower()
    return result


class SVGValidationError(Exception):
    """Erreur levée quand le contenu SVG est invalide pour la broderie."""
    pass


def validate_svg_structure(svg_path: Path) -> None:
    """
    Vérifie que le fichier est un XML valide avec un élément racine <svg>.
    Lève ValidationError si le fichier n'est pas un SVG valide.
    """
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValidationError(f'SVG invalide (erreur XML) : {e}')

    # L'élément racine doit être <svg> (avec ou sans namespace)
    tag = root.tag.lower()
    if 'svg' not in tag:
        raise ValidationError(
            f'Le fichier ne contient pas un élément SVG valide (racine : {root.tag}).'
        )


def validate_svg_content(svg_path: Path) -> None:
    """
    Vérifie que le SVG contient des éléments brodables.
    Lève SVGValidationError avec un message lisible si le SVG est vide ou sans chemins brodables.
    """
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return  # La validation structurelle aura déjà échoué avant

    # Vérifier les dimensions nulles
    for attr in ('width', 'height'):
        raw = root.get(attr)
        if raw is None:
            continue
        numeric = raw.strip().lower().rstrip('mxcptins% ')
        if not numeric:
            continue
        try:
            if float(numeric) == 0:
                raise SVGValidationError(
                    f'Le SVG a une dimension nulle ({attr}="{raw}"). '
                    'Vérifiez que votre fichier a une taille valide.'
                )
        except ValueError:
            pass

    # Chercher des éléments brodables (avec ou sans namespace SVG)
    for element in tree.iter():
        local_tag = element.tag
        if local_tag.startswith('{'):
            # Extraire le nom local depuis le namespace {ns}tag
            local_tag = local_tag.split('}', 1)[1]

        if local_tag.lower() not in BRODABLE_TAGS:
            continue

        # L'élément est un candidat brodable — vérifier fill/stroke
        # Priorité : attribut direct, sinon parsing du style CSS inline (ex: style="fill:#xxx")
        fill = element.get('fill', '').strip().lower()
        stroke = element.get('stroke', '').strip().lower()

        style_str = element.get('style', '')
        if style_str and (not fill or not stroke):
            css = _parse_css_style(style_str)
            if not fill:
                fill = css.get('fill', '')
            if not stroke:
                stroke = css.get('stroke', '')

        has_fill = fill not in ('', 'none')
        has_stroke = stroke not in ('', 'none')

        if has_fill or has_stroke:
            return  # Au moins un élément brodable trouvé

    raise SVGValidationError(
        'Le SVG ne contient pas d\'éléments brodables. '
        'Assurez-vous que vos formes ont un contour (stroke) ou un remplissage (fill) '
        'et ne sont pas définis uniquement via CSS externe.'
    )
