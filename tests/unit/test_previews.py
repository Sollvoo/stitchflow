"""
Tests unitaires pour conversions/services/previews.py
"""
import pytest

from conversions.services.previews import (
    _filter_pes_v1_color_breaks,
    _is_near_white_thread,
)


# ---------------------------------------------------------------------------
# Helpers de test : thread simulé
# ---------------------------------------------------------------------------


class FakeThread:
    def __init__(self, r, g, b):
        self.color = (r << 16) | (g << 8) | b


def white():
    return FakeThread(255, 255, 255)


def almost_white():
    return FakeThread(241, 241, 241)  # juste au-dessus du seuil 240


def red():
    return FakeThread(255, 0, 0)


def blue():
    return FakeThread(0, 0, 255)


def dark_grey():
    return FakeThread(50, 50, 50)


# ---------------------------------------------------------------------------
# _is_near_white_thread
# ---------------------------------------------------------------------------


def test_is_near_white_true():
    assert _is_near_white_thread(white().color) is True
    assert _is_near_white_thread(almost_white().color) is True


def test_is_near_white_false():
    assert _is_near_white_thread(red().color) is False
    assert _is_near_white_thread(blue().color) is False
    assert _is_near_white_thread(dark_grey().color) is False
    # Exactement au seuil (240) — pas near-white (> 240 requis)
    exactly_240 = FakeThread(240, 240, 240)
    assert _is_near_white_thread(exactly_240.color) is False


# ---------------------------------------------------------------------------
# _filter_pes_v1_color_breaks
# ---------------------------------------------------------------------------


def test_filter_list_too_short():
    """Moins de 3 éléments → pas de filtrage."""
    threads = [white(), red()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert result == threads
    assert removed is False


def test_filter_white_between_two_colors():
    """Blanc entre deux non-blancs → COLOR_BREAK PES v1 → supprimé."""
    threads = [red(), white(), blue()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert len(result) == 2
    assert removed is True
    # Le blanc au milieu doit avoir été retiré
    colors = [t.color for t in result]
    assert white().color not in colors


def test_filter_white_at_start_kept():
    """Blanc au début → vrai fil blanc, conservé."""
    threads = [white(), red(), blue()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert len(result) == 3
    assert removed is False


def test_filter_white_at_end_kept():
    """Blanc à la fin → conservé."""
    threads = [red(), blue(), white()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert len(result) == 3
    assert removed is False


def test_filter_two_consecutive_whites_kept():
    """Deux blancs consécutifs → aucun n'est sandwiché entre deux non-blancs → conservés."""
    threads = [red(), white(), white(), blue()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    # Aucun des deux blancs n'est seul entre deux non-blancs
    # Blanc[1] : précédent = red (non-blanc), suivant = white (blanc) → suivant non-réel → conservé
    # Blanc[2] : précédent = white (blanc) → précédent non-réel → conservé
    assert removed is False
    assert len(result) == 4


def test_filter_multiple_separators():
    """Plusieurs separateurs PES v1 dans une longue séquence."""
    threads = [red(), white(), blue(), white(), dark_grey()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert removed is True
    assert len(result) == 3


def test_filter_all_whites_preserved():
    """Séquence de 3 blancs → aucun filtrage car pas de non-blanc adjacents."""
    threads = [white(), white(), white()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert len(result) == 3
    assert removed is False


def test_filter_no_whites():
    """Aucun blanc → aucun filtrage."""
    threads = [red(), blue(), dark_grey()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert result == threads
    assert removed is False


def test_filter_preserves_almost_white_true():
    """Un fil RGB(241,241,241) est near-white → traité comme blanc."""
    threads = [red(), almost_white(), blue()]
    result, removed = _filter_pes_v1_color_breaks(threads)
    assert removed is True
    assert len(result) == 2
