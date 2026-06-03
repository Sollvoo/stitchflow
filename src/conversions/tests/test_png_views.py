import struct
import zlib
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


def _make_tiny_png(width: int = 4, height: int = 4) -> bytes:
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


class AnalyzePNGViewTest(TestCase):
    def test_valid_png_returns_suggestions_fragment(self):
        png_data = _make_tiny_png(width=8, height=8)
        response = self.client.post(
            reverse('conversions:analyze_png'),
            {'original_file': SimpleUploadedFile('test.png', png_data, content_type='image/png')},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'png-suggestions', response.content)

    def test_no_file_returns_empty(self):
        response = self.client.post(reverse('conversions:analyze_png'), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_invalid_file_returns_empty(self):
        response = self.client.post(
            reverse('conversions:analyze_png'),
            {'original_file': SimpleUploadedFile('test.png', b'not a png', content_type='image/png')},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_detects_n_colors_in_response(self):
        png_data = _make_tiny_png(width=8, height=8)
        response = self.client.post(
            reverse('conversions:analyze_png'),
            {'original_file': SimpleUploadedFile('test.png', png_data, content_type='image/png')},
        )
        self.assertIn(b'couleur', response.content)
