"""
Génération de prévisualisations et extraction de métadonnées depuis les fichiers PES.
Utilise pyembroidery pour lire le PES et générer un PNG via Pillow.
"""

import json
import logging
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pyembroidery
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# Vitesse conservative de broderie pour estimation du temps (points/minute)
# Brother PR1050X : max 1000 spm, estimation prudente à 600 spm pour designs normaux
_STITCHES_PER_MINUTE = 600


# ---------------------------------------------------------------------------
# Helpers couleurs (stdlib pure — pas de numpy ni scikit)
# ---------------------------------------------------------------------------


def _is_near_white_thread(color_int: int) -> bool:
    """Retourne True si la couleur entière (0xRRGGBB) est quasi-blanche (R,G,B > 240)."""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return r > 240 and g > 240 and b > 240


def _filter_pes_v1_color_breaks(threadlist: list) -> tuple[list, bool]:
    """
    Filtre les entrées blanc-marqueur PES v1 du threadlist.

    PES v1 insère un fil blanc neutre (COLOR_BREAK) entre chaque vraie couleur.
    Détection par analyse glissante : un blanc encadré par deux non-blancs = COLOR_BREAK.
    Un blanc en début, fin, ou adjacent à un autre blanc = vrai fil blanc conservé.

    Retourne (threadlist_filtré, filtrage_appliqué).
    """
    if len(threadlist) < 3:
        return threadlist, False

    filtered = []
    removed = False
    for i, t in enumerate(threadlist):
        if _is_near_white_thread(t.color):
            prev_real = i > 0 and not _is_near_white_thread(threadlist[i - 1].color)
            next_real = i < len(threadlist) - 1 and not _is_near_white_thread(
                threadlist[i + 1].color
            )
            if prev_real and next_real:
                removed = True
                continue  # COLOR_BREAK PES v1 → supprimer
        filtered.append(t)

    return filtered, removed


def _rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Conversion RGB 0-255 → CIE Lab (D65, 2°)."""

    def _lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = _lin(r), _lin(g), _lin(b)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041

    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (903.3 * t + 16.0) / 116.0

    fx = _f(x / 0.95047)
    fy = _f(y / 1.00000)
    fz = _f(z / 1.08883)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def _lab_distance(
    c1: tuple[float, float, float], c2: tuple[float, float, float]
) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _is_near_white(r: int, g: int, b: int, threshold: int = 235) -> bool:
    return r >= threshold and g >= threshold and b >= threshold


# ---------------------------------------------------------------------------
# Extraction couleurs SVG
# ---------------------------------------------------------------------------


def _extract_svg_colors(svg_path: Path) -> list[tuple[int, int, int]]:
    """
    Extrait les couleurs fill distinctes non-blanches du SVG.
    Retourne une liste de tuples (R, G, B).
    """
    try:
        root = ET.parse(svg_path).getroot()
    except (ET.ParseError, OSError):
        return []

    seen: set[str] = set()
    colors: list[tuple[int, int, int]] = []
    for el in root.iter():
        fill = el.get("fill", "")
        if not fill.startswith("#") or len(fill) != 7 or fill in seen:
            continue
        seen.add(fill)
        try:
            r, g, b = int(fill[1:3], 16), int(fill[3:5], 16), int(fill[5:7], 16)
        except ValueError:
            continue
        if not _is_near_white(r, g, b):
            colors.append((r, g, b))
    return colors


# ---------------------------------------------------------------------------
# Critères de score additionnels
# ---------------------------------------------------------------------------


def _score_color_fidelity(
    pattern: pyembroidery.EmbPattern,
    svg_path: Path,
) -> tuple[int, str]:
    """
    Mesure la distance perceptuelle (Lab) entre les couleurs du SVG source
    et les fils du PES. Une distance Lab moyenne faible = bonne fidélité.
    Retourne (score 0-100, message).
    """
    svg_colors = _extract_svg_colors(svg_path)
    threadlist = pattern.threadlist or []

    pes_colors = []
    for t in threadlist:
        r, g, b = (t.color >> 16) & 0xFF, (t.color >> 8) & 0xFF, t.color & 0xFF
        if not _is_near_white(r, g, b):
            pes_colors.append((r, g, b))

    if not svg_colors:
        return 50, "Couleurs SVG non lisibles"
    if not pes_colors:
        return 0, "Aucun fil de couleur dans le PES"

    svg_labs = [_rgb_to_lab(*c) for c in svg_colors]
    pes_labs = [_rgb_to_lab(*c) for c in pes_colors]

    # Distance Lab moyenne : pour chaque couleur SVG → fil PES le plus proche
    distances = [min(_lab_distance(sl, pl) for pl in pes_labs) for sl in svg_labs]
    mean_dist = sum(distances) / len(distances)

    # Pénalité si le PES a bien moins de fils que le SVG n'a de couleurs
    # (ex: SVG 10 couleurs → PES 2 fils = vectorisation partielle)
    ratio = min(1.0, len(pes_colors) / len(svg_colors))
    # Coefficient 1.2 : Δ Lab 83 = score 0, Δ Lab 30 = 64, plus réaliste que 2×
    distance_score = max(0, 100 - int(mean_dist * 1.2))
    score = int(distance_score * (0.4 + 0.6 * ratio))

    fils = f"{len(pes_colors)}/{len(svg_colors)} fil(s)"
    if score >= 85:
        msg = f"Couleurs fidèles (Δ Lab moyen {mean_dist:.1f}, {fils})"
    elif score >= 60:
        msg = f"Fidélité correcte (Δ Lab {mean_dist:.1f}, {fils})"
    elif score >= 30:
        msg = f"Dérive couleurs notable (Δ Lab {mean_dist:.1f}, {fils})"
    else:
        msg = (
            f"Mauvaise fidélité couleurs (Δ Lab {mean_dist:.1f}, {fils} "
            "— vectorisation partielle ?)"
        )
    return score, msg


def _score_vectorization_coverage(
    svg_path: Path,
    n_colors_requested: int | None,
) -> tuple[int, str]:
    """
    Pour PNG/JPEG/WebP/PDF scannés : vérifie que le nombre de couleurs non-blanches
    obtenues dans le SVG est cohérent avec le nombre de couleurs demandé.
    Retourne (100, msg) si n_colors_requested est None (SVG direct, PDF vectoriel).
    """
    if n_colors_requested is None:
        return 100, "Source vectorielle — couverture non applicable"

    svg_colors = _extract_svg_colors(svg_path)
    n_obtained = len(svg_colors)

    if n_obtained == 0:
        return 0, "SVG sans couleur — vectorisation échouée ou image blanche"

    ratio = min(n_obtained, n_colors_requested) / max(n_obtained, n_colors_requested)
    score = int(ratio * 100)
    # Plancher à 40 : une vectorisation qui produit au moins 1 couleur n'est pas un échec total,
    # même si l'image avait naturellement moins de couleurs que demandé.
    score = max(score, 40)
    # Quasi-couverture : une couleur manquante = vraisemblablement le fond blanc retiré par
    # remove_bg, pas un échec de vectorisation. Floor 80 reflète cette situation normale.
    if n_obtained >= n_colors_requested - 1 and n_obtained > 0:
        score = max(score, 80)

    if n_obtained == n_colors_requested:
        msg = f"{n_obtained}/{n_colors_requested} couleurs vectorisées — couverture exacte"
    elif score >= 75:
        msg = (
            f"{n_obtained}/{n_colors_requested} couleurs vectorisées — bonne couverture"
        )
    elif score >= 50:
        msg = f"{n_obtained}/{n_colors_requested} couleurs vectorisées — couverture partielle"
    else:
        msg = f"{n_obtained}/{n_colors_requested} couleurs vectorisées — vectorisation appauvrie"
    return score, msg


# ---------------------------------------------------------------------------
# Score qualité principal
# ---------------------------------------------------------------------------


def _compute_quality_score(
    pattern: pyembroidery.EmbPattern,
    source_svg_path: Path | None = None,
    n_colors_requested: int | None = None,
) -> dict:
    """
    Score qualité 0-100 pour Brother PR1050X.
    7 critères pondérés + gate critique sur les critères essentiels.

    Pondération :
      fils        18%   contrainte machine 10 aiguilles
      points      18%   densité design
      dimensions  14%   zone broderie 360×200mm
      sauts       10%   qualité du séquençage
      densité     10%   points/mm²
      fidélité    18%   couleurs SVG→PES (Lab)
      couverture  12%   nb couleurs obtenues vs demandées
    """
    raw_threadlist = pattern.threadlist or []
    threadlist, _ = _filter_pes_v1_color_breaks(raw_threadlist)
    thread_count = len(threadlist)
    stitch_count = pattern.count_stitch_commands(pyembroidery.STITCH)
    jump_count = pattern.count_stitch_commands(pyembroidery.JUMP)

    bounds = pattern.bounds()
    if bounds and len(bounds) == 4 and not math.isinf(bounds[0]):
        width_mm = (bounds[2] - bounds[0]) / 10
        height_mm = (bounds[3] - bounds[1]) / 10
    else:
        width_mm = 0.0
        height_mm = 0.0

    # 1. Fils (18%) — PR1050X : max 10 aiguilles, idéal ≤7
    if thread_count == 0:
        t_score = 0
        t_msg = "Aucun fil — design vide"
    elif thread_count <= 7:
        t_score = 100
        t_msg = f"{thread_count} fil(s) — idéal PR1050X (≤7)"
    elif thread_count <= 10:
        # Resserré : 60 au lieu de 75 — dépasse déjà les 7 idéaux
        t_score = 60
        t_msg = f"{thread_count} fils — dépasse les 7 idéaux, re-enfilage possible"
    elif thread_count <= 15:
        # Resserré : 25 au lieu de 35 — re-enfilage = coût opérationnel réel
        t_score = 25
        t_msg = (
            f"{thread_count} fils — dépasse les 10 aiguilles, re-enfilage nécessaire"
        )
    else:
        t_score = 0
        t_msg = f"{thread_count} fils — impossible sans re-enfilage multiple"

    # 2. Points (18%) — PR1050X : < 500k recommandé
    if stitch_count < 100:
        s_score = 0
        s_msg = f"{stitch_count} points — design quasi vide"
    elif stitch_count < 500:
        s_score = 20
        s_msg = f"{stitch_count} points — design très pauvre"
    elif stitch_count < 1200:
        s_score = 60
        s_msg = f"{stitch_count} points — design simple"
    elif stitch_count <= 50000:
        s_score = 100
        s_msg = f"{stitch_count:,} points — excellent (design professionnel)"
    elif stitch_count <= 150000:
        s_score = 75
        s_msg = f"{stitch_count:,} points — design complexe, broderie longue"
    elif stitch_count <= 500000:
        s_score = 35
        s_msg = f"{stitch_count:,} points — très dense, risque dépasser limites machine"
    else:
        s_score = 0
        s_msg = f"{stitch_count:,} points — dépasse la limite recommandée (500 000)"

    # 3. Dimensions (14%) — PR1050X : zone max 360×200mm
    if width_mm > 0 and height_mm > 0:
        if width_mm <= 360 and height_mm <= 200:
            if width_mm >= 20 and height_mm >= 5:
                d_score = 100
                d_msg = f"{width_mm:.0f}×{height_mm:.0f} mm — dans la zone PR1050X"
            else:
                d_score = 35
                d_msg = (
                    f"{width_mm:.0f}×{height_mm:.0f} mm — très petit, "
                    "détails risquent d'être illisibles"
                )
        elif width_mm <= 400 and height_mm <= 230:
            d_score = 55
            d_msg = f"{width_mm:.0f}×{height_mm:.0f} mm — légèrement hors zone (max 360×200 mm)"
        else:
            d_score = 0
            d_msg = f"{width_mm:.0f}×{height_mm:.0f} mm — hors zone de broderie (max 360×200 mm)"
    else:
        d_score = 50
        d_msg = "Dimensions non disponibles"

    # 4. Sauts de fil (10%) — seuils resserrés pour machine pro
    total_cmds = stitch_count + jump_count
    jump_ratio = jump_count / total_cmds if total_cmds > 0 else 0.0
    if jump_ratio < 0.005:
        # Resserré : <0.5% (était <1%) pour machine pro
        j_score = 100
        j_msg = f"{jump_count} saut(s) ({jump_ratio*100:.1f}%) — excellent"
    elif jump_ratio < 0.02:
        # Resserré : <2% (était <3%)
        j_score = 80
        j_msg = f"{jump_count} sauts ({jump_ratio*100:.1f}%) — normal"
    elif jump_ratio < 0.08:
        j_score = 45
        j_msg = (
            f"{jump_count} sauts ({jump_ratio*100:.1f}%) — nombreux, risque casse fil"
        )
    else:
        j_score = 10
        j_msg = f"{jump_count} sauts ({jump_ratio*100:.1f}%) — excessif, design mal optimisé"

    # 5. Densité points/mm² (10%)
    if width_mm > 0 and height_mm > 0:
        area = width_mm * height_mm
        density = stitch_count / area if area > 0 else 0.0
        if 0.5 <= density <= 20:
            dens_score = 100
            dens_msg = f"{density:.1f} pts/mm² — densité optimale broderie"
        elif 0.2 <= density < 0.5:
            dens_score = 75
            dens_msg = f"{density:.2f} pts/mm² — densité légère (contours/outlines)"
        elif 20 < density <= 50:
            dens_score = 65
            dens_msg = f"{density:.0f} pts/mm² — remplissage dense (fill stitch normal)"
        elif density < 0.2:
            dens_score = 20
            dens_msg = f"{density:.3f} pts/mm² — design presque vide"
        else:
            dens_score = 15
            dens_msg = f"{density:.0f} pts/mm² — très dense, risque déformation tissu"
    else:
        density = 0.0
        dens_score = 50
        dens_msg = "Densité non calculable"

    # Correction density-aware pour designs compacts (textes, contours fins, petits logos) :
    # stitch_count < 500 → normalement s_score=20 "très pauvre", mais si density >= 0.2 pts/mm²
    # la faiblesse vient de la taille du design, pas d'un défaut de conversion.
    if s_score == 20 and density >= 0.2:
        s_score = 60
        s_msg = (
            f"{stitch_count} points — design compact (densité {density:.2f} pts/mm²)"
        )

    # 6. Fidélité couleurs SVG→PES (18%)
    if source_svg_path and source_svg_path.exists():
        c_score, c_msg = _score_color_fidelity(pattern, source_svg_path)
    else:
        c_score, c_msg = 50, "SVG source non disponible pour comparaison couleurs"

    # 7. Couverture vectorisation (12%)
    if source_svg_path and source_svg_path.exists():
        cov_score, cov_msg = _score_vectorization_coverage(
            source_svg_path, n_colors_requested
        )
    else:
        cov_score, cov_msg = 50, "SVG source non disponible"

    # Score pondéré avec valeurs brutes et seuils pour le debug
    details = {
        "threads": {
            "score": t_score,
            "message": t_msg,
            "weight": 18,
            "raw_value": thread_count,
            "thresholds": {"ideal": 7, "max_machine": 10, "hard_limit": 15},
        },
        "stitches": {
            "score": s_score,
            "message": s_msg,
            "weight": 18,
            "raw_value": stitch_count,
            "thresholds": {
                "min_simple": 500,
                "min_pro": 2000,
                "max_recommended": 500000,
            },
        },
        "dimensions": {
            "score": d_score,
            "message": d_msg,
            "weight": 14,
            "raw_value": {
                "width_mm": round(width_mm, 1),
                "height_mm": round(height_mm, 1),
            },
            "thresholds": {"max_w": 360, "max_h": 200},
        },
        "jumps": {
            "score": j_score,
            "message": j_msg,
            "weight": 10,
            "raw_value": {
                "jump_count": jump_count,
                "ratio_pct": round(jump_ratio * 100, 2),
            },
            "thresholds": {"excellent_pct": 0.5, "normal_pct": 2.0, "bad_pct": 8.0},
        },
        "density": {
            "score": dens_score,
            "message": dens_msg,
            "weight": 10,
            "raw_value": round(density, 3),
            "thresholds": {"min": 0.5, "max": 20.0},
        },
        "color_fidelity": {
            "score": c_score,
            "message": c_msg,
            "weight": 18,
            "raw_value": None,
        },
        "coverage": {
            "score": cov_score,
            "message": cov_msg,
            "weight": 12,
            "raw_value": None,
        },
    }

    raw = sum(d["score"] * d["weight"] for d in details.values()) // 100

    # Gate critique : si un critère essentiel est effondré → cap à 40
    # Pour les SVG directs (n_colors_requested is None), la fidélité couleurs dépend entièrement
    # d'Ink/Stitch (hors de notre contrôle) — elle n'active pas la gate.
    if n_colors_requested is None:
        essential_min = s_score
    else:
        # cov_score n'active plus le gate : un logo monochrome uploadé avec n_colors=6 (défaut)
        # vectorise légitimement 1 couleur → ratio 1/6 ne doit pas pénaliser brutalement.
        # La couverture pèse quand même 12% dans le score pondéré.
        essential_min = min(s_score, c_score)
    if essential_min < 20:
        total = min(raw, 40)
    elif essential_min < 40:
        total = min(raw, 65)
    else:
        total = raw

    gate_applied = total < raw

    if total >= 85:
        label, color = "Excellent", "success"
    elif total >= 70:
        label, color = "Bon", "info"
    elif total >= 50:
        label, color = "Acceptable", "warning"
    else:
        label, color = "Problématique", "error"

    logger.debug(
        "quality_score_breakdown job=%s score=%d/%d label=%s gate=%s breakdown=%s",
        source_svg_path.stem if source_svg_path else "unknown",
        total,
        raw,
        label,
        gate_applied,
        json.dumps(
            {
                k: {"score": v["score"], "raw": v.get("raw_value"), "msg": v["message"]}
                for k, v in details.items()
            },
            ensure_ascii=False,
        ),
    )

    return {
        "score": total,
        "label": label,
        "color": color,
        "details": details,
        "jump_count": jump_count,
        "jump_ratio": round(jump_ratio * 100, 1),
        "raw_score_before_gate": raw,
        "gate_applied": gate_applied,
    }


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def generate_pes_preview(pes_path: Path, output_dir: Path) -> Path | None:
    """
    Génère un PNG de prévisualisation depuis un fichier PES via Pillow.
    Itère sur pattern.stitches et ne dessine que les commandes STITCH.
    Les JUMP/TRIM ne sont pas dessinés → pas de lignes parasites.
    Les COLOR_BREAK PES v1 blancs sont filtrés avant le rendu.
    Retourne le chemin du PNG, ou None si la génération échoue.
    Ne lève jamais d'exception — les erreurs sont loguées silencieusement.
    """
    try:
        pattern = pyembroidery.read(str(pes_path))
        if pattern is None:
            return None

        threadlist, _ = _filter_pes_v1_color_breaks(pattern.threadlist or [])
        if not threadlist or not pattern.stitches:
            return None

        bounds = pattern.bounds()
        if not bounds or len(bounds) < 4 or math.isinf(bounds[0]):
            return None
        min_x, min_y, max_x, max_y = bounds
        width = max_x - min_x
        height = max_y - min_y
        if width <= 0 or height <= 0:
            return None

        # Dimensions finales (inchangées vs avant)
        MAX_DIM = 1200
        # Rendu interne à 2× pour obtenir l'anti-aliasing via downsample LANCZOS
        RENDER_SCALE = 2
        # Fond crème/lin — simule un tissu blanc photographié sous lumière naturelle
        FABRIC_COLOR = (245, 240, 232)
        # Flou léger avant downsample pour simuler le relief arrondi du fil
        BLUR_RADIUS = 0.8

        scale = min(MAX_DIM / width, MAX_DIM / height, 1.0)
        img_w = max(1, int(width * scale))
        img_h = max(1, int(height * scale))

        # Canvas de rendu 2× — chaque stitch est dessiné plus épais, puis réduit
        render_scale = scale * RENDER_SCALE
        render_w = img_w * RENDER_SCALE
        render_h = img_h * RENDER_SCALE
        # 6px à 2× → ~3px après downsample, avec bords anti-aliasés
        line_w = max(2, round(6 * scale)) if scale < 1.0 else 6

        img = Image.new("RGB", (render_w, render_h), color=FABRIC_COLOR)
        draw = ImageDraw.Draw(img)

        def _thread_color(idx: int) -> tuple[int, int, int]:
            if idx >= len(threadlist):
                return (128, 128, 128)
            c = threadlist[idx].color
            return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)

        color_idx = 0
        last_x: float | None = None
        last_y: float | None = None

        for stitch in pattern.stitches:
            x, y, cmd = stitch[0], stitch[1], stitch[2] & 0xFF
            sx = int((x - min_x) * render_scale)
            sy = int((y - min_y) * render_scale)

            if cmd == pyembroidery.STITCH:
                if last_x is not None:
                    draw.line(
                        [(last_x, last_y), (sx, sy)],
                        fill=_thread_color(color_idx),
                        width=line_w,
                    )
                last_x, last_y = sx, sy
            elif cmd == pyembroidery.COLOR_CHANGE:
                color_idx += 1
                last_x = last_y = None
            else:
                # JUMP, TRIM, END et toutes autres commandes : reset sans dessiner
                last_x = last_y = None

        # Léger blur pour arrondir les bords du fil (simuler l'épaisseur réelle du fil)
        img = img.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
        # Downsample LANCZOS → anti-aliasing naturel des lignes
        img = img.resize((img_w, img_h), Image.LANCZOS)

        output_dir.mkdir(parents=True, exist_ok=True)
        preview_path = output_dir / (pes_path.stem + "_preview.png")
        img.save(str(preview_path))
        return preview_path if preview_path.exists() else None
    except Exception as exc:
        logger.warning("Échec génération preview pour %s : %s", pes_path.name, exc)
        return None


def extract_pes_metadata(
    pes_path: Path,
    source_svg_path: Path | None = None,
    n_colors_requested: int | None = None,
) -> dict:
    """
    Extrait les métadonnées de broderie depuis un fichier PES.

    Args:
        pes_path: Chemin vers le fichier PES.
        source_svg_path: SVG envoyé à Ink/Stitch (pour score fidélité couleurs).
        n_colors_requested: Nombre de couleurs demandé lors de la vectorisation
            (job.n_colors). None pour SVG direct et PDF vectoriel.

    Retourne un dict avec color_changes, width_mm, height_mm, stitch_count,
    time_minutes, thread_colors, quality_score, quality_label, quality_color,
    quality_details, jump_count, jump_ratio.
    Retourne {} si l'extraction échoue.
    """
    try:
        pattern = pyembroidery.read(str(pes_path))
        if pattern is None:
            return {}

        raw_threadlist = pattern.threadlist or []
        threadlist, was_filtered = _filter_pes_v1_color_breaks(raw_threadlist)
        if was_filtered:
            logger.info(
                "[pes] %d fils réels extraits (sur %d entries PES v1 avec COLOR_BREAK blancs)",
                len(threadlist),
                len(raw_threadlist),
            )
        color_changes = len(threadlist)

        thread_colors = [
            {"hex": f"#{t.color:06X}", "name": t.description or ""} for t in threadlist
        ]

        bounds = pattern.bounds()
        if bounds and len(bounds) == 4 and not math.isinf(bounds[0]):
            width_mm = round((bounds[2] - bounds[0]) / 10, 1)
            height_mm = round((bounds[3] - bounds[1]) / 10, 1)
        else:
            width_mm = None
            height_mm = None

        stitch_count = pattern.count_stitches()
        time_minutes = (
            round(stitch_count / _STITCHES_PER_MINUTE, 1) if stitch_count else None
        )

        quality = _compute_quality_score(pattern, source_svg_path, n_colors_requested)

        return {
            "color_changes": color_changes,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "stitch_count": stitch_count,
            "time_minutes": time_minutes,
            "thread_colors": thread_colors,
            "quality_score": quality["score"],
            "quality_label": quality["label"],
            "quality_color": quality["color"],
            "quality_details": quality["details"],
            "jump_count": quality["jump_count"],
            "jump_ratio": quality["jump_ratio"],
        }
    except Exception as exc:
        logger.warning("Échec extraction metadata pour %s : %s", pes_path.name, exc)
        return {}
