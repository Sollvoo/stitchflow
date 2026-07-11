"""
Tests d'intégration : process_conversion_job, finalize_svg_to_pes, _resolve_machine_params.
Ink/Stitch et tous les services externes sont mockés dans leurs modules d'origine.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from conversions.models import ConversionJob
from conversions.tasks import (
    _resolve_machine_params,
    finalize_svg_to_pes,
    process_conversion_job,
    _DEFAULT_MACHINE,
)
from factories import ConversionJobFactory, UserFactory

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'


def _setup_media_dirs(tmp_path):
    for subdir in [
        "conversions/uploads",
        "conversions/outputs",
        "conversions/previews",
        "conversions/vectorized",
        "conversions/prepared",
        "conversions/snapshots",
    ]:
        os.makedirs(tmp_path / subdir, exist_ok=True)


# ---------------------------------------------------------------------------
# process_conversion_job — SVG direct path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_conversion_job_svg_completes(tmp_path, settings, mocker):
    """Pipeline SVG complet (services mockés) → status COMPLETED."""
    settings.MEDIA_ROOT = str(tmp_path)
    _setup_media_dirs(tmp_path)

    svg_path = tmp_path / "conversions" / "uploads" / "test.svg"
    svg_path.write_bytes(MINIMAL_SVG)
    pes_path = tmp_path / "conversions" / "outputs" / "test.pes"
    pes_path.write_bytes(b"#PES" + b"\x00" * 100)

    job = ConversionJobFactory(source_format="svg", status=ConversionJob.Status.PENDING)
    job.original_file.name = "conversions/uploads/test.svg"
    job.save()

    mocker.patch("conversions.services.svg_utils.prepare_svg_for_inkstitch", return_value={})
    mocker.patch("conversions.services.validation.validate_svg_content")
    mocker.patch("conversions.services.svg_utils.filter_micro_paths", return_value=0)
    mocker.patch("conversions.services.svg_utils.reorder_svg_paths_for_minimal_jumps")
    mocker.patch("conversions.services.svg_utils.group_paths_by_color", return_value=0)
    mocker.patch("conversions.services.svg_utils.force_max_svg_colors", return_value=0)
    mocker.patch("conversions.services.svg_utils._count_svg_unique_fills", return_value=1)
    mocker.patch("conversions.services.thread_color.snap_svg_colors_to_brother_palette")
    mocker.patch("conversions.services.svg_utils.inject_inkstitch_params", return_value={})
    mocker.patch("conversions.services.svg_utils.normalize_stroke_only_paths", return_value=0)
    mocker.patch("conversions.services.svg_utils.close_open_paths", return_value=0)
    mocker.patch("conversions.services.svg_utils.inject_inkstitch_namespace")
    mocker.patch("conversions.services.svg_utils.remove_background_fill", return_value=0)
    mocker.patch("conversions.services.inkstitch.convert_svg_to_pes", return_value=pes_path)
    mocker.patch("conversions.services.previews.generate_pes_preview", return_value=None)
    mocker.patch(
        "conversions.services.previews.extract_pes_metadata",
        return_value={"quality_score": 75},
    )

    process_conversion_job(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.COMPLETED
    assert job.duration_seconds is not None


@pytest.mark.django_db
def test_process_conversion_job_svg_validation_error(tmp_path, settings, mocker):
    """SVGValidationError → status FAILED, error_message sans traceback."""
    settings.MEDIA_ROOT = str(tmp_path)
    _setup_media_dirs(tmp_path)

    svg_path = tmp_path / "conversions" / "uploads" / "test.svg"
    svg_path.write_bytes(MINIMAL_SVG)

    job = ConversionJobFactory(source_format="svg")
    job.original_file.name = "conversions/uploads/test.svg"
    job.save()

    from conversions.services.validation import SVGValidationError
    mocker.patch("conversions.services.svg_utils.prepare_svg_for_inkstitch", return_value={})
    mocker.patch(
        "conversions.services.validation.validate_svg_content",
        side_effect=SVGValidationError("Pas d'éléments brodables"),
    )

    process_conversion_job(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.FAILED
    assert "Traceback" not in job.error_message
    assert 'File "' not in job.error_message


@pytest.mark.django_db
def test_process_conversion_job_inkstitch_error(tmp_path, settings, mocker):
    """InkstitchError → status FAILED, error_message humanisé."""
    settings.MEDIA_ROOT = str(tmp_path)
    _setup_media_dirs(tmp_path)

    svg_path = tmp_path / "conversions" / "uploads" / "test.svg"
    svg_path.write_bytes(MINIMAL_SVG)
    pes_path = tmp_path / "conversions" / "outputs" / "test.pes"
    pes_path.write_bytes(b"#PES")

    job = ConversionJobFactory(source_format="svg")
    job.original_file.name = "conversions/uploads/test.svg"
    job.save()

    from conversions.services.inkstitch import InkstitchError
    mocker.patch("conversions.services.svg_utils.prepare_svg_for_inkstitch", return_value={})
    mocker.patch("conversions.services.validation.validate_svg_content")
    mocker.patch("conversions.services.svg_utils.filter_micro_paths", return_value=0)
    mocker.patch("conversions.services.svg_utils.reorder_svg_paths_for_minimal_jumps")
    mocker.patch("conversions.services.svg_utils.group_paths_by_color", return_value=0)
    mocker.patch("conversions.services.svg_utils.force_max_svg_colors", return_value=0)
    mocker.patch("conversions.services.svg_utils._count_svg_unique_fills", return_value=1)
    mocker.patch("conversions.services.thread_color.snap_svg_colors_to_brother_palette")
    mocker.patch("conversions.services.svg_utils.inject_inkstitch_params", return_value={})
    mocker.patch("conversions.services.svg_utils.normalize_stroke_only_paths", return_value=0)
    mocker.patch("conversions.services.svg_utils.close_open_paths", return_value=0)
    mocker.patch("conversions.services.svg_utils.inject_inkstitch_namespace")
    mocker.patch("conversions.services.svg_utils.remove_background_fill", return_value=0)
    mocker.patch(
        "conversions.services.inkstitch.convert_svg_to_pes",
        side_effect=InkstitchError("no stitchable elements"),
    )

    process_conversion_job(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.FAILED
    assert job.error_message


@pytest.mark.django_db
def test_process_conversion_job_generic_exception(tmp_path, settings, mocker):
    """Exception générique → FAILED, message générique (pas de repr de l'exception)."""
    settings.MEDIA_ROOT = str(tmp_path)
    _setup_media_dirs(tmp_path)

    svg_path = tmp_path / "conversions" / "uploads" / "test.svg"
    svg_path.write_bytes(MINIMAL_SVG)

    job = ConversionJobFactory(source_format="svg")
    job.original_file.name = "conversions/uploads/test.svg"
    job.save()

    mocker.patch(
        "conversions.services.svg_utils.prepare_svg_for_inkstitch",
        side_effect=RuntimeError("super_secret_internal_error_xyz"),
    )

    process_conversion_job(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.FAILED
    assert "Traceback" not in job.error_message
    assert 'File "' not in job.error_message


@pytest.mark.django_db
def test_process_conversion_job_png_stops_at_awaiting(tmp_path, settings, mocker):
    """Pipeline PNG → statut AWAITING_SVG_VALIDATION (pause pour validation utilisateur)."""
    settings.MEDIA_ROOT = str(tmp_path)
    _setup_media_dirs(tmp_path)

    png_path = tmp_path / "conversions" / "uploads" / "test.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    svg_out = tmp_path / "conversions" / "vectorized" / "test.svg"
    svg_out.write_bytes(MINIMAL_SVG)

    job = ConversionJobFactory(source_format="png")
    job.original_file.name = "conversions/uploads/test.png"
    job.save()

    mocker.patch("conversions.services.png_processing.validate_png")
    mocker.patch("conversions.services.png_processing.preprocess_image", return_value=png_path)
    mocker.patch("conversions.services.png_processing.vectorize_to_svg", return_value=svg_out)

    process_conversion_job(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.AWAITING_SVG_VALIDATION


# ---------------------------------------------------------------------------
# finalize_svg_to_pes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_finalize_svg_to_pes_missing_vectorized_file_fails():
    """Pas de vectorized_svg_file → FAILED avec message explicite."""
    job = ConversionJobFactory(
        source_format="png",
        status=ConversionJob.Status.AWAITING_SVG_VALIDATION,
    )
    job.vectorized_svg_file = None
    job.save(update_fields=["vectorized_svg_file"])

    finalize_svg_to_pes(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.FAILED
    assert "SVG vectorisé introuvable" in job.error_message


@pytest.mark.django_db
def test_finalize_svg_to_pes_generic_exception(tmp_path, settings, mocker):
    """Exception dans le pipeline → FAILED, message générique."""
    settings.MEDIA_ROOT = str(tmp_path)
    _setup_media_dirs(tmp_path)

    svg_path = tmp_path / "conversions" / "vectorized" / "test.svg"
    svg_path.write_bytes(MINIMAL_SVG)

    job = ConversionJobFactory(
        source_format="png",
        status=ConversionJob.Status.AWAITING_SVG_VALIDATION,
    )
    job.vectorized_svg_file.name = "conversions/vectorized/test.svg"
    job.save()

    mocker.patch(
        "conversions.services.svg_utils.prepare_svg_for_inkstitch",
        side_effect=RuntimeError("crash"),
    )

    finalize_svg_to_pes(str(job.id))
    job.refresh_from_db()
    assert job.status == ConversionJob.Status.FAILED
    assert "Traceback" not in job.error_message


# ---------------------------------------------------------------------------
# _resolve_machine_params
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_resolve_machine_params_anonymous_job():
    """job.user_id=None → retourne le profil machine par défaut PR1050X."""
    job = ConversionJobFactory(user=None)
    params = _resolve_machine_params(job)
    assert params["model"] == "PR1050X"
    assert params["max_threads"] == 10
    assert params["format"] == "PES"


@pytest.mark.django_db
def test_resolve_machine_params_exception_fallback():
    """Exception dans get_or_create → fallback sur _DEFAULT_MACHINE."""
    user = UserFactory()
    job = ConversionJobFactory(user=user)

    with patch("users.models.UserProfile.objects.get_or_create") as mock_goc:
        mock_goc.side_effect = Exception("DB error")
        params = _resolve_machine_params(job)

    assert params["model"] == "PR1050X"
    assert params == dict(_DEFAULT_MACHINE)
