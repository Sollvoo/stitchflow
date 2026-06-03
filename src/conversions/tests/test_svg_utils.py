import tempfile
from pathlib import Path

from django.test import TestCase

from conversions.services.svg_utils import get_svg_dimensions_mm, scale_svg_to_width_mm

SVG_WITH_MM = '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="80mm"><rect fill="red" width="50" height="40"/></svg>'
SVG_WITH_PX = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect fill="red" width="50" height="40"/></svg>'
SVG_WITH_VIEWBOX_ONLY = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect fill="red" width="200" height="150"/></svg>'
SVG_PERCENT_WIDTH = '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><rect fill="red" width="50" height="40"/></svg>'


def _write_svg(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w', encoding='utf-8')
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


class GetSvgDimensionsTest(TestCase):
    def test_mm_dimensions_parsed(self):
        path = _write_svg(SVG_WITH_MM)
        try:
            w, h = get_svg_dimensions_mm(path)
            self.assertAlmostEqual(w, 100.0)
            self.assertAlmostEqual(h, 80.0)
        finally:
            path.unlink(missing_ok=True)

    def test_px_dimensions_converted(self):
        path = _write_svg(SVG_WITH_PX)
        try:
            w, h = get_svg_dimensions_mm(path)
            # 200px × 100px → en mm (200 × 25.4/96 ≈ 52.9mm)
            self.assertIsNotNone(w)
            self.assertIsNotNone(h)
            self.assertGreater(w, 0)
        finally:
            path.unlink(missing_ok=True)

    def test_viewbox_only_fallback(self):
        path = _write_svg(SVG_WITH_VIEWBOX_ONLY)
        try:
            w, h = get_svg_dimensions_mm(path)
            self.assertIsNotNone(w)
            self.assertIsNotNone(h)
        finally:
            path.unlink(missing_ok=True)

    def test_percent_width_returns_none(self):
        path = _write_svg(SVG_PERCENT_WIDTH)
        try:
            w, h = get_svg_dimensions_mm(path)
            # Pas de viewBox non plus → None
            self.assertIsNone(w)
            self.assertIsNone(h)
        finally:
            path.unlink(missing_ok=True)


class ScaleSvgToWidthTest(TestCase):
    def test_scale_preserves_aspect_ratio(self):
        path = _write_svg(SVG_WITH_MM)  # 100mm × 80mm → ratio 0.8
        scaled = None
        try:
            scaled = scale_svg_to_width_mm(path, 200)
            w, h = get_svg_dimensions_mm(scaled)
            self.assertAlmostEqual(w, 200.0)
            self.assertAlmostEqual(h, 160.0, delta=1.0)  # 200 × 0.8 = 160
        finally:
            path.unlink(missing_ok=True)
            if scaled:
                scaled.unlink(missing_ok=True)

    def test_scaled_file_is_valid_svg(self):
        path = _write_svg(SVG_WITH_MM)
        scaled = None
        try:
            scaled = scale_svg_to_width_mm(path, 50)
            self.assertTrue(scaled.exists())
            content = scaled.read_text(encoding='utf-8')
            self.assertIn('<svg', content)
            self.assertIn('50mm', content)
        finally:
            path.unlink(missing_ok=True)
            if scaled:
                scaled.unlink(missing_ok=True)

    def test_scale_svg_without_viewbox(self):
        path = _write_svg(SVG_WITH_PX)
        scaled = None
        try:
            scaled = scale_svg_to_width_mm(path, 100)
            self.assertTrue(scaled.exists())
            content = scaled.read_text(encoding='utf-8')
            self.assertIn('viewBox', content)  # viewBox ajouté automatiquement
            self.assertIn('100mm', content)
        finally:
            path.unlink(missing_ok=True)
            if scaled:
                scaled.unlink(missing_ok=True)
