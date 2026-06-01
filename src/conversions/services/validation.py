"""
Validation supplémentaire des fichiers SVG.
Utilisé en complément de la validation du formulaire.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from django.core.exceptions import ValidationError


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
