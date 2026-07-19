import logging
import shutil
import time
from pathlib import Path

from django.conf import settings

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **_kwargs):
        def decorator(inner):
            inner.delay = inner
            return inner
        return decorator(func) if func else decorator

logger = logging.getLogger(__name__)


def _set_progress(job, pct: int, step: str) -> None:
    job.progress_pct = pct
    job.progress_step = step
    job.save(update_fields=['progress_pct', 'progress_step', 'updated_at'])
    logger.debug('[progress] job %s: %d%% (%s)', job.id, pct, step)

_DEFAULT_MACHINE = {
    'model': 'PR1050X',
    'needles': 10,
    'max_threads': 10,
    'hoop_width_mm': 360,
    'hoop_height_mm': 200,
    'format': 'PES',
}


def _resolve_machine_params(job) -> dict:
    """Paramètres machine du propriétaire du job — défaut PR1050X (jobs anonymes)."""
    if not job.user_id:
        return dict(_DEFAULT_MACHINE)
    try:
        from users.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user_id=job.user_id)
        return profile.machine_params()
    except Exception as exc:
        logger.warning("Profil machine illisible pour job %s : %s", job.id, exc)
        return dict(_DEFAULT_MACHINE)


def _run_svg_to_pes_pipeline(job, source_svg_path: Path, start_time: float | None = None) -> None:
    """
    Pipeline commun SVG→PES : validation, post-traitement, Ink/Stitch, preview, métadonnées.
    Met à jour job.status = COMPLETED en fin. Propage les exceptions vers l'appelant.

    start_time : time.monotonic() capturé au tout début de la tâche Celery appelante,
    utilisé pour calculer job.duration_seconds (base de l'estimation historique).
    """
    from .services.inkstitch import (
        convert_svg_to_pes,
        convert_pes_to_format,
        InkstitchError,
        humanize_inkstitch_error,
    )
    from .services.previews import generate_pes_preview, extract_pes_metadata
    from .services.svg_utils import (
        scale_svg_to_width_mm,
        reorder_svg_paths_for_minimal_jumps,
        filter_micro_paths,
        remove_background_fill,
        force_max_svg_colors,
        group_paths_by_color,
        normalize_stroke_only_paths,
        prepare_svg_for_inkstitch,
        close_open_paths,
        inject_inkstitch_namespace,
        inject_inkstitch_params,
        _count_svg_unique_fills,
    )
    from .services.validation import validate_svg_content

    output_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'outputs'
    preview_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'previews'

    machine = _resolve_machine_params(job)
    if machine['model'] != 'PR1050X':
        logger.info('[machine] job %s : %s', job.id, machine)

    scaled_svg_path: Path | None = None

    try:
        _excl_raw = (job.conversion_metadata or {}).get('excluded_colors', '')
        if _excl_raw:
            _excl_hexes = [h.strip() for h in _excl_raw.split(',') if h.strip().startswith('#')]
            if _excl_hexes:
                from .services.svg_utils import remove_excluded_colors_from_svg
                n_excl = remove_excluded_colors_from_svg(source_svg_path, _excl_hexes)
                if n_excl > 0:
                    logger.info('[excluded] %d éléments supprimés (%s) pour job %s', n_excl, _excl_hexes, job.id)

        _t0 = time.monotonic()
        prep_stats = prepare_svg_for_inkstitch(source_svg_path)
        logger.debug('[timing] job %s : prepare_svg_for_inkstitch %.2fs', job.id, time.monotonic() - _t0)
        if any(v > 0 for v in prep_stats.values()):
            logger.info('[svg-prep] job %s : %s', job.id, prep_stats)
        _set_progress(job, 10, 'Normalisation du dessin vectoriel')

        validate_svg_content(source_svg_path)

        if job.source_format != 'svg':
            n_bg = remove_background_fill(source_svg_path)
            if n_bg > 0:
                logger.info('[bg] %d fond(s) blanc supprimé(s) pour job %s', n_bg, job.id)

        n_micro = filter_micro_paths(source_svg_path, job.target_width_mm or 0)
        if n_micro > 0:
            logger.info('[6b] %d micro-paths supprimés pour job %s', n_micro, job.id)

        _t0 = time.monotonic()
        reorder_svg_paths_for_minimal_jumps(source_svg_path)
        group_paths_by_color(source_svg_path)
        logger.debug('[timing] job %s : reorder+group %.2fs', job.id, time.monotonic() - _t0)
        _set_progress(job, 25, 'Optimisation de l\'ordre de broderie')

        svg_to_convert = source_svg_path
        if job.target_width_mm:
            scaled_svg_path = scale_svg_to_width_mm(source_svg_path, job.target_width_mm)
            svg_to_convert = scaled_svg_path
            logger.info("SVG redimensionné à %dmm pour job %s", job.target_width_mm, job.id)

        _t0 = time.monotonic()
        n_merged = force_max_svg_colors(svg_to_convert, max_colors=machine['max_threads'])
        if n_merged > 0:
            logger.info(
                '[colors] %d couleur(s) fusionnées → ≤%d fils pour job %s',
                n_merged, machine['max_threads'], job.id,
            )

        n_before_snap = _count_svg_unique_fills(svg_to_convert)
        try:
            from .services.thread_color import snap_svg_colors_to_brother_palette
            snap_svg_colors_to_brother_palette(svg_to_convert)
        except Exception as snap_exc:
            logger.warning("Snap couleurs Brother échoué pour job %s : %s", job.id, snap_exc)

        group_paths_by_color(svg_to_convert)
        n_after_snap = _count_svg_unique_fills(svg_to_convert)
        if n_after_snap != n_before_snap:
            logger.info(
                '[snap] %d couleurs → %d fils effectifs après snap Brother pour job %s',
                n_before_snap, n_after_snap, job.id,
            )
        logger.debug('[timing] job %s : couleurs (fusion+snap) %.2fs', job.id, time.monotonic() - _t0)
        _set_progress(job, 45, 'Adaptation de la palette de fils')

        params_stats = inject_inkstitch_params(svg_to_convert, job.target_width_mm or 0)
        if any(params_stats.values()):
            logger.info('[params] %s pour job %s', params_stats, job.id)

        n_stroke = normalize_stroke_only_paths(svg_to_convert)
        if n_stroke > 0:
            logger.info('[stroke] %d paths stroke-only convertis en fill pour job %s', n_stroke, job.id)

        n_closed = close_open_paths(svg_to_convert)
        if n_closed > 0:
            logger.info('[close] %d paths fill fermés pour job %s', n_closed, job.id)

        inject_inkstitch_namespace(svg_to_convert)
        _set_progress(job, 55, 'Préparation des paramètres de broderie')

        prepared_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'prepared'
        prepared_dir.mkdir(parents=True, exist_ok=True)
        prepared_svg_path = prepared_dir / f"{job.id}_prepared.svg"
        shutil.copy2(svg_to_convert, prepared_svg_path)
        job.prepared_svg_file.name = str(prepared_svg_path.relative_to(settings.MEDIA_ROOT))
        job.save(update_fields=['prepared_svg_file', 'updated_at'])

        _t0 = time.monotonic()
        pes_path = convert_svg_to_pes(svg_to_convert, output_dir)
        logger.debug('[timing] job %s : convert_svg_to_pes (Ink/Stitch) %.2fs', job.id, time.monotonic() - _t0)
        _set_progress(job, 90, 'Génération du fichier de broderie')

        # Export multi-format selon le profil machine — le PES reste la source
        # de vérité pour la preview et les métadonnées (DST ne stocke pas les couleurs)
        output_path = pes_path
        if machine['format'] != 'PES':
            try:
                output_path = convert_pes_to_format(pes_path, machine['format'])
                logger.info('[export] %s généré pour job %s', machine['format'], job.id)
            except Exception as export_exc:
                logger.warning(
                    'Export %s échoué pour job %s (PES conservé) : %s',
                    machine['format'], job.id, export_exc,
                )
                output_path = pes_path

        job.output_file.name = str(output_path.relative_to(settings.MEDIA_ROOT))
        job.status = job.__class__.Status.COMPLETED
        job.progress_pct = 100
        job.progress_step = 'Conversion terminée'
        if start_time is not None:
            job.duration_seconds = round(time.monotonic() - start_time, 1)

        try:
            preview_path = generate_pes_preview(pes_path, preview_dir)
            if preview_path:
                job.preview_file.name = str(preview_path.relative_to(settings.MEDIA_ROOT))
        except Exception as preview_exc:
            logger.warning("Preview échouée pour job %s : %s", job.id, preview_exc)

        try:
            job.conversion_metadata = extract_pes_metadata(
                pes_path,
                source_svg_path=svg_to_convert,
                n_colors_requested=job.n_colors if job.source_format != 'svg' else None,
                machine=machine,
            )
        except Exception as meta_exc:
            logger.warning("Metadata échouée pour job %s : %s", job.id, meta_exc)

        job.save(update_fields=[
            'status', 'output_file', 'preview_file', 'conversion_metadata',
            'progress_pct', 'progress_step', 'duration_seconds', 'updated_at',
        ])
        logger.info("Conversion job %s terminée : %s", job.id, pes_path)

    finally:
        if scaled_svg_path and scaled_svg_path.exists():
            scaled_svg_path.unlink(missing_ok=True)


@shared_task(bind=False, name='conversions.process_conversion_job')
def process_conversion_job(job_id: str) -> None:
    """
    Tâche Celery principale : vectorise le fichier source et sauvegarde le SVG intermédiaire.
    Pour les formats raster, s'arrête en AWAITING_SVG_VALIDATION pour que l'utilisateur
    valide le SVG avant la conversion PES (via finalize_svg_to_pes).
    Pour SVG direct, enchaîne immédiatement avec le pipeline SVG→PES.
    """
    from .models import ConversionJob
    from .services.inkstitch import humanize_inkstitch_error, InkstitchError
    from .services.pdf_processing import PDFExtractionError, GradientNotSupportedError
    from .services.png_processing import PNGValidationError
    from .services.validation import SVGValidationError

    try:
        job = ConversionJob.objects.get(id=job_id)
    except ConversionJob.DoesNotExist:
        logger.error("ConversionJob %s introuvable.", job_id)
        return

    start_time = time.monotonic()
    job.status = ConversionJob.Status.PROCESSING
    job.error_message = ''
    job.progress_pct = 0
    job.progress_step = ''
    job.save(update_fields=['status', 'error_message', 'progress_pct', 'progress_step', 'updated_at'])
    logger.info("Démarrage conversion job %s (format: %s)", job_id, job.source_format)

    tmp_png_paths: list[Path] = []
    tmp_svg_path: Path | None = None

    try:
        input_path = Path(settings.MEDIA_ROOT) / job.original_file.name
        vectorized_dir = Path(settings.MEDIA_ROOT) / 'conversions' / 'vectorized'
        vectorized_dir.mkdir(parents=True, exist_ok=True)

        source_svg_path: Path | None = None

        # --- Branche A : PDF vectoriel → extraction directe ---
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
                logger.info('[pdf] PDF vectoriel détecté — validation SVG avant PES pour job %s', job_id)
                postprocess_vector_svg(tmp_svg_path)

                dest_svg = vectorized_dir / f'{job.id}.svg'
                shutil.copy2(tmp_svg_path, dest_svg)
                job.vectorized_svg_file.name = str(dest_svg.relative_to(settings.MEDIA_ROOT))

                # Pause : l'utilisateur valide le SVG avant la conversion PES,
                # comme pour PNG/JPEG/WebP (éditeur couleurs/densité)
                job.status = ConversionJob.Status.AWAITING_SVG_VALIDATION
                job.save(update_fields=['status', 'vectorized_svg_file', 'updated_at'])
                logger.info("Job %s en attente de validation SVG (%s)", job_id, dest_svg.name)
                return
            else:
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
            _set_progress(job, 20, 'Validation de l\'image')

            _t0 = time.monotonic()
            processed_path = preprocess_image(raster_path)
            tmp_png_paths.append(processed_path)
            logger.debug('[timing] job %s : preprocess_image %.2fs', job_id, time.monotonic() - _t0)
            _set_progress(job, 45, 'Préparation de l\'image')

            if job.remove_background:
                _t0 = time.monotonic()
                processed_path = remove_background(processed_path)
                tmp_png_paths.append(processed_path)
                logger.debug('[timing] job %s : remove_background %.2fs', job_id, time.monotonic() - _t0)
                logger.info("Suppression du fond effectuée pour job %s", job_id)
                _set_progress(job, 65, 'Suppression du fond')

            _t0 = time.monotonic()
            tmp_svg_path = vectorize_to_svg(processed_path, n_colors=job.n_colors or 6)
            logger.debug('[timing] job %s : vectorize_to_svg %.2fs', job_id, time.monotonic() - _t0)
            logger.info("Vectorisation SVG terminée pour job %s", job_id)
            _set_progress(job, 95, 'Vectorisation du dessin')

            dest_svg = vectorized_dir / f'{job.id}.svg'
            shutil.copy2(tmp_svg_path, dest_svg)
            job.vectorized_svg_file.name = str(dest_svg.relative_to(settings.MEDIA_ROOT))

            # Pause : l'utilisateur valide le SVG avant la conversion PES
            job.status = ConversionJob.Status.AWAITING_SVG_VALIDATION
            job.progress_pct = 100
            job.progress_step = 'En attente de validation'
            job.save(update_fields=['status', 'vectorized_svg_file', 'progress_pct', 'progress_step', 'updated_at'])
            logger.info("Job %s en attente de validation SVG (%s)", job_id, dest_svg.name)
            return

        elif source_svg_path is None:
            # SVG direct : pas de pause, conversion immédiate
            source_svg_path = input_path

        # --- Pipeline SVG→PES (SVG direct uniquement depuis ici) ---
        _run_svg_to_pes_pipeline(job, source_svg_path, start_time=start_time)

    except PDFExtractionError as exc:
        logger.error("Extraction PDF échouée pour job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except GradientNotSupportedError as exc:
        logger.error("Gradients détectés pour job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except PNGValidationError as exc:
        logger.error("Validation PNG échouée pour job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except SVGValidationError as exc:
        logger.error("Validation SVG échouée pour job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except (InkstitchError, FileNotFoundError) as exc:
        error_msg = humanize_inkstitch_error(str(exc))
        logger.error("Échec conversion job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except Exception:
        logger.exception("Erreur inattendue job %s", job_id)
        job.status = ConversionJob.Status.FAILED
        job.error_message = "Une erreur interne est survenue. Veuillez réessayer."
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    finally:
        for p in tmp_png_paths:
            if p and p.exists():
                p.unlink(missing_ok=True)
        if tmp_svg_path and tmp_svg_path.exists():
            tmp_svg_path.unlink(missing_ok=True)


@shared_task(bind=False, name='conversions.finalize_svg_to_pes')
def finalize_svg_to_pes(job_id: str) -> None:
    """
    Tâche Celery de finalisation : reprend le pipeline SVG→PES depuis vectorized_svg_file.
    Déclenchée par SvgValidateView après validation utilisateur de l'éditeur SVG.
    """
    from .models import ConversionJob
    from .services.inkstitch import InkstitchError, humanize_inkstitch_error
    from .services.validation import SVGValidationError

    try:
        job = ConversionJob.objects.get(id=job_id)
    except ConversionJob.DoesNotExist:
        logger.error("ConversionJob %s introuvable pour finalisation.", job_id)
        return

    if not job.vectorized_svg_file:
        logger.error("Pas de vectorized_svg_file pour job %s", job_id)
        job.status = ConversionJob.Status.FAILED
        job.error_message = "SVG vectorisé introuvable."
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return

    start_time = time.monotonic()
    job.status = ConversionJob.Status.PROCESSING
    job.error_message = ''
    job.progress_pct = 0
    job.progress_step = ''
    job.save(update_fields=['status', 'error_message', 'progress_pct', 'progress_step', 'updated_at'])
    logger.info("Finalisation PES job %s depuis %s", job_id, job.vectorized_svg_file.name)

    svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
    import tempfile as _tmpmod
    import os as _os
    _fd, _tmp = _tmpmod.mkstemp(suffix='_finalize.svg')
    _os.close(_fd)
    tmp_working_svg = Path(_tmp)
    shutil.copy2(svg_path, tmp_working_svg)

    try:
        _run_svg_to_pes_pipeline(job, tmp_working_svg, start_time=start_time)

    except SVGValidationError as exc:
        logger.error("Validation SVG échouée pour job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except (InkstitchError, FileNotFoundError) as exc:
        error_msg = humanize_inkstitch_error(str(exc))
        logger.error("Échec conversion job %s : %s", job_id, exc)
        job.status = ConversionJob.Status.FAILED
        job.error_message = error_msg
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    except Exception:
        logger.exception("Erreur inattendue finalisation job %s", job_id)
        job.status = ConversionJob.Status.FAILED
        job.error_message = "Une erreur interne est survenue. Veuillez réessayer."
        job.save(update_fields=['status', 'error_message', 'updated_at'])

    finally:
        tmp_working_svg.unlink(missing_ok=True)
