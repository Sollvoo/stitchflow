import io
import struct
import tempfile
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase
from PIL import Image

from conversions.services.png_processing import (
    PNGValidationError,
    _build_svg,
    _color_to_pbm,
    _extract_potrace_paths,
    _vectorize_potrace,
    preprocess_image,
    remove_background,
    validate_png,
    vectorize_to_svg,
)


def _make_tiny_png(width: int = 4, height: int = 4) -> bytes:
    """Génère un PNG minimal valide en mémoire (pixels rouges)."""
    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)
    raw_rows = b''.join(b'\x00' + b'\xff\x00\x00' * width for _ in range(height))
    idat = chunk(b'IDAT', zlib.compress(raw_rows))
    iend = chunk(b'IEND', b'')
    return signature + ihdr + idat + iend


def _tmp_png(width: int = 4, height: int = 4) -> Path:
    data = _make_tiny_png(width, height)
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


class ValidatePNGTest(TestCase):
    def test_valid_png_passes(self):
        p = _tmp_png()
        try:
            validate_png(p)
        finally:
            p.unlink(missing_ok=True)

    def test_wrong_magic_bytes_raises(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.write(b'NOTAPNG\x00' * 10)
        tmp.close()
        p = Path(tmp.name)
        try:
            with self.assertRaises(PNGValidationError):
                validate_png(p)
        finally:
            p.unlink(missing_ok=True)

    def test_oversized_raises(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.write(b'\x89PNG' + b'\x00' * (21 * 1024 * 1024))
        tmp.close()
        p = Path(tmp.name)
        try:
            with self.assertRaises(PNGValidationError):
                validate_png(p)
        finally:
            p.unlink(missing_ok=True)


class PreprocessImageTest(TestCase):
    def test_returns_existing_file(self):
        p = _tmp_png()
        out = None
        try:
            out = preprocess_image(p)
            self.assertTrue(out.exists())
            self.assertTrue(out.suffix == '.png')
        finally:
            p.unlink(missing_ok=True)
            if out:
                out.unlink(missing_ok=True)

    def test_output_different_from_input(self):
        p = _tmp_png()
        out = None
        try:
            out = preprocess_image(p)
            self.assertNotEqual(p, out)
        finally:
            p.unlink(missing_ok=True)
            if out:
                out.unlink(missing_ok=True)


class RemoveBackgroundTest(TestCase):
    def test_fallback_pillow_returns_file(self):
        p = _tmp_png()
        out = None
        try:
            with patch.dict('sys.modules', {'rembg': None}):
                out = remove_background(p)
            self.assertTrue(out.exists())
        finally:
            p.unlink(missing_ok=True)
            if out:
                out.unlink(missing_ok=True)

    def test_rembg_called_when_available(self):
        p = _tmp_png()
        out = None
        mock_rembg = MagicMock()
        mock_rembg.remove.return_value = _make_tiny_png()
        try:
            with patch.dict('sys.modules', {'rembg': mock_rembg}):
                out = remove_background(p)
            mock_rembg.remove.assert_called_once()
            self.assertTrue(out.exists())
        finally:
            p.unlink(missing_ok=True)
            if out:
                out.unlink(missing_ok=True)


class VectorizeToSVGTest(TestCase):
    def test_vectorize_produces_svg_file(self):
        p = _tmp_png()
        out = None
        fake_svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
        # vtracer tourne en subprocess — simuler un succès via subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        try:
            def fake_run(cmd, **kwargs):
                # Écrire le faux SVG dans le fichier de sortie passé en argument
                svg_output = cmd[3]
                with open(svg_output, 'w') as f:
                    f.write(fake_svg)
                return mock_result
            with patch('conversions.services.png_processing.subprocess.run', side_effect=fake_run):
                out = vectorize_to_svg(p, n_colors=4)
            self.assertTrue(out.exists())
            self.assertEqual(out.suffix, '.svg')
            self.assertIn('<svg', out.read_text())
        finally:
            p.unlink(missing_ok=True)
            if out:
                out.unlink(missing_ok=True)

    def test_vectorize_failure_raises_runtime_error(self):
        p = _tmp_png()
        # VTracer échoue (SIGSEGV), potrace absent, Inkscape absent → RuntimeError
        mock_fail = MagicMock()
        mock_fail.returncode = -11
        mock_fail.stderr = b''
        try:
            with patch('conversions.services.png_processing.subprocess.run', return_value=mock_fail):
                with patch('conversions.services.png_processing.shutil.which', return_value=None):
                    with self.assertRaises(RuntimeError):
                        vectorize_to_svg(p, n_colors=4)
        finally:
            p.unlink(missing_ok=True)


class ColorToPBMTest(TestCase):
    def test_creates_pbm_file(self):
        mask = Image.new('1', (8, 8), 0)
        tmp = Path(tempfile.mktemp(suffix='.pbm'))
        try:
            _color_to_pbm(mask, tmp)
            self.assertTrue(tmp.exists())
            self.assertGreater(tmp.stat().st_size, 0)
            self.assertEqual(tmp.read_bytes()[:2], b'P4')
        finally:
            tmp.unlink(missing_ok=True)

    def test_pbm_dimensions_in_header(self):
        mask = Image.new('1', (12, 7), 255)
        tmp = Path(tempfile.mktemp(suffix='.pbm'))
        try:
            _color_to_pbm(mask, tmp)
            header = tmp.read_bytes().split(b'\n')
            self.assertIn(b'12 7', header[1])
        finally:
            tmp.unlink(missing_ok=True)


class ExtractPotracePathsTest(TestCase):
    def test_extracts_single_path(self):
        svg = (
            '<?xml version="1.0"?>'
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g><path d="M10 20 L30 40 Z"/></g>'
            '</svg>'
        )
        tmp = Path(tempfile.mktemp(suffix='.svg'))
        try:
            tmp.write_text(svg)
            paths = _extract_potrace_paths(tmp)
            self.assertEqual(len(paths), 1)
            self.assertIn('M10 20', paths[0])
        finally:
            tmp.unlink(missing_ok=True)

    def test_extracts_multiple_paths(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g><path d="M1 2 Z"/><path d="M3 4 Z"/></g>'
            '</svg>'
        )
        tmp = Path(tempfile.mktemp(suffix='.svg'))
        try:
            tmp.write_text(svg)
            self.assertEqual(len(_extract_potrace_paths(tmp)), 2)
        finally:
            tmp.unlink(missing_ok=True)

    def test_empty_svg_returns_empty_list(self):
        tmp = Path(tempfile.mktemp(suffix='.svg'))
        try:
            tmp.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
            self.assertEqual(_extract_potrace_paths(tmp), [])
        finally:
            tmp.unlink(missing_ok=True)

    def test_invalid_svg_returns_empty_list(self):
        tmp = Path(tempfile.mktemp(suffix='.svg'))
        try:
            tmp.write_text('not xml at all <<>>')
            self.assertEqual(_extract_potrace_paths(tmp), [])
        finally:
            tmp.unlink(missing_ok=True)


class BuildSVGTest(TestCase):
    def test_produces_valid_svg_with_viewbox(self):
        svg = _build_svg([(['M0 0 L10 10 Z'], '#ff0000'), (['M20 20 Z'], '#0000ff')], 100, 80)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn('viewBox="0 0 100 80"', svg)
        self.assertIn('#ff0000', svg)
        self.assertIn('#0000ff', svg)
        self.assertIn('M0 0 L10 10 Z', svg)

    def test_single_color(self):
        svg = _build_svg([(['M0 0 Z'], '#aabbcc')], 50, 50)
        self.assertIn('#aabbcc', svg)
        self.assertIn('width="50"', svg)
        self.assertIn('height="50"', svg)

    def test_yfip_transform_present(self):
        svg = _build_svg([(['M0 0 Z'], '#123456')], 40, 30)
        self.assertIn('translate(0,30) scale(1,-1)', svg)
        self.assertIn('stroke="none"', svg)


class VectorizePotraceTest(TestCase):
    def test_raises_when_potrace_missing(self):
        p = _tmp_png()
        tmp_svg = Path(tempfile.mktemp(suffix='.svg'))
        try:
            with patch('conversions.services.png_processing.shutil.which', return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    _vectorize_potrace(p, tmp_svg, n_colors=4)
            self.assertIn('potrace', str(ctx.exception))
        finally:
            p.unlink(missing_ok=True)
            tmp_svg.unlink(missing_ok=True)

    def test_produces_svg_with_mocked_potrace(self):
        p = _tmp_png(width=8, height=8)
        tmp_svg = Path(tempfile.mktemp(suffix='.svg'))
        fake_potrace_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="8pt" height="8pt">'
            '<g transform="translate(0,8) scale(1,-1)" fill="#000000" stroke="none">'
            '<path d="M1 1 L7 7 Z"/>'
            '</g></svg>'
        )

        def fake_run(cmd, **kwargs):
            out_idx = cmd.index('--output')
            Path(cmd[out_idx + 1]).write_text(fake_potrace_svg)
            m = MagicMock()
            m.returncode = 0
            return m

        try:
            with patch('conversions.services.png_processing.shutil.which', return_value='/usr/bin/potrace'):
                with patch('conversions.services.png_processing.subprocess.run', side_effect=fake_run):
                    result = _vectorize_potrace(p, tmp_svg, n_colors=4)
            self.assertTrue(result.exists())
            content = result.read_text()
            self.assertIn('<svg', content)
            self.assertIn('<path', content)
        finally:
            p.unlink(missing_ok=True)
            tmp_svg.unlink(missing_ok=True)
