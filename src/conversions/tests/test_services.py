import io
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from conversions.services.inkstitch import InkstitchError, convert_svg_to_pes, humanize_inkstitch_error
from conversions.services.validation import SVGValidationError, validate_svg_content, validate_svg_structure

VALID_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="red" width="50" height="50"/></svg>'
NO_ELEMENT_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><g></g></svg>'
ZERO_WIDTH_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="0" height="100"><rect fill="red" width="50" height="50"/></svg>'
BROKEN_XML = '<svg><unclosed'
NOT_SVG_XML = '<html><body>not svg</body></html>'


def _write_svg(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w', encoding='utf-8')
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _make_zip_with_pes(pes_name: str = 'output.pes') -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(pes_name, b'\x23\x50\x45\x53')  # minimal PES magic bytes
    return buf.getvalue()


# ──────────────────────────────────────────────
# validate_svg_structure
# ──────────────────────────────────────────────

class ValidateSvgStructureTest(TestCase):
    def test_valid_svg_passes(self):
        path = _write_svg(VALID_SVG)
        try:
            validate_svg_structure(path)  # should not raise
        finally:
            path.unlink(missing_ok=True)

    def test_broken_xml_raises(self):
        path = _write_svg(BROKEN_XML)
        try:
            with self.assertRaises(ValidationError):
                validate_svg_structure(path)
        finally:
            path.unlink(missing_ok=True)

    def test_non_svg_root_raises(self):
        path = _write_svg(NOT_SVG_XML)
        try:
            with self.assertRaises(ValidationError):
                validate_svg_structure(path)
        finally:
            path.unlink(missing_ok=True)


# ──────────────────────────────────────────────
# validate_svg_content
# ──────────────────────────────────────────────

class ValidateSvgContentTest(TestCase):
    def test_valid_svg_with_filled_rect_passes(self):
        path = _write_svg(VALID_SVG)
        try:
            validate_svg_content(path)  # should not raise
        finally:
            path.unlink(missing_ok=True)

    def test_svg_without_brodable_elements_raises(self):
        path = _write_svg(NO_ELEMENT_SVG)
        try:
            with self.assertRaises(SVGValidationError):
                validate_svg_content(path)
        finally:
            path.unlink(missing_ok=True)

    def test_svg_with_zero_width_raises(self):
        path = _write_svg(ZERO_WIDTH_SVG)
        try:
            with self.assertRaises(SVGValidationError):
                validate_svg_content(path)
        finally:
            path.unlink(missing_ok=True)

    def test_svg_with_stroke_only_passes(self):
        stroke_svg = '<svg xmlns="http://www.w3.org/2000/svg"><path stroke="black" d="M0 0 L10 10"/></svg>'
        path = _write_svg(stroke_svg)
        try:
            validate_svg_content(path)  # should not raise
        finally:
            path.unlink(missing_ok=True)

    def test_svg_with_css_style_fill_passes(self):
        """SVG généré par Inkscape trace — fill via style= et non attribut direct."""
        inkscape_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
            '<path style="fill:#37379a" d="M 20,180 L 380,180 L 380,20 L 20,20 Z"/>'
            '</svg>'
        )
        path = _write_svg(inkscape_svg)
        try:
            validate_svg_content(path)  # should not raise
        finally:
            path.unlink(missing_ok=True)

    def test_svg_with_css_style_stroke_passes(self):
        """fill:none mais stroke défini via style CSS."""
        css_stroke_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<path style="fill:none;stroke:#000000" d="M 0,0 L 100,100"/>'
            '</svg>'
        )
        path = _write_svg(css_stroke_svg)
        try:
            validate_svg_content(path)  # should not raise
        finally:
            path.unlink(missing_ok=True)

    def test_svg_with_css_style_fill_none_raises(self):
        """style avec fill:none ET stroke:none = pas brodable."""
        no_fill_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<path style="fill:none;stroke:none" d="M 0,0 L 100,100"/>'
            '</svg>'
        )
        path = _write_svg(no_fill_svg)
        try:
            with self.assertRaises(SVGValidationError):
                validate_svg_content(path)
        finally:
            path.unlink(missing_ok=True)


# ──────────────────────────────────────────────
# convert_svg_to_pes
# ──────────────────────────────────────────────

class ConvertSvgToPesTest(TestCase):
    def setUp(self):
        self.svg_path = _write_svg(VALID_SVG)
        self.output_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        self.svg_path.unlink(missing_ok=True)
        for f in self.output_dir.iterdir():
            f.unlink()
        self.output_dir.rmdir()

    @patch('conversions.services.inkstitch.subprocess.run')
    def test_successful_conversion_returns_path(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _make_zip_with_pes('output.pes')
        mock_run.return_value = mock_result

        result = convert_svg_to_pes(self.svg_path, self.output_dir)

        self.assertIsInstance(result, Path)
        self.assertTrue(result.suffix == '.pes')

    @patch('conversions.services.inkstitch.subprocess.run')
    def test_nonzero_returncode_raises_inkstitch_error(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b''
        mock_result.stderr = b'Error: something went wrong'
        mock_run.return_value = mock_result

        with self.assertRaises(InkstitchError):
            convert_svg_to_pes(self.svg_path, self.output_dir)

    @patch('conversions.services.inkstitch.subprocess.run', side_effect=FileNotFoundError)
    def test_executable_not_found_raises(self, mock_run):
        with self.assertRaises(FileNotFoundError):
            convert_svg_to_pes(self.svg_path, self.output_dir)

    @patch('conversions.services.inkstitch.subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='inkstitch', timeout=120))
    def test_timeout_raises_inkstitch_error(self, mock_run):
        with self.assertRaises(InkstitchError):
            convert_svg_to_pes(self.svg_path, self.output_dir)

    @patch('conversions.services.inkstitch.subprocess.run')
    def test_empty_stdout_raises_inkstitch_error(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b''
        mock_run.return_value = mock_result

        with self.assertRaises(InkstitchError):
            convert_svg_to_pes(self.svg_path, self.output_dir)

    @patch('conversions.services.inkstitch.subprocess.run')
    def test_zip_without_pes_raises_inkstitch_error(self, mock_run):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('output.txt', 'not a pes file')
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = buf.getvalue()
        mock_run.return_value = mock_result

        with self.assertRaises(InkstitchError):
            convert_svg_to_pes(self.svg_path, self.output_dir)


# ──────────────────────────────────────────────
# humanize_inkstitch_error
# ──────────────────────────────────────────────

class HumanizeInkstitchErrorTest(TestCase):
    def test_stitchable_elements_error(self):
        result = humanize_inkstitch_error('Error: No stitchable elements found in the document')
        self.assertIn('brodables', result)

    def test_file_not_found_error(self):
        result = humanize_inkstitch_error("FileNotFoundError: inkstitch not found")
        self.assertIn('indisponible', result)

    def test_timeout_error(self):
        result = humanize_inkstitch_error('TimeoutExpired: inkstitch timed out after 120s')
        self.assertIn('complexe', result)

    def test_unknown_error_returned_as_is(self):
        raw = 'Some unknown error that does not match any pattern'
        result = humanize_inkstitch_error(raw)
        self.assertEqual(result, raw)
