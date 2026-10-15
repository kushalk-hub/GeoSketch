"""High level artwork engine: GPS points in, SVG + PNG out."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.artwork.generator import ArtworkOptions, build_art_spec, default_padding
from app.artwork.geometry import ProcessedRoute, process_route
from app.artwork.renderers.png import render_png
from app.artwork.renderers.svg import render_svg
from app.artwork.styles import STYLE_CANVAS, STYLE_INFO, ArtSpec, ArtworkStyle
from app.core.config import Settings, get_settings
from app.core.errors import ValidationFailed


@dataclass
class RenderResult:
    style: str
    title: str
    width: int
    height: int
    svg: str
    png: bytes
    spec: ArtSpec
    processed: ProcessedRoute
    options: ArtworkOptions


def resolve_canvas(style: str, width: Optional[int], height: Optional[int]):
    """Canvas size for a style, honouring a single-axis override."""
    default_w, default_h = STYLE_CANVAS.get(style, (1600, 1000))
    if width and height:
        return int(width), int(height)
    if width:
        return int(width), max(200, int(round(width * default_h / default_w)))
    if height:
        return max(200, int(round(height * default_w / default_h))), int(height)
    return default_w, default_h


def render_route_art(
    points: Sequence,
    *,
    style: str | ArtworkStyle = ArtworkStyle.MINIMAL,
    options: Optional[ArtworkOptions] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    settings: Optional[Settings] = None,
    supersample: int = 2,
    png_export: bool = True,
) -> RenderResult:
    """Process ``points`` and render the artwork.

    ``png_export=False`` skips the (comparatively expensive) raster pass, which
    is what the live preview in the studio uses - the SVG alone is enough to
    preview, and the PNG is only produced when the user exports.
    """
    settings = settings or get_settings()
    style_value = style.value if isinstance(style, ArtworkStyle) else str(style)
    if style_value not in STYLE_INFO:
        raise ValidationFailed(
            f"unknown artwork style '{style_value}'",
            code="unknown_style",
            details={"allowed": sorted(STYLE_INFO.keys())},
        )

    options = options or ArtworkOptions()
    canvas_w, canvas_h = resolve_canvas(style_value, width, height)

    processed = process_route(
        points,
        width=canvas_w,
        height=canvas_h,
        padding=default_padding(style_value),
        min_point_distance_m=settings.min_point_distance_m,
        max_gap_seconds=settings.max_gap_seconds,
        max_plausible_speed_kmh=settings.max_plausible_speed_kmh,
    )

    if processed.is_empty:
        raise ValidationFailed(
            "this journey has no drawable GPS points yet",
            code="no_route_points",
            details={"source_points": processed.source_points, "excluded": processed.excluded_points},
        )

    spec = build_art_spec(processed, style_value, options)
    svg = render_svg(spec)
    png = render_png(spec, supersample=supersample) if png_export else b""

    return RenderResult(
        style=style_value,
        title=options.title,
        width=canvas_w,
        height=canvas_h,
        svg=svg,
        png=png,
        spec=spec,
        processed=processed,
        options=options,
    )
