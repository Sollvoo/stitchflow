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
    from .services.pdf_processing import PDFExtractionError, GradientNotSupportedError
    from .services.previews import generate_pes_preview, extract_pes_metadata
    from .services.png_processing import PNGValidationError
    from .services.svg_utils import (
        scale_svg_to_width_mm,
        reorder_svg_paths_for_minimal_jumps,
        filter_micro_paths,
        remove_background_fill,
        force_max_svg_colors,
        group_paths_by_color,
        normalize_stroke_only_paths,
        _count_svg_unique_fills,
    )
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
        vectorized_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'vectorized'
        vectorized_dir.mkdir(parents=True, exist_ok=True)

        source_svg_path: Path | None = None  # chemin SVG à convertir (commun aux deux branches)

        # --- Branche A : PDF vectoriel → extraction directe sans rasterisation ---
        if job.source_format == 'pdf':
            from .services.pdf_processing import (
                extract_vector_svg_from_pdf,
                is_vector_pdf_svg,
                postprocess_vector_svg,
            )
            import tempfile as _tmpmod
            _fd, _svg_str = _tmpmod.mkstemp(suffix='_pdf_extracted.svg')
            import os as _os; _os.close(_fd)
            tmp_svg_path = Path(_svg_str)

            extract_vector_svg_from_pdf(input_path, tmp_svg_path)

            if is_vector_pdf_svg(tmp_svg_path):
                logger.info('[pdf] PDF vectoriel détecté — pipeline direct SVG→PES pour job %s', job_id)
                postprocess_vector_svg(tmp_svg_path)

                dest_svg = vectorized_dir / f'{job.id}.svg'
                shutil.copy2(tmp_svg_path, dest_svg)
                job.vectorized_svg_file.name = str(dest_svg.relative_to(settings.MEDIA_ROOT))
                job.save(update_fields=['vectorized_svg_file', 'updated_at'])

                source_svg_path = tmp_svg_path
            else:
                # PDF scanné : supprimer le SVG extrait et tomber dans le bloc raster
                logger.info('[pdf] PDF scanné détecté — fallback pipeline raster pour job %s', job_id)
                tmp_svg_path.unlink(missing_ok=True)
                tmp_svg_path = None

        # --- Branche B : PNG / JPEG / WebP / PDF scanné → vectorisation ---
        if source_svg_path is None and job.source_format in ('png', 'jpeg', 'webp', 'pdf'):
            from .services.png_processing import (
                validate_png,
                preprocess_image,
                remove_background,
                vectorize_to_svg,
                convert_to_png,
                convert_pdf_to_png,
            )

            logger.info('[DEBUG task] n_colors=%s, remove_background=%s, target_width_mm=%s',
                        job.n_colors, job.remove_background, job.target_width_mm)

            raster_path = input_path
            if job.source_format == 'pdf':
                converted_png = convert_pdf_to_png(input_path)
                tmp_png_paths.append(converted_png)
                raster_path = converted_png
                logger.info("PDF scanné rasterisé en PNG pour job %s", job_id)
            elif job.source_format in ('jpeg', 'webp'):
                converted_png = convert_to_png(input_path)
                tmp_png_paths.append(converted_png)
                raster_path = converted_png
                logger.info("%s converti en PNG pour job %s", job.source_format.upper(), job_id)

            validate_png(raster_path)

            processed_path = preprocess_image(raster_path)
            tmp_png_paths.append(processed_path)

            if job.remove_background:
                processed_path = remove_background(processed_path)
                tmp_png_paths.append(processed_path)
                logger.info("Suppression du fond effectuée pour job %s", job_id)

            tmp_svg_path = vectorize_to_svg(processed_path, n_colors=job.n_colors or 6)
            logger.info("Vectorisation SVG terminée pour job %s", job_id)

            dest_svg = vectorized_dir / f'{job.id}.svg'
            shutil.copy2(tmp_svg_path, dest_svg)
            job.vectorized_svg_file.name = str(dest_svg.relative_to(settings.MEDIA_ROOT))
            job.save(update_fields=['vectorized_svg_file', 'updated_at'])

            source_svg_path = tmp_svg_path

        elif source_svg_path is None:  # SVG direct
            source_svg_path = input_path

        # --- Pipeline SVG→PES commun ---
        _excl_raw = (job.conversion_metadata or {}).get('excluded_colors', '')
        if _excl_raw:
            _excl_hexes = [h.strip() for h in _excl_raw.split(',') if h.strip().startswith('#')]
            if _excl_hexes:
                from .services.svg_utils import remove_excluded_colors_from_svg
                n_excl = remove_excluded_colors_from_svg(source_svg_path, _excl_hexes)
                if n_excl > 0:
                    logger.info('[excluded] %d éléments supprimés (%s) pour job %s', n_excl, _excl_hexes, job_id)

        validate_svg_content(source_svg_path)

        # Fond blanc vectorisé → supprimer seulement pour PNG/JPEG/WebP/PDF (pas SVG direct)
        if job.source_format != 'svg':
            n_bg = remove_background_fill(source_svg_path)
            if n_bg > 0:
                logger.info('[bg] %d fond(s) blanc supprimé(s) pour job %s', n_bg, job_id)

        n_micro = filter_micro_paths(source_svg_path, job.target_width_mm or 0)
        if n_micro > 0:
            logger.info('[6b] %d micro-paths supprimés pour job %s', n_micro, job_id)

        # Reorder spatial NN, puis grouper par couleur pour limiter les changements de fil
        reorder_svg_paths_for_minimal_jumps(source_svg_path)
        group_paths_by_color(source_svg_path)

        svg_to_convert = source_svg_path
        if job.target_width_mm:
            scaled_svg_path = scale_svg_to_width_mm(source_svg_path, job.target_width_mm)
            svg_to_convert = scaled_svg_path
            logger.info("SVG redimensionné à %dmm pour job %s", job.target_width_mm, job_id)

        # Réduire d'abord à ≤10 couleurs, PUIS snapper vers la palette Brother.
        # Ordre optimal : fusion sur couleurs brutes → snap précis sur moins de couleurs distinctes.
        n_merged = force_max_svg_colors(svg_to_convert, max_colors=10)
        if n_merged > 0:
            logger.info('[colors] %d couleur(s) fusionnées → ≤10 fils pour job %s', n_merged, job_id)

        n_before_snap = _count_svg_unique_fills(svg_to_convert)
        try:
            from .services.thread_color import snap_svg_colors_to_brother_palette
            snap_svg_colors_to_brother_palette(svg_to_convert)
        except Exception as snap_exc:
            logger.warning("Snap couleurs Brother échoué pour job %s : %s", job_id, snap_exc)

        # reorder : NN spatial intra-groupe ; group_by_color : regroupe par couleur avec NN inter-groupes
        group_paths_by_color(svg_to_convert)
        n_after_snap = _count_svg_unique_fills(svg_to_convert)
        if n_after_snap != n_before_snap:
            logger.info(
                '[snap] %d couleurs → %d fils effectifs après snap Brother pour job %s',
                n_before_snap, n_after_snap, job_id,
            )

        # Convertir les paths stroke-only en fill pour garantir que Ink/Stitch les brod
        n_stroke = normalize_stroke_only_paths(svg_to_convert)
        if n_stroke > 0:
            logger.info('[stroke] %d paths stroke-only convertis en fill pour job %s', n_stroke, job_id)

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
            job.conversion_metadata = extract_pes_metadata(
                pes_path,
                source_svg_path=svg_to_convert,
                n_colors_requested=job.n_colors if job.source_format != 'svg' else None,
            )
        except Exception as meta_exc:
            logger.warning("Metadata échouée pour job %s : %s", job_id, meta_exc)

        job.save(update_fields=['status', 'output_file', 'preview_file', 'conversion_metadata', 'updated_at'])
        logger.info("Conversion job %s terminée : %s", job_id, pes_path)

    except PDFExtractionError as exc:
        error_msg = str(exc)
        logger.error("Extraction PDF échouée pour job %s : %s", job_id, error_msg)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except GradientNotSupportedError as exc:
        error_msg = str(exc)
        logger.error("Gradients détectés pour job %s : %s", job_id, error_msg)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

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
