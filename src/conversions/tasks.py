import logging
import shutil
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def process_conversion_job(self, job_id: str) -> None:
    """
    Tâche Celery principale : convertit un fichier en PES via Ink/Stitch.
    Supporte SVG (direct) et PNG (vectorisation VTracer → SVG puis Ink/Stitch).

    Cycle de vie du job :
        pending → processing → completed | failed
    """
    from .models import ConversionJob
    from .services.inkstitch import convert_svg_to_pes, InkstitchError, humanize_inkstitch_error
    from .services.previews import generate_pes_preview, extract_pes_metadata
    from .services.png_processing import PNGValidationError
    from .services.svg_utils import scale_svg_to_width_mm
    from .services.validation import validate_svg_content, SVGValidationError

    try:
        job = ConversionJob.objects.get(id=job_id)
    except ConversionJob.DoesNotExist:
        logger.error("ConversionJob %s introuvable.", job_id)
        return

    job.status = ConversionJob.Status.PROCESSING
    job.error_message = ''
    job.save(update_fields=['status', 'error_message', 'updated_at'])
    logger.info("Démarrage conversion job %s (format: %s)", job_id, job.source_format)

    scaled_svg_path: Path | None = None
    tmp_png_paths: list[Path] = []
    tmp_svg_path: Path | None = None  # SVG vectorisé depuis PNG (temporaire)

    try:
        input_path = Path(settings.MEDIA_ROOT) / job.original_file.name
        output_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'outputs'
        preview_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'previews'

        # --- Bloc PNG : vectorisation avant le pipeline SVG→PES ---
        if job.source_format == 'png':
            from .services.png_processing import (
                validate_png,
                preprocess_image,
                remove_background,
                vectorize_to_svg,
            )

            logger.info('[DEBUG task] n_colors=%s, remove_background=%s, target_width_mm=%s',
                        job.n_colors, job.remove_background, job.target_width_mm)

            validate_png(input_path)

            processed_path = preprocess_image(input_path)
            tmp_png_paths.append(processed_path)

            if job.remove_background:
                processed_path = remove_background(processed_path)
                tmp_png_paths.append(processed_path)
                logger.info("Suppression du fond effectuée pour job %s", job_id)

            tmp_svg_path = vectorize_to_svg(processed_path, n_colors=job.n_colors or 6)
            logger.info("Vectorisation SVG terminée pour job %s", job_id)

            # Copier le SVG vectorisé dans media/ pour l'aperçu comparatif
            vectorized_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'vectorized'
            vectorized_dir.mkdir(parents=True, exist_ok=True)
            dest_svg = vectorized_dir / f"{job.id}.svg"
            shutil.copy2(tmp_svg_path, dest_svg)
            job.vectorized_svg_file.name = str(dest_svg.relative_to(settings.MEDIA_ROOT))
            job.save(update_fields=['vectorized_svg_file', 'updated_at'])

            source_svg_path = tmp_svg_path
        else:
            source_svg_path = input_path

        # --- Pipeline SVG→PES commun ---
        validate_svg_content(source_svg_path)

        svg_to_convert = source_svg_path
        if job.target_width_mm:
            scaled_svg_path = scale_svg_to_width_mm(source_svg_path, job.target_width_mm)
            svg_to_convert = scaled_svg_path
            logger.info("SVG redimensionné à %dmm pour job %s", job.target_width_mm, job_id)

        pes_path = convert_svg_to_pes(svg_to_convert, output_dir)

        relative_pes_path = pes_path.relative_to(settings.MEDIA_ROOT)
        job.output_file.name = str(relative_pes_path)
        job.status = ConversionJob.Status.COMPLETED

        try:
            preview_path = generate_pes_preview(pes_path, preview_dir)
            if preview_path:
                relative_preview_path = preview_path.relative_to(settings.MEDIA_ROOT)
                job.preview_file.name = str(relative_preview_path)
        except Exception as preview_exc:
            logger.warning("Preview échouée pour job %s : %s", job_id, preview_exc)

        try:
            job.conversion_metadata = extract_pes_metadata(pes_path)
        except Exception as meta_exc:
            logger.warning("Metadata échouée pour job %s : %s", job_id, meta_exc)

        job.save(update_fields=['status', 'output_file', 'preview_file', 'conversion_metadata', 'updated_at'])
        logger.info("Conversion job %s terminée : %s", job_id, pes_path)

    except PNGValidationError as exc:
        error_msg = str(exc)
        logger.error("Validation PNG échouée pour job %s : %s", job_id, error_msg)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except SVGValidationError as exc:
        error_msg = str(exc)
        logger.error("Validation SVG échouée pour job %s : %s", job_id, error_msg)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except (InkstitchError, FileNotFoundError) as exc:
        error_msg = humanize_inkstitch_error(str(exc))
        logger.error("Échec conversion job %s : %s", job_id, str(exc))
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Erreur inattendue job %s : %s", job_id, error_msg)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    finally:
        for p in tmp_png_paths:
            if p and p.exists():
                p.unlink(missing_ok=True)
        if tmp_svg_path and tmp_svg_path.exists():
            tmp_svg_path.unlink(missing_ok=True)
        if scaled_svg_path and scaled_svg_path.exists():
            scaled_svg_path.unlink(missing_ok=True)
