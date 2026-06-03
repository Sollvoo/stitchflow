"""
Génération de prévisualisations et extraction de métadonnées depuis les fichiers PES.
Utilise pyembroidery pour lire le PES et générer un PNG.
"""
import logging
import math
from pathlib import Path

import pyembroidery

logger = logging.getLogger(__name__)

# Vitesse conservative de broderie pour estimation du temps (points/minute)
# Brother PR1050X : max 1000 spm, estimation prudente à 600 spm pour designs normaux
_STITCHES_PER_MINUTE = 600


def generate_pes_preview(pes_path: Path, output_dir: Path) -> Path | None:
    """
    Génère un PNG de prévisualisation depuis un fichier PES.
    Retourne le chemin du PNG, ou None si la génération échoue.
    Ne lève jamais d'exception — les erreurs sont loguées silencieusement.
    """
    try:
        pattern = pyembroidery.read(str(pes_path))
        if pattern is None:
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        preview_path = output_dir / (pes_path.stem + '_preview.png')

        pyembroidery.write(pattern, str(preview_path))

        return preview_path if preview_path.exists() else None
    except Exception as exc:
        logger.warning("Échec génération preview pour %s : %s", pes_path.name, exc)
        return None


def extract_pes_metadata(pes_path: Path) -> dict:
    """
    Extrait les métadonnées de broderie depuis un fichier PES.

    Retourne un dict avec :
        - color_changes (int) : nombre de fils/couleurs
        - width_mm (float | None) : largeur du motif en mm
        - height_mm (float | None) : hauteur du motif en mm
        - stitch_count (int) : nombre total de points
        - time_minutes (float | None) : temps de broderie estimé en minutes
        - thread_colors (list) : [{hex, name}] pour chaque fil

    Retourne {} si l'extraction échoue — ne lève jamais d'exception.
    """
    try:
        pattern = pyembroidery.read(str(pes_path))
        if pattern is None:
            return {}

        # Couleurs / fils
        threadlist = pattern.threadlist or []
        color_changes = len(threadlist)

        thread_colors = []
        for thread in threadlist:
            thread_colors.append({
                'hex': f'#{thread.color:06X}',
                'name': thread.description or '',
            })

        # Dimensions depuis les bounds
        bounds = pattern.bounds()
        if bounds and len(bounds) == 4 and not math.isinf(bounds[0]):
            # pyembroidery retourne les bounds en unités de 0.1 mm
            width_mm = round((bounds[2] - bounds[0]) / 10, 1)
            height_mm = round((bounds[3] - bounds[1]) / 10, 1)
        else:
            width_mm = None
            height_mm = None

        # Points et temps estimé
        stitch_count = pattern.count_stitches()
        time_minutes = round(stitch_count / _STITCHES_PER_MINUTE, 1) if stitch_count else None

        return {
            'color_changes': color_changes,
            'width_mm': width_mm,
            'height_mm': height_mm,
            'stitch_count': stitch_count,
            'time_minutes': time_minutes,
            'thread_colors': thread_colors,
        }
    except Exception as exc:
        logger.warning("Échec extraction metadata pour %s : %s", pes_path.name, exc)
        return {}
