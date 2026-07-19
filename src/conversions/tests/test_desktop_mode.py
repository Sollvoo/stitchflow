import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from conversions.models import ConversionJob
from conversions.tasks import process_conversion_job
from conversions.views import _dispatch


MINIMAL_PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02'
    b'\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


class DesktopDispatchTest(TestCase):
    @override_settings(USE_CELERY=False)
    @patch('conversions.views.threading.Thread')
    def test_dispatch_marks_job_failed_when_thread_cannot_start(self, mock_thread):
        job = ConversionJob.objects.create(source_format='svg')
        job.original_file.save('test.svg', ContentFile(b'<svg/>'))
        mock_thread.return_value.start.side_effect = RuntimeError('thread refused')

        _dispatch(lambda _job_id: None, str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, ConversionJob.Status.FAILED)
        self.assertIn('Impossible de démarrer', job.error_message)


class DesktopAutoFinalizeTest(TestCase):
    @override_settings(DESKTOP_MODE=True)
    @patch('conversions.tasks._run_svg_to_pes_pipeline')
    @patch('conversions.services.png_processing.vectorize_to_svg')
    @patch('conversions.services.png_processing.preprocess_image')
    @patch('conversions.services.png_processing.validate_png')
    def test_desktop_png_auto_finalizes_after_vectorization(
        self, _mock_validate_png, mock_preprocess, mock_vectorize, mock_pipeline
    ):
        with tempfile.TemporaryDirectory() as media_root:
            media_root_path = Path(media_root)
            uploads_dir = media_root_path / 'conversions' / 'uploads'
            uploads_dir.mkdir(parents=True)
            png_path = uploads_dir / 'test.png'
            png_path.write_bytes(MINIMAL_PNG_BYTES)

            tmp_svg = media_root_path / 'vectorized-source.svg'
            tmp_svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><path fill="#000" d="M0 0"/></svg>',
                encoding='utf-8',
            )
            mock_preprocess.return_value = png_path
            mock_vectorize.return_value = tmp_svg

            def complete_job(job, _source_svg_path, start_time=None):
                job.status = ConversionJob.Status.COMPLETED
                job.progress_pct = 100
                job.progress_step = 'Conversion terminée'
                job.save(update_fields=['status', 'progress_pct', 'progress_step', 'updated_at'])

            mock_pipeline.side_effect = complete_job

            with override_settings(MEDIA_ROOT=media_root):
                job = ConversionJob.objects.create(source_format='png', n_colors=4)
                job.original_file.name = 'conversions/uploads/test.png'
                job.save(update_fields=['original_file'])

                process_conversion_job(str(job.id))

                job.refresh_from_db()
                self.assertEqual(job.status, ConversionJob.Status.COMPLETED)
                self.assertTrue(job.vectorized_svg_file.name.endswith(f'{job.id}.svg'))
                mock_pipeline.assert_called_once()


class AnalyzePDFDesktopTest(TestCase):
    @patch('conversions.services.png_processing.convert_pdf_to_png')
    @patch('conversions.services.pdf_processing.extract_vector_svg_from_pdf')
    def test_scanned_pdf_returns_warning_preview_and_suggested_width(
        self, mock_extract, mock_convert_pdf_to_png
    ):
        from conversions.services.pdf_processing import PDFExtractionError

        mock_extract.side_effect = PDFExtractionError('pdftocairo indisponible')
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as png_file:
            preview_path = Path(png_file.name)
        Image.new('RGB', (400, 200), 'white').save(preview_path, 'PNG')
        mock_convert_pdf_to_png.return_value = preview_path

        response = self.client.post(
            reverse('conversions:analyze_pdf'),
            {'original_file': SimpleUploadedFile('scan.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf')},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'pdf-suggestions', response.content)
        self.assertIn(b'data:image/png;base64,', response.content)
        self.assertIn(b'Largeur sugg', response.content)
        self.assertIn(b'101 mm', response.content)
