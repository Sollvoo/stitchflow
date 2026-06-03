"""
Utilitaires pour la manipulation de fichiers SVG.
"""
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Facteurs de conversion vers mm
_UNITS_TO_MM: dict[str, float] = {
    'mm': 1.0,
    'cm': 10.0,
    'in': 25.4,
    'pt': 25.4 / 72,
    'pc': 25.4 / 6,
    'px': 25.4 / 96,
}

# Namespaces SVG courants à enregistrer pour préserver les préfixes à l'écriture
_SVG_NAMESPACES = {
    '': 'http://www.w3.org/2000/svg',
    'xlink': 'http://www.w3.org/1999/xlink',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cc': 'http://creativecommons.org/ns#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
}


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
        return float(v) * _UNITS_TO_MM['px']  # sans unité = px par défaut
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

        w_attr = root.get('width', '')
        h_attr = root.get('height', '')

        if '%' not in w_attr and '%' not in h_attr and w_attr and h_attr:
            w_mm = _parse_length_mm(w_attr)
            h_mm = _parse_length_mm(h_attr)
            if w_mm and h_mm:
                return round(w_mm, 1), round(h_mm, 1)

        # Fallback : viewBox en pixels
        vb = root.get('viewBox')
        if vb:
            parts = vb.split()
            if len(parts) == 4:
                vb_w = float(parts[2])
                vb_h = float(parts[3])
                return (
                    round(vb_w * _UNITS_TO_MM['px'], 1),
                    round(vb_h * _UNITS_TO_MM['px'], 1),
                )
    except Exception:
        pass
    return None, None


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
    vb = root.get('viewBox')
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
            w_attr = root.get('width', '100')
            h_attr = root.get('height', '100')
            w_px = (_parse_length_mm(w_attr) or 100) / _UNITS_TO_MM['px']
            h_px = (_parse_length_mm(h_attr) or 100) / _UNITS_TO_MM['px']
            root.set('viewBox', f'0 0 {w_px:.4f} {h_px:.4f}')
        else:
            aspect = 1.0

    target_height_mm = round(target_width_mm * aspect, 4)
    root.set('width', f'{target_width_mm}mm')
    root.set('height', f'{target_height_mm}mm')

    tmp = tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w', encoding='utf-8')
    tmp.close()
    tree.write(tmp.name, encoding='unicode', xml_declaration=True)
    return Path(tmp.name)
