"""Colour utilities used by the artwork styles."""

from __future__ import annotations

import re
from collections.abc import Sequence

RGB = tuple[int, int, int]

_HEX_RE = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

DEFAULT_ACCENT = "#38BDF8"


def normalize_hex(value: str | None, fallback: str = DEFAULT_ACCENT) -> str:
    """Return a ``#rrggbb`` string, falling back when the input is invalid."""
    if not value or not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        return fallback
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    return "#" + text.lower()


def hex_to_rgb(value: str) -> RGB:
    text = normalize_hex(value).lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def rgb_to_hex(rgb: Sequence[float]) -> str:
    channels = [max(0, min(255, round(channel))) for channel in rgb[:3]]
    return "#{:02x}{:02x}{:02x}".format(*channels)


def mix(color_a: str, color_b: str, t: float) -> str:
    """Linear interpolation between two hex colours (``t`` in 0..1)."""
    t = max(0.0, min(1.0, t))
    a = hex_to_rgb(color_a)
    b = hex_to_rgb(color_b)
    return rgb_to_hex([a[i] + (b[i] - a[i]) * t for i in range(3)])


def ramp(stops: Sequence[str], t: float) -> str:
    """Sample a multi-stop colour ramp at position ``t`` (0..1)."""
    if not stops:
        return DEFAULT_ACCENT
    if len(stops) == 1:
        return normalize_hex(stops[0])
    t = max(0.0, min(1.0, t))
    scaled = t * (len(stops) - 1)
    index = min(len(stops) - 2, int(scaled))
    local_t = scaled - index
    return mix(stops[index], stops[index + 1], local_t)


def lighten(color: str, amount: float = 0.25) -> str:
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float = 0.25) -> str:
    return mix(color, "#000000", amount)


def is_dark(color: str) -> bool:
    """Perceived luminance test, used to pick readable text colours."""
    r, g, b = hex_to_rgb(color)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return luminance < 0.55


def readable_on(background: str) -> str:
    return "#0b1220" if not is_dark(background) else "#f8fafc"


def default_gradient_stops() -> list[str]:
    return ["#22d3ee", "#818cf8", "#f472b6"]
