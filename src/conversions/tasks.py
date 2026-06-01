import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def process_conversion_job(self, job_id: str) -> None:
    """
    Tâche Celery principale : convertit un SVG en PES via Ink/Stitch.

    Cycle de vie du job :
        pending → processing → completed | failed
    """
    # Import ici pour éviter les imports circulaires au démarrage Celery
    from .models import ConversionJob
    from .services.inkstitch import convert_svg_to_pes, InkstitchError

    try:
        job = ConversionJob.objects.get(id=job_id)
    except ConversionJob.DoesNotExist:
        logger.error("ConversionJob %s introuvable.", job_id)
        return

    job.status = ConversionJob.Status.PROCESSING
    job.error_message = ''
    job.save(update_fields=['status', 'error_message', 'updated_at'])
    logger.info("Démarrage conversion job %s", job_id)

    try:
        input_path = Path(settings.MEDIA_ROOT) / job.original_file.name
        output_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'outputs'

        pes_path = convert_svg_to_pes(input_path, output_dir)

        # Stocker le chemin relatif au MEDIA_ROOT dans le FileField
        relative_path = pes_path.relative_to(settings.MEDIA_ROOT)
        job.output_file.name = str(relative_path)
        job.status = ConversionJob.Status.COMPLETED
        job.save(update_fields=['status', 'output_file', 'updated_at'])
        logger.info("Conversion job %s terminée : %s", job_id, pes_path)

    except (InkstitchError, FileNotFoundError, Exception) as exc:
        error_msg = str(exc)
        logger.error("Échec conversion job %s : %s", job_id, error_msg)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])
