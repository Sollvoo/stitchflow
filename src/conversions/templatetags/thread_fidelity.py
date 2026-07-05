from django import template

from conversions.services.thread_color import hex_delta_e

register = template.Library()


@register.filter
def delta_e(hex1: str, hex2: str) -> float:
    """Distance perceptuelle CIE Lab entre deux couleurs hex '#rrggbb'."""
    if not hex1 or not hex2:
        return 0.0
    return round(hex_delta_e(hex1, hex2), 1)
