import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from conversions.models import ConversionJob
from conversions.tasks import process_conversion_job

MINIMAL_PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02'
    b'\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _make_png_job() -> ConversionJob:
    job = ConversionJob.objects.create(
        source_format='png',
        n_colors=4,
        remove_background=False,
    )
    job.original_file.save(f'{uuid.uuid4().hex}.png', ContentFile(MINIMAL_PNG_BYTES))
    return job


class ProcessPNGJobSuccessTest(TestCase):
    @patch('conversions.services.previews.extract_pes_metadata', return_value={'stitch_count': 100})
    @patch('conversions.services.previews.generate_pes_preview', return_value=None)
    @patch('conversions.services.inkstitch.convert_svg_to_pes')
    @patch('conversions.services.validation.validate_svg_content')
    @patch('conversions.services.png_processing.vectorize_to_svg')
    @patch('conversions.services.png_processing.preprocess_image')
    @patch('conversions.services.png_processing.validate_png')
    def test_png_job_completes(
        self, mock_validate_png, mock_preprocess, mock_vectorize,
        mock_validate_svg, mock_convert, mock_preview, mock_meta,
    ):
        import tempfile
        from django.test import override_settings

        with tempfile.TemporaryDirectory() as media_root:
            # Faux SVG temporaire retourné par vectorize_to_svg
            tmp_svg = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
            tmp_svg.write(b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
            tmp_svg.close()
            tmp_svg_path = Path(tmp_svg.name)

            # Faux PNG preprocessé
            tmp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_png.write(MINIMAL_PNG_BYTES)
            tmp_png.close()
            tmp_png_path = Path(tmp_png.name)

            mock_preprocess.return_value = tmp_png_path
            mock_vectorize.return_value = tmp_svg_path

            # Faux PES dans le MEDIA_ROOT temporaire
            pes_dir = Path(media_root) / 'conversions' / 'outputs'
            pes_dir.mkdir(parents=True)
            tmp_pes_path = pes_dir / 'result.pes'
            tmp_pes_path.write_bytes(b'PES_DATA')
            mock_convert.return_value = tmp_pes_path

            with override_settings(MEDIA_ROOT=media_root):
                job = _make_png_job()
                # Mettre à jour le chemin du fichier original dans le MEDIA_ROOT temporaire
                uploads_dir = Path(media_root) / 'conversions' / 'uploads'
                uploads_dir.mkdir(parents=True, exist_ok=True)
                png_path = uploads_dir / f'{uuid.uuid4().hex}.png'
                png_path.write_bytes(MINIMAL_PNG_BYTES)
                job.original_file.name = str(png_path.relative_to(media_root))
                job.save(update_fields=['original_file'])

                process_conversion_job(str(job.id))
                job.refresh_from_db()
                self.assertEqual(job.status, ConversionJob.Status.COMPLETED)
                mock_validate_png.assert_called_once()
                mock_preprocess.assert_called_once()
                mock_vectorize.assert_called_once()


class ProcessPNGJobPNGValidationErrorTest(TestCase):
    @patch('conversions.services.png_processing.validate_png')
    def test_png_validation_error_sets_failed(self, mock_validate_png):
        from conversions.services.png_processing import PNGValidationError
        mock_validate_png.side_effect = PNGValidationError('PNG invalide')

        job = _make_png_job()
        process_conversion_job(str(job.id))
        job.refresh_from_db()

        self.assertEqual(job.status, ConversionJob.Status.FAILED)
        self.assertIn('PNG invalide', job.error_message)


class ProcessPNGJobVectorizationErrorTest(TestCase):
    @patch('conversions.services.png_processing.vectorize_to_svg')
    @patch('conversions.services.png_processing.preprocess_image')
    @patch('conversions.services.png_processing.validate_png')
    def test_vectorization_error_sets_failed(
        self, mock_validate_png, mock_preprocess, mock_vectorize
    ):
        import tempfile

        tmp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp_png.write(MINIMAL_PNG_BYTES)
        tmp_png.close()
        mock_preprocess.return_value = Path(tmp_png.name)
        mock_vectorize.side_effect = RuntimeError('VTracer crash')

        job = _make_png_job()
        process_conversion_job(str(job.id))
        job.refresh_from_db()

        self.assertEqual(job.status, ConversionJob.Status.FAILED)
        self.assertIn('VTracer crash', job.error_message)
