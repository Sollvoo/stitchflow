from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from conversions.forms import PNGUploadForm

# Signature PNG valide (8 octets magic bytes + IHDR minimal)
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
VALID_PNG = PNG_MAGIC + b'\x00' * 100


def _form(content: bytes, name: str = 'test.png', extra: dict | None = None) -> PNGUploadForm:
    uploaded = SimpleUploadedFile(name, content, content_type='image/png')
    data = extra or {}
    return PNGUploadForm(data=data, files={'original_file': uploaded})


class PNGUploadFormTest(TestCase):
    def test_valid_png_accepted(self):
        form = _form(VALID_PNG, extra={'n_colors': '6'})
        self.assertTrue(form.is_valid(), form.errors)

    def test_file_renamed_to_uuid_hex(self):
        form = _form(VALID_PNG, extra={'n_colors': '6'})
        self.assertTrue(form.is_valid())
        filename = form.cleaned_data['original_file'].name
        stem = filename.replace('.png', '')
        self.assertEqual(len(stem), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in stem))

    def test_invalid_extension_rejected(self):
        # .gif n'est pas accepté (seuls .png/.jpg/.jpeg/.webp le sont)
        form = _form(VALID_PNG, name='test.gif')
        self.assertFalse(form.is_valid())
        self.assertIn('original_file', form.errors)

    def test_jpeg_extension_accepted(self):
        jpeg_magic = b'\xff\xd8\xff' + b'\x00' * 100
        form = _form(jpeg_magic, name='test.jpg', extra={'n_colors': '6'})
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.source_format, 'jpeg')

    def test_webp_extension_accepted(self):
        webp_magic = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 80
        form = _form(webp_magic, name='test.webp', extra={'n_colors': '6'})
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.source_format, 'webp')

    def test_wrong_magic_bytes_rejected(self):
        form = _form(b'NOTAPNG' + b'\x00' * 50)
        self.assertFalse(form.is_valid())
        self.assertIn('original_file', form.errors)

    def test_n_colors_below_min_rejected(self):
        form = _form(VALID_PNG, extra={'n_colors': '1'})
        self.assertFalse(form.is_valid())
        self.assertIn('n_colors', form.errors)

    def test_n_colors_above_max_rejected(self):
        form = _form(VALID_PNG, extra={'n_colors': '17'})
        self.assertFalse(form.is_valid())
        self.assertIn('n_colors', form.errors)

    def test_n_colors_at_bounds_accepted(self):
        for val in ('2', '16'):
            form = _form(VALID_PNG, extra={'n_colors': val})
            self.assertTrue(form.is_valid(), f"n_colors={val} devrait être valide")

    def test_n_colors_optional(self):
        form = _form(VALID_PNG)
        self.assertTrue(form.is_valid(), form.errors)

    def test_oversized_file_rejected(self):
        big = PNG_MAGIC + b'\x00' * (21 * 1024 * 1024)
        form = _form(big)
        self.assertFalse(form.is_valid())
        self.assertIn('original_file', form.errors)
