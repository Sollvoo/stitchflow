"""
Estimation du temps de conversion affiché à l'utilisateur pendant le traitement.
Priorité à la moyenne historique réelle (auto-corrective) ; repli sur une
heuristique statique tant que l'historique est trop pauvre.
"""

import logging

logger = logging.getLogger(__name__)

_MIN_SAMPLES = 5
_HISTORY_WINDOW = 20


def _static_heuristic(
    source_format: str, n_colors: int | None, remove_background: bool
) -> int:
    if source_format in ("png", "jpeg", "webp"):
        n = n_colors or 6
        return 4 + int(n * 1.5) + (4 if remove_background else 0)
    if source_format == "pdf":
        n = n_colors or 6
        return 10 + int(n * 1.5) + (4 if remove_background else 0)
    return 6


def estimate_duration_seconds(
    source_format: str, n_colors: int | None, remove_background: bool
) -> int:
    """
    Retourne une estimation en secondes pour un job PROCESSING.
    Utilise la moyenne des N dernières conversions complétées du même format
    si suffisamment d'échantillons existent, sinon une heuristique statique.
    """
    from ..models import ConversionJob

    durations = list(
        ConversionJob.objects.filter(
            status=ConversionJob.Status.COMPLETED,
            source_format=source_format,
            duration_seconds__isnull=False,
        )
        .order_by("-created_at")
        .values_list("duration_seconds", flat=True)[:_HISTORY_WINDOW]
    )

    if len(durations) >= _MIN_SAMPLES:
        avg = sum(durations) / len(durations)
        return max(1, round(avg))

    return _static_heuristic(source_format, n_colors, remove_background)
