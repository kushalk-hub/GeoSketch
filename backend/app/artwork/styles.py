"""Artwork styles and the renderer independent "art spec".

Both renderers (SVG and PNG) consume the same :class:`ArtSpec`, which guarantees
that the preview and the downloaded file always show the same drawing.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field

Point = tuple[float, float]


class ArtworkStyle(enum.StrEnum):
    MINIMAL = "minimal"
    NEON = "neon"
    GRADIENT = "gradient"
    POSTER = "poster"
    CUSTOM = "custom"


@dataclass
class StrokeLayer:
    """One polyline drawing instruction (a style may use several layers)."""

    segments: list[list[Point]]
    color: str
    width: float = 4.0
    opacity: float = 1.0
    blur: float = 0.0
    cap: str = "round"


@dataclass
class MarkerLayer:
    x: float
    y: float
    color: str
    radius: float = 9.0
    opacity: float = 1.0
    ring: bool = True


@dataclass
class TextLayer:
    text: str
    x: float
    y: float
    size: float
    color: str
    weight: str = "normal"  # "normal" | "bold"
    anchor: str = "start"  # "start" | "middle" | "end"
    opacity: float = 1.0
    letter_spacing: float = 0.0


@dataclass
class ArtSpec:
    width: int
    height: int
    background: str = "#ffffff"
    background_gradient: tuple[str, str] | None = None
    layers: list[StrokeLayer] = field(default_factory=list)
    markers: list[MarkerLayer] = field(default_factory=list)
    texts: list[TextLayer] = field(default_factory=list)
    frame: dict[str, object] | None = None
    watermark: str | None = None
    accent: str = "#38bdf8"


#: Presentation metadata surfaced to the frontend style picker.
STYLE_INFO: dict[str, dict[str, str]] = {
    ArtworkStyle.MINIMAL.value: {
        "label": "Minimal Route",
        "description": "Clean single-weight line on a paper white canvas.",
    },
    ArtworkStyle.NEON.value: {
        "label": "Neon Trail",
        "description": "Glowing trail on a deep night background.",
    },
    ArtworkStyle.GRADIENT.value: {
        "label": "Gradient Journey",
        "description": "Colour ramps along the path to show journey progression.",
    },
    ArtworkStyle.POSTER.value: {
        "label": "Artistic Poster",
        "description": "Framed route with title, distance, duration and date.",
    },
    ArtworkStyle.CUSTOM.value: {
        "label": "Custom Art",
        "description": "Your own background, route colour, line width and title.",
    },
}

#: Canvas defaults per style (portrait for the poster, landscape otherwise).
STYLE_CANVAS: dict[str, tuple[int, int]] = {
    ArtworkStyle.MINIMAL.value: (1600, 1000),
    ArtworkStyle.NEON.value: (1600, 1000),
    ArtworkStyle.GRADIENT.value: (1600, 1000),
    ArtworkStyle.POSTER.value: (1200, 1600),
    ArtworkStyle.CUSTOM.value: (1600, 1000),
}


def style_label(style: str) -> str:
    return STYLE_INFO.get(style, {}).get("label", style.title())


def all_styles() -> list[dict[str, object]]:
    """Style catalogue for ``GET /api/v1/artwork/styles``."""
    return [
        {
            "id": key,
            "label": info["label"],
            "description": info["description"],
            "default_width": STYLE_CANVAS.get(key, (1600, 1000))[0],
            "default_height": STYLE_CANVAS.get(key, (1600, 1000))[1],
        }
        for key, info in STYLE_INFO.items()
    ]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sequence_length(points: Sequence[Point]) -> float:
    total = 0.0
    for index in range(1, len(points)):
        total += (
            (points[index][0] - points[index - 1][0]) ** 2
            + (points[index][1] - points[index - 1][1]) ** 2
        ) ** 0.5
    return total
