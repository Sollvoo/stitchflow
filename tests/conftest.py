"""
Fixtures partagées pour la suite pytest StitchFlow.
"""
import sys
from pathlib import Path

import pytest

# Ajouter le répertoire tests/ au sys.path pour que `from factories import ...` fonctionne
sys.path.insert(0, str(Path(__file__).parent))


# ---------------------------------------------------------------------------
# Constantes SVG de test
# ---------------------------------------------------------------------------

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'

MULTI_COLOR_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/>
<path fill="#00ff00" d="M20 0 L30 0 L30 10 Z"/>
<path fill="#0000ff" d="M40 0 L50 0 L50 10 Z"/>
</svg>"""

ZERO_WIDTH_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="0mm" height="100mm" viewBox="0 0 0 100"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'

NO_BRODABLE_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><path fill="none" stroke="none" d="M0 0 L10 0 L10 10 Z"/></svg>'

STYLE_FILL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><path style="fill:#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'

XXE_SVG = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z">&xxe;</path>
</svg>"""

BILLION_LAUGHS_SVG = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ff0000" d="&lol3;"/></svg>"""

MALFORMED_XML = b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ff0000" UNCLOSED'

NOT_SVG_ROOT = b'<?xml version="1.0"?><root><child/></root>'

NAMESPACE_SVG = b'<svg:svg xmlns:svg="http://www.w3.org/2000/svg" width="100mm" height="100mm"><svg:path fill="#ff0000" d="M0 0 L10 0"/></svg:svg>'


# ---------------------------------------------------------------------------
# Override global : staticfiles simple storage (pas de manifest compilé en test)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def use_simple_static_files(settings):
    """Remplace ManifestStaticFilesStorage par StaticFilesStorage en test."""
    try:
        storages = dict(settings.STORAGES)
        storages["staticfiles"] = {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        }
        settings.STORAGES = storages
    except AttributeError:
        settings.STATICFILES_STORAGE = (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
        )


# ---------------------------------------------------------------------------
# Fixtures fichiers temporaires
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_svg_file(tmp_path):
    """Retourne un chemin vers un fichier SVG minimal valide."""
    p = tmp_path / "test.svg"
    p.write_bytes(MINIMAL_SVG)
    return p


@pytest.fixture
def tmp_multi_color_svg(tmp_path):
    p = tmp_path / "multi.svg"
    p.write_bytes(MULTI_COLOR_SVG)
    return p


@pytest.fixture
def tmp_xxe_svg(tmp_path):
    p = tmp_path / "xxe.svg"
    p.write_bytes(XXE_SVG)
    return p


@pytest.fixture
def tmp_billion_laughs_svg(tmp_path):
    p = tmp_path / "billion.svg"
    p.write_bytes(BILLION_LAUGHS_SVG)
    return p


@pytest.fixture
def tmp_zero_width_svg(tmp_path):
    p = tmp_path / "zero.svg"
    p.write_bytes(ZERO_WIDTH_SVG)
    return p


@pytest.fixture
def tmp_no_brodable_svg(tmp_path):
    p = tmp_path / "nobrodable.svg"
    p.write_bytes(NO_BRODABLE_SVG)
    return p


@pytest.fixture
def tmp_style_fill_svg(tmp_path):
    p = tmp_path / "stylefill.svg"
    p.write_bytes(STYLE_FILL_SVG)
    return p
