#!/usr/bin/env python3
"""
Génère les fixtures de test StitchFlow par catégorie broderie.

Usage :
    source .venv/bin/activate
    python tests/generate_fixtures.py

Dépendances : PIL (dans le venv), Inkscape (brew), stdlib uniquement.
Pas de dépendances additionnelles — reproductible à l'identique.
"""
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"


# ---------------------------------------------------------------------------
# Helpers SVG
# ---------------------------------------------------------------------------

def _svg_header(width: int, height: int) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
    )


def _svg_footer() -> str:
    return "</svg>\n"


def _write_svg(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ {path.relative_to(FIXTURES_DIR.parent)}")


def _write_png(path: Path, img: Image.Image) -> None:
    img.save(path, "PNG")
    print(f"  ✓ {path.relative_to(FIXTURES_DIR.parent)}")


# ---------------------------------------------------------------------------
# CATÉGORIE : logos/
# ---------------------------------------------------------------------------

def generate_logo_simple_svg() -> None:
    """Logo 3 couleurs : bouclier + initiale. Cas idéal pour broderie."""
    w, h = 200, 200
    svg = _svg_header(w, h)
    # Fond blanc
    svg += '  <rect width="200" height="200" fill="#FFFFFF"/>\n'
    # Bouclier bleu marine
    svg += (
        '  <path d="M100,20 L170,50 L170,130 Q170,170 100,185 Q30,170 30,130 L30,50 Z" '
        'fill="#1A3A6B" stroke="#0D1F3C" stroke-width="3"/>\n'
    )
    # Bande centrale dorée
    svg += (
        '  <path d="M100,20 L115,50 L115,185 Q107,187 100,185 Q93,187 85,185 L85,50 Z" '
        'fill="#C8A84B"/>\n'
    )
    # Initiale "S" rouge
    svg += (
        '  <text x="100" y="125" font-family="Helvetica,Arial,sans-serif" '
        'font-size="72" font-weight="bold" fill="#CC2200" '
        'text-anchor="middle" dominant-baseline="middle">S</text>\n'
    )
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "logos" / "logo-simple-3couleurs.svg", svg)


def generate_logo_complexe_svg() -> None:
    """Logo 7 couleurs avec texte — challenge multi-couleurs typique."""
    w, h = 300, 200
    svg = _svg_header(w, h)
    svg += '  <rect width="300" height="200" fill="#F5F5F5"/>\n'
    # Cercle extérieur bleu
    svg += '  <circle cx="100" cy="100" r="85" fill="#1565C0" stroke="#0D47A1" stroke-width="4"/>\n'
    # Anneau blanc
    svg += '  <circle cx="100" cy="100" r="70" fill="#FFFFFF"/>\n'
    # Demi-cercle vert en haut
    svg += (
        '  <path d="M30,100 A70,70 0 0,1 170,100 Z" fill="#2E7D32"/>\n'
    )
    # Demi-cercle rouge en bas
    svg += (
        '  <path d="M30,100 A70,70 0 0,0 170,100 Z" fill="#C62828"/>\n'
    )
    # Étoile centrale or
    star_pts = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = 28 if i % 2 == 0 else 14
        x = 100 + r * math.cos(angle)
        y = 100 + r * math.sin(angle)
        star_pts.append(f"{x:.1f},{y:.1f}")
    svg += f'  <polygon points="{" ".join(star_pts)}" fill="#F9A825"/>\n'
    # Texte "ATELIER" couleur bordeaux
    svg += (
        '  <text x="210" y="85" font-family="Helvetica,Arial,sans-serif" '
        'font-size="22" font-weight="bold" fill="#6A1B4D" '
        'text-anchor="middle">ATELIER</text>\n'
    )
    # Sous-titre "BRODERIE"
    svg += (
        '  <text x="210" y="115" font-family="Helvetica,Arial,sans-serif" '
        'font-size="16" fill="#1A237E" text-anchor="middle">BRODERIE</text>\n'
    )
    # Ligne décorative orange
    svg += (
        '  <line x1="155" y1="130" x2="265" y2="130" '
        'stroke="#E65100" stroke-width="3"/>\n'
    )
    # Sous-sous-titre
    svg += (
        '  <text x="210" y="150" font-family="Helvetica,Arial,sans-serif" '
        'font-size="12" fill="#37474F" text-anchor="middle">depuis 1987</text>\n'
    )
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "logos" / "logo-complexe-7couleurs-texte.svg", svg)


def generate_logo_fond_blanc_png() -> None:
    """Logo coloré sur fond blanc — test auto-détection fond blanc."""
    img = Image.new("RGB", (400, 300), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    # Fond blanc dominant (~70% des pixels → doit déclencher suggest removeBg)
    # Carré principal
    draw.rounded_rectangle([80, 60, 320, 240], radius=20,
                            fill="#1565C0", outline="#0D47A1", width=5)
    # Cercle intérieur blanc
    draw.ellipse([140, 100, 260, 200], fill="#FFFFFF", outline="#E65100", width=4)
    # Texte simulé avec rectangle
    draw.rectangle([155, 130, 245, 160], fill="#E65100")
    draw.rectangle([165, 170, 235, 185], fill="#2E7D32")
    # Triangle doré dans le cercle
    pts = [(200, 110), (230, 165), (170, 165)]
    draw.polygon(pts, fill="#F9A825", outline="#E65100", width=2)
    _write_png(FIXTURES_DIR / "logos" / "logo-fond-blanc.png", img)


def generate_logo_fond_transparent_png() -> None:
    """Logo avec fond transparent — test canal alpha."""
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Hexagone rouge sans fond (alpha = 0 partout sauf le dessin)
    hex_pts = []
    for i in range(6):
        angle = math.radians(i * 60 - 30)
        x = 150 + 110 * math.cos(angle)
        y = 150 + 110 * math.sin(angle)
        hex_pts.append((x, y))
    draw.polygon(hex_pts, fill=(26, 58, 107, 255), outline=(200, 170, 50, 255))
    # Contours intérieurs
    inner_pts = [(150 + 80 * math.cos(math.radians(i * 60 - 30)),
                  150 + 80 * math.sin(math.radians(i * 60 - 30))) for i in range(6)]
    draw.polygon(inner_pts, fill=(200, 170, 50, 255))
    # Centre
    draw.ellipse([110, 110, 190, 190], fill=(198, 40, 40, 255))
    draw.ellipse([130, 130, 170, 170], fill=(255, 255, 255, 255))
    _write_png(FIXTURES_DIR / "logos" / "logo-fond-transparent.png", img)


# ---------------------------------------------------------------------------
# CATÉGORIE : ecusson/
# ---------------------------------------------------------------------------

def generate_ecusson_club_png() -> None:
    """Écusson hexagonal 6 couleurs — cas d'usage typique broderie club."""
    size = 500
    img = Image.new("RGB", (size, size), "#F0EDE0")
    draw = ImageDraw.Draw(img)

    # Hexagone fond marine
    hex_pts = [(size // 2 + int(200 * math.cos(math.radians(i * 60 - 30))),
                size // 2 + int(220 * math.sin(math.radians(i * 60 - 30))))
               for i in range(6)]
    draw.polygon(hex_pts, fill="#1A2E5A", outline="#0D1C3A", width=6)

    # Bande horizontale or au tiers supérieur
    mid_y = size // 2
    draw.rectangle([size // 2 - 200, mid_y - 170, size // 2 + 200, mid_y - 100],
                   fill="#C8A84B")

    # 3 étoiles blanches dans la bande
    for sx in [size // 2 - 80, size // 2, size // 2 + 80]:
        star = [(sx + int(20 * math.cos(math.radians(j * 72 - 90))),
                 mid_y - 135 + int(20 * math.sin(math.radians(j * 72 - 90))))
                for j in range(5)]
        inner = [(sx + int(9 * math.cos(math.radians(j * 72 - 54))),
                  mid_y - 135 + int(9 * math.sin(math.radians(j * 72 - 54))))
                 for j in range(5)]
        full_star = []
        for outer, inner_pt in zip(star, inner):
            full_star.extend([outer, inner_pt])
        draw.polygon(full_star, fill="#FFFFFF")

    # Zone rouge centrale avec croix blanche
    draw.rectangle([size // 2 - 70, mid_y - 90, size // 2 + 70, mid_y + 50],
                   fill="#C62828")
    draw.rectangle([size // 2 - 12, mid_y - 85, size // 2 + 12, mid_y + 45],
                   fill="#FFFFFF")
    draw.rectangle([size // 2 - 65, mid_y - 30, size // 2 + 65, mid_y - 8],
                   fill="#FFFFFF")

    # Bandeau inférieur vert
    draw.rectangle([size // 2 - 195, mid_y + 60, size // 2 + 195, mid_y + 130],
                   fill="#2E5A1A")
    # Texte simulé avec blocs blancs
    for bx in range(size // 2 - 140, size // 2 + 140, 28):
        draw.rectangle([bx, mid_y + 75, bx + 20, mid_y + 115], fill="#FFFFFF")

    _write_png(FIXTURES_DIR / "ecusson" / "ecusson-club-6couleurs.png", img)


def generate_patch_sportif_png() -> None:
    """Patch sportif ovale — 8 couleurs avec texte + numéro + étoiles."""
    w, h = 500, 350
    img = Image.new("RGB", (w, h), "#F0EDE0")
    draw = ImageDraw.Draw(img)

    # Ovale fond bleu marine
    draw.ellipse([20, 20, w - 20, h - 20], fill="#0D2B6B", outline="#091A45", width=5)
    # Ovale intérieur blanc (bordure)
    draw.ellipse([40, 40, w - 40, h - 40], outline="#FFFFFF", width=4)

    # Bandeau rouge en haut
    draw.rectangle([60, 50, w - 60, 110], fill="#CC1800")
    # "TEAM" simulé : 4 blocs blancs dans le bandeau
    for i, bx in enumerate(range(90, 390, 75)):
        draw.rectangle([bx, 58, bx + 55, 102], fill="#FFFFFF")
        # Lettre simulée : diagonale
        draw.line([(bx + 5, 62), (bx + 27, 98)], fill="#CC1800", width=4)
        draw.line([(bx + 50, 62), (bx + 27, 98)], fill="#CC1800", width=4)

    # Numéro "7" central doré
    draw.ellipse([w // 2 - 55, h // 2 - 55, w // 2 + 55, h // 2 + 55],
                 fill="#C8A84B", outline="#A07820", width=3)
    draw.rectangle([w // 2 - 10, h // 2 - 40, w // 2 + 20, h // 2 + 40],
                   fill="#1A2E5A")
    draw.rectangle([w // 2 - 25, h // 2 - 40, w // 2 + 20, h // 2 - 15],
                   fill="#1A2E5A")

    # 5 étoiles blanches en bas
    for i, sx in enumerate(range(80, 430, 85)):
        pts = [(sx + int(18 * math.cos(math.radians(j * 72 - 90))),
                h - 75 + int(18 * math.sin(math.radians(j * 72 - 90))))
               for j in range(5)]
        inner = [(sx + int(8 * math.cos(math.radians(j * 72 - 54))),
                  h - 75 + int(8 * math.sin(math.radians(j * 72 - 54))))
                 for j in range(5)]
        full = []
        for o, n in zip(pts, inner):
            full.extend([o, n])
        draw.polygon(full, fill="#FFD700")

    # Bandeau vert en bas
    draw.rectangle([60, h - 110, w - 60, h - 55], fill="#2E7D32")

    _write_png(FIXTURES_DIR / "ecusson" / "patch-sportif-texte-graphique.png", img)


def generate_badge_contours_svg() -> None:
    """Badge circulaire — 5 couleurs, contours fins (challenge vectorisation)."""
    w, h = 300, 300
    svg = _svg_header(w, h)
    cx, cy, R = 150, 150, 130

    svg += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="#2C3E50" stroke="#1A252F" stroke-width="5"/>\n'
    svg += f'  <circle cx="{cx}" cy="{cy}" r="{R - 12}" fill="none" stroke="#F39C12" stroke-width="2"/>\n'
    svg += f'  <circle cx="{cx}" cy="{cy}" r="{R - 18}" fill="none" stroke="#ECF0F1" stroke-width="1"/>\n'

    # 8 rayons fins
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + (R - 25) * math.cos(angle)
        y1 = cy + (R - 25) * math.sin(angle)
        x2 = cx + 35 * math.cos(angle)
        y2 = cy + 35 * math.sin(angle)
        svg += f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#BDC3C7" stroke-width="1.5"/>\n'

    # Croix centrale rouge
    svg += f'  <rect x="{cx - 8}" y="{cy - 35}" width="16" height="70" fill="#E74C3C" rx="3"/>\n'
    svg += f'  <rect x="{cx - 35}" y="{cy - 8}" width="70" height="16" fill="#E74C3C" rx="3"/>\n'
    svg += f'  <circle cx="{cx}" cy="{cy}" r="15" fill="#ECF0F1"/>\n'
    svg += f'  <circle cx="{cx}" cy="{cy}" r="8" fill="#2C3E50"/>\n'

    # Texte circulaire simulé : petits traits sur le périmètre
    for i in range(24):
        angle = math.radians(i * 15)
        x1 = cx + (R - 8) * math.cos(angle)
        y1 = cy + (R - 8) * math.sin(angle)
        x2 = cx + (R - 4) * math.cos(angle)
        y2 = cy + (R - 4) * math.sin(angle)
        col = "#F39C12" if i % 3 == 0 else "#ECF0F1"
        svg += f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="1.5"/>\n'

    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "ecusson" / "badge-contours-fins.svg", svg)


# ---------------------------------------------------------------------------
# CATÉGORIE : texte/
# ---------------------------------------------------------------------------

def generate_monogramme_svg() -> None:
    """Monogramme 'AB' en style héraldique — cas typique broderie personnalisée."""
    w, h = 250, 250
    svg = _svg_header(w, h)
    svg += '  <rect width="250" height="250" fill="#FAFAFA"/>\n'
    # Fond ovale doré
    svg += '  <ellipse cx="125" cy="125" rx="110" ry="110" fill="#C8A84B" stroke="#A07820" stroke-width="4"/>\n'
    svg += '  <ellipse cx="125" cy="125" rx="96" ry="96" fill="#1A2E5A"/>\n'
    # Lettres A et B en blanc
    svg += (
        '  <text x="80" y="155" font-family="Georgia,Times New Roman,serif" '
        'font-size="90" font-weight="bold" font-style="italic" fill="#FFFFFF" '
        'text-anchor="middle" dominant-baseline="middle">A</text>\n'
    )
    svg += (
        '  <text x="170" y="155" font-family="Georgia,Times New Roman,serif" '
        'font-size="90" font-weight="bold" font-style="italic" fill="#C8A84B" '
        'text-anchor="middle" dominant-baseline="middle">B</text>\n'
    )
    # Ligne de séparation
    svg += '  <line x1="125" y1="60" x2="125" y2="190" stroke="#C8A84B" stroke-width="2" stroke-dasharray="4,3"/>\n'
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "texte" / "monogramme-initiales.svg", svg)


def generate_texte_multicolore_svg() -> None:
    """Texte 'BRODERIE' — chaque lettre dans une couleur différente, satin stitch."""
    w, h = 500, 150
    svg = _svg_header(w, h)
    svg += '  <rect width="500" height="150" fill="#FFFFFF"/>\n'
    colors = ["#E74C3C", "#E67E22", "#F1C40F", "#2ECC71", "#1ABC9C", "#3498DB", "#9B59B6", "#E91E63"]
    letters = list("BRODERIE")
    x_start = 22
    for i, (letter, color) in enumerate(zip(letters, colors)):
        x = x_start + i * 58
        # Ombre portée
        svg += (
            f'  <text x="{x + 3}" y="108" font-family="Helvetica,Arial,sans-serif" '
            f'font-size="85" font-weight="bold" fill="#33333344" '
            f'text-anchor="middle">{letter}</text>\n'
        )
        # Lettre principale
        svg += (
            f'  <text x="{x}" y="105" font-family="Helvetica,Arial,sans-serif" '
            f'font-size="85" font-weight="bold" fill="{color}" '
            f'stroke="#00000033" stroke-width="1" text-anchor="middle">{letter}</text>\n'
        )
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "texte" / "texte-multicolore-8couleurs.svg", svg)


def generate_texte_contours_svg() -> None:
    """Texte avec contours fins seuls (stroke-only) — test limites vectorisation."""
    w, h = 400, 200
    svg = _svg_header(w, h)
    svg += '  <rect width="400" height="200" fill="#F8F8F8"/>\n'
    # Titre avec stroke fin
    svg += (
        '  <text x="200" y="80" font-family="Helvetica,Arial,sans-serif" '
        'font-size="52" font-weight="bold" fill="none" '
        'stroke="#1A3A6B" stroke-width="2" text-anchor="middle">STITCH</text>\n'
    )
    # Sous-titre rempli + stroke
    svg += (
        '  <text x="200" y="140" font-family="Helvetica,Arial,sans-serif" '
        'font-size="36" fill="#CC2200" stroke="#880000" '
        'stroke-width="1" text-anchor="middle">FLOW</text>\n'
    )
    # Ligne décorative
    svg += '  <line x1="40" y1="155" x2="360" y2="155" stroke="#C8A84B" stroke-width="3"/>\n'
    svg += (
        '  <text x="200" y="182" font-family="Helvetica,Arial,sans-serif" '
        'font-size="14" fill="#666666" text-anchor="middle" letter-spacing="8">BRODERIE NUMÉRIQUE</text>\n'
    )
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "texte" / "texte-contours-fins.svg", svg)


# ---------------------------------------------------------------------------
# CATÉGORIE : geometrique/
# ---------------------------------------------------------------------------

def generate_motif_repetitif_svg() -> None:
    """Grille de losanges 4 couleurs — motif répétitif typique broderie ethnique."""
    w, h = 400, 400
    svg = _svg_header(w, h)
    svg += '  <rect width="400" height="400" fill="#F5F0E8"/>\n'
    colors = ["#1A3A6B", "#C62828", "#2E7D32", "#C8A84B"]
    cell = 80
    for row in range(5):
        for col in range(5):
            cx = col * cell + cell // 2
            cy = row * cell + cell // 2
            color = colors[(row + col) % 4]
            r = 32
            pts = f"{cx},{cy - r} {cx + r},{cy} {cx},{cy + r} {cx - r},{cy}"
            svg += f'  <polygon points="{pts}" fill="{color}" stroke="#FFFFFF" stroke-width="3"/>\n'
            # Petit losange intérieur contrasté
            r2 = 12
            pts2 = f"{cx},{cy - r2} {cx + r2},{cy} {cx},{cy + r2} {cx - r2},{cy}"
            inner_col = "#FFFFFF" if color != "#C8A84B" else "#1A3A6B"
            svg += f'  <polygon points="{pts2}" fill="{inner_col}"/>\n'
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "geometrique" / "motif-repetitif-losanges.svg", svg)


def generate_formes_concentriques_png() -> None:
    """Cercles concentriques 5 couleurs — test quantification couleurs."""
    size = 500
    img = Image.new("RGB", (size, size), "#FAFAFA")
    draw = ImageDraw.Draw(img)
    colors = ["#1A3A6B", "#C62828", "#C8A84B", "#2E7D32", "#6A1B9A"]
    radii = [230, 185, 140, 95, 50]
    cx, cy = size // 2, size // 2
    for r, color in zip(radii, colors):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # Motif central blanc
    draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill="#FFFFFF")
    _write_png(FIXTURES_DIR / "geometrique" / "cercles-concentriques-5couleurs.png", img)


def generate_abstrait_multizone_svg() -> None:
    """Formes géométriques qui se chevauchent — 6 couleurs, test fidélité."""
    w, h = 400, 300
    svg = _svg_header(w, h)
    svg += '  <rect width="400" height="300" fill="#ECEFF1"/>\n'
    # Rectangle bleu
    svg += '  <rect x="30" y="40" width="180" height="200" fill="#1565C0" rx="10"/>\n'
    # Cercle rouge se chevauchant
    svg += '  <circle cx="200" cy="150" r="100" fill="#C62828" opacity="1"/>\n'
    # Triangle vert en avant
    svg += '  <polygon points="320,50 380,250 200,250" fill="#2E7D32"/>\n'
    # Losange doré au centre
    svg += '  <polygon points="200,70 260,150 200,230 140,150" fill="#F9A825"/>\n'
    # Cercle violet petit
    svg += '  <circle cx="100" cy="150" r="45" fill="#6A1B9A"/>\n'
    # Étoile à 6 branches blanche
    for i in range(6):
        angle = math.radians(i * 60)
        x = 310 + 35 * math.cos(angle)
        y = 100 + 35 * math.sin(angle)
        svg += f'  <line x1="310" y1="100" x2="{x:.1f}" y2="{y:.1f}" stroke="#FFFFFF" stroke-width="8"/>\n'
    svg += '  <circle cx="310" cy="100" r="12" fill="#FFFFFF"/>\n'
    svg += _svg_footer()
    _write_svg(FIXTURES_DIR / "geometrique" / "abstrait-6couleurs.svg", svg)


# ---------------------------------------------------------------------------
# CATÉGORIE : pdf/
# ---------------------------------------------------------------------------

def _svg_to_pdf_inkscape(svg_path: Path, pdf_path: Path) -> bool:
    """Convertit SVG → PDF via Inkscape CLI. Retourne True si succès."""
    try:
        result = subprocess.run(
            ["inkscape", str(svg_path), "--export-type=pdf", f"--export-filename={pdf_path}"],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and pdf_path.exists():
            print(f"  ✓ {pdf_path.relative_to(FIXTURES_DIR.parent)}")
            return True
        else:
            print(f"  ✗ Inkscape erreur : {result.stderr.decode()[:200]}", file=sys.stderr)
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  ✗ Inkscape indisponible : {e}", file=sys.stderr)
        return False


def generate_pdf_logo_vectoriel() -> None:
    """PDF vectoriel d'un logo — pipeline pdftocairo → SVG direct."""
    # Crée d'abord le SVG source
    w, h = 300, 200
    svg = _svg_header(w, h)
    svg += '  <rect width="300" height="200" fill="#FFFFFF"/>\n'
    svg += '  <rect x="20" y="30" width="120" height="140" fill="#1565C0" rx="8"/>\n'
    svg += '  <circle cx="80" cy="100" r="45" fill="#FFFFFF"/>\n'
    svg += '  <circle cx="80" cy="100" r="30" fill="#C62828"/>\n'
    svg += (
        '  <text x="175" y="85" font-family="Helvetica,Arial,sans-serif" '
        'font-size="28" font-weight="bold" fill="#1A2E5A" text-anchor="middle">LOGO</text>\n'
    )
    svg += (
        '  <text x="175" y="120" font-family="Helvetica,Arial,sans-serif" '
        'font-size="18" fill="#666666" text-anchor="middle">Vectoriel</text>\n'
    )
    svg += '  <line x1="130" y1="135" x2="255" y2="135" stroke="#C8A84B" stroke-width="3"/>\n'
    svg += _svg_footer()

    tmp_svg = FIXTURES_DIR / "pdf" / "_tmp_logo.svg"
    tmp_svg.write_text(svg, encoding="utf-8")
    pdf_path = FIXTURES_DIR / "pdf" / "logo-vectoriel.pdf"
    _svg_to_pdf_inkscape(tmp_svg, pdf_path)
    tmp_svg.unlink(missing_ok=True)


def generate_pdf_texte_vectoriel() -> None:
    """PDF vectoriel avec texte — pipeline PDF vectoriel."""
    w, h = 300, 200
    svg = _svg_header(w, h)
    svg += '  <rect width="300" height="200" fill="#F5F0E8"/>\n'
    # Titre principal
    svg += (
        '  <text x="150" y="70" font-family="Georgia,serif" '
        'font-size="36" font-weight="bold" fill="#1A2E5A" text-anchor="middle">Nom</text>\n'
    )
    svg += (
        '  <text x="150" y="110" font-family="Georgia,serif" '
        'font-size="28" fill="#C62828" text-anchor="middle">Prénom</text>\n'
    )
    svg += '  <line x1="40" y1="125" x2="260" y2="125" stroke="#C8A84B" stroke-width="2"/>\n'
    svg += (
        '  <text x="150" y="155" font-family="Helvetica,Arial,sans-serif" '
        'font-size="16" fill="#555555" text-anchor="middle">brodé sur mesure</text>\n'
    )
    svg += '  <rect x="20" y="10" width="260" height="180" fill="none" stroke="#C8A84B" stroke-width="3" rx="5"/>\n'
    svg += _svg_footer()

    tmp_svg = FIXTURES_DIR / "pdf" / "_tmp_texte.svg"
    tmp_svg.write_text(svg, encoding="utf-8")
    pdf_path = FIXTURES_DIR / "pdf" / "texte-vectoriel.pdf"
    _svg_to_pdf_inkscape(tmp_svg, pdf_path)
    tmp_svg.unlink(missing_ok=True)


def generate_pdf_simule_scanne() -> None:
    """PDF raster simulant un scan — pipeline PDF scanné (fallback rasterisation)."""
    # PIL peut sauvegarder un PNG en PDF directement
    size = 400
    img = Image.new("RGB", (size, size), "#F2EEE0")
    draw = ImageDraw.Draw(img)

    # Bruit léger simulant scanner (lignes horizontales légères)
    for y in range(0, size, 8):
        draw.line([(0, y), (size, y)], fill="#E8E4D8", width=1)

    # Dessin "scanné" : logo simple avec apparence ancienne
    draw.ellipse([80, 80, 320, 320], outline="#333333", width=6)
    draw.ellipse([110, 110, 290, 290], fill="#CCCCCC", outline="#555555", width=3)
    draw.line([(200, 100), (200, 300)], fill="#333333", width=8)
    draw.line([(100, 200), (300, 200)], fill="#333333", width=8)
    draw.rectangle([155, 155, 245, 245], fill="#FFFFFF", outline="#333333", width=3)

    # Sauvegarder en PDF via PIL
    pdf_path = FIXTURES_DIR / "pdf" / "simule-scanne.pdf"
    img.save(str(pdf_path), "PDF", resolution=150)
    print(f"  ✓ {pdf_path.relative_to(FIXTURES_DIR.parent)}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> None:
    print("Création des dossiers fixtures...")
    for d in ["logos", "ecusson", "texte", "geometrique", "pdf"]:
        (FIXTURES_DIR / d).mkdir(parents=True, exist_ok=True)

    print("\n[logos/]")
    generate_logo_simple_svg()
    generate_logo_complexe_svg()
    generate_logo_fond_blanc_png()
    generate_logo_fond_transparent_png()

    print("\n[ecusson/]")
    generate_ecusson_club_png()
    generate_patch_sportif_png()
    generate_badge_contours_svg()

    print("\n[texte/]")
    generate_monogramme_svg()
    generate_texte_multicolore_svg()
    generate_texte_contours_svg()

    print("\n[geometrique/]")
    generate_motif_repetitif_svg()
    generate_formes_concentriques_png()
    generate_abstrait_multizone_svg()

    print("\n[pdf/]")
    generate_pdf_logo_vectoriel()
    generate_pdf_texte_vectoriel()
    generate_pdf_simule_scanne()

    total = sum(1 for _ in FIXTURES_DIR.rglob("*") if _.is_file())
    print(f"\n{total} fixtures générées dans tests/fixtures/")


if __name__ == "__main__":
    main()
