from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from conversions.forms import SVGUploadForm

VALID_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="red" width="50" height="50"/></svg>'


class SVGUploadFormTest(TestCase):
    def _form(self, content: bytes, name: str = 'test.svg') -> SVGUploadForm:
        uploaded = SimpleUploadedFile(name, content, content_type='image/svg+xml')
        return SVGUploadForm(files={'original_file': uploaded})

    def test_valid_svg_accepted(self):
        form = self._form(VALID_SVG)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_svg_renamed_to_uuid_hex(self):
        form = self._form(VALID_SVG)
        self.assertTrue(form.is_valid())
        filename = form.cleaned_data['original_file'].name
        stem = filename.replace('.svg', '')
        self.assertEqual(len(stem), 32)  # UUID hex = 32 chars
        self.assertTrue(all(c in '0123456789abcdef' for c in stem))

    def test_invalid_extension_rejected(self):
        form = self._form(VALID_SVG, name='test.png')
        self.assertFalse(form.is_valid())
        self.assertIn('original_file', form.errors)

    def test_oversized_file_rejected(self):
        big_content = b'<svg>' + b'x' * (11 * 1024 * 1024) + b'</svg>'
        form = self._form(big_content)
        self.assertFalse(form.is_valid())
        self.assertIn('original_file', form.errors)

    def test_non_svg_content_rejected(self):
        form = self._form(b'%PDF-1.4 this is not an svg')
        self.assertFalse(form.is_valid())
        self.assertIn('original_file', form.errors)

    def test_xml_with_svg_header_accepted(self):
        xml_svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        form = self._form(xml_svg)
        self.assertTrue(form.is_valid(), form.errors)
