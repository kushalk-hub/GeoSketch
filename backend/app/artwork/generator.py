"""Style builders: turn a :class:`ProcessedRoute` into an :class:`ArtSpec`.

Every style is built from the same processed route, so switching styles never
changes the geometry - only the presentation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.artwork.colors import (
    DEFAULT_ACCENT,
    default_gradient_stops,
    lighten,
    mix,
    normalize_hex,
    ramp,
    readable_on,
)
from app.artwork.geometry import ProcessedRoute, subdivide_route
from app.artwork.styles import (
    ArtSpec,
    ArtworkStyle,
    MarkerLayer,
    StrokeLayer,
    TextLayer,
)
from app.utils.formatting import format_date, format_distance, format_duration

#: Named colour ramps selectable from the studio.
PALETTES: dict[str, list[str]] = {
    "aurora": ["#22d3ee", "#818cf8", "#f472b6"],
    "sunset": ["#fbbf24", "#fb7185", "#7c3aed"],
    "ocean": ["#0ea5e9", "#22d3ee", "#a7f3d0"],
    "forest": ["#a3e635", "#22c55e", "#0f766e"],
    "magma": ["#fde047", "#f97316", "#dc2626"],
    "mono": ["#e2e8f0", "#94a3b8", "#475569"],
}

START_COLOR = "#22c55e"
END_COLOR = "#ef4444"


@dataclass
class ArtworkOptions:
    """User supplied customisation, already validated by the API schema."""

    title: str = "Route artwork"
    subtitle: str | None = None
    background: str | None = None
    route_color: str | None = None
    accent_color: str | None = None
    line_width: float | None = None
    glow: bool | None = None
    show_start_marker: bool = True
    show_end_marker: bool = True
    palette: str | None = None

    def palette_stops(self) -> list[str]:
        if self.palette and self.palette.lower() in PALETTES:
            return PALETTES[self.palette.lower()]
        stops = default_gradient_stops()
        if self.route_color:
            stops = [
                normalize_hex(self.route_color, stops[0]),
                normalize_hex(self.accent_color, stops[1]),
                normalize_hex(self.route_color, stops[0]),
            ]
        return stops


def _fit_font_size(
    text: str, desired: float, max_width: float, minimum: float = 18.0, factor: float = 0.58
) -> float:
    """Shrink a font size so long titles stay inside the canvas.

    ``factor`` is the average glyph width relative to the font size for a bold
    humanist sans face - accurate enough to avoid overflowing artwork, and it
    keeps the SVG and PNG renderers in agreement.
    """
    if not text or max_width <= 0:
        return desired
    estimated = len(text) * desired * factor
    if estimated <= max_width:
        return desired
    return max(minimum, desired * max_width / estimated)


def _title_block(spec: ArtSpec, options: ArtworkOptions, route: ProcessedRoute) -> None:
    """Small caption used by every non-poster style."""
    background = options.background or spec.background
    text_color = readable_on(background)
    title = options.title.upper()
    spec.texts.append(
        TextLayer(
            text=title,
            x=48,
            y=64,
            size=_fit_font_size(title, 30.0, spec.width - 220.0, minimum=16.0),
            color=text_color,
            weight="bold",
            letter_spacing=2.0,
            opacity=0.9,
        )
    )
    spec.texts.append(
        TextLayer(
            text=format_distance(route.distance_m),
            x=48,
            y=98,
            size=22,
            color=text_color,
            opacity=0.65,
        )
    )


def _watermark(spec: ArtSpec, options: ArtworkOptions) -> None:
    text_color = readable_on(options.background or spec.background)
    spec.texts.append(
        TextLayer(
            text="GeoSketch",
            x=spec.width - 48,
            y=spec.height - 40,
            size=20,
            color=text_color,
            anchor="end",
            letter_spacing=3.0,
            opacity=0.5,
        )
    )


def _markers(
    spec: ArtSpec, route: ProcessedRoute, options: ArtworkOptions, start: str, end: str
) -> None:
    radius = max(7.0, min(14.0, spec.width / 160.0))
    if options.show_start_marker and route.start_point:
        spec.markers.append(
            MarkerLayer(x=route.start_point[0], y=route.start_point[1], color=start, radius=radius)
        )
    if options.show_end_marker and route.end_point:
        spec.markers.append(
            MarkerLayer(x=route.end_point[0], y=route.end_point[1], color=end, radius=radius, ring=False)
        )


def _build_minimal(route: ProcessedRoute, options: ArtworkOptions) -> ArtSpec:
    background = normalize_hex(options.background, "#f6f5f2")
    route_color = normalize_hex(options.route_color, "#111827")
    spec = ArtSpec(width=route.width, height=route.height, background=background, accent=route_color)
    spec.layers.append(
        StrokeLayer(
            segments=route.segments,
            color=route_color,
            width=options.line_width or 7.0,
            opacity=0.95,
        )
    )
    _markers(spec, route, options, START_COLOR, END_COLOR)
    _title_block(spec, options, route)
    _watermark(spec, options)
    return spec


def _build_neon(route: ProcessedRoute, options: ArtworkOptions) -> ArtSpec:
    background = normalize_hex(options.background, "#05070d")
    core = normalize_hex(options.route_color, "#22d3ee")
    width = options.line_width or 5.0
    spec = ArtSpec(width=route.width, height=route.height, background=background, accent=core)

    # Three stacked copies of the same geometry: wide + faint, mid + brighter,
    # then a near-white core, which is what produces the "glow" without needing
    # an expensive post-processing pass on the SVG side.
    spec.layers.append(
        StrokeLayer(segments=route.segments, color=core, width=width * 6.0, opacity=0.10, blur=18.0)
    )
    spec.layers.append(
        StrokeLayer(segments=route.segments, color=core, width=width * 2.8, opacity=0.22, blur=8.0)
    )
    spec.layers.append(
        StrokeLayer(segments=route.segments, color=core, width=width * 1.5, opacity=0.55, blur=2.5)
    )
    spec.layers.append(
        StrokeLayer(
            segments=route.segments, color=lighten(core, 0.55), width=width, opacity=1.0
        )
    )
    _markers(spec, route, options, "#4ade80", "#fb7185")
    _title_block(spec, options, route)
    _watermark(spec, options)
    return spec


def _build_gradient(route: ProcessedRoute, options: ArtworkOptions) -> ArtSpec:
    background = normalize_hex(options.background, "#0b1020")
    stops = options.palette_stops()
    spec = ArtSpec(
        width=route.width, height=route.height, background=background, accent=stops[0]
    )

    width = options.line_width or 8.0
    glow_stops = [(chunk, position) for chunk, position in subdivide_route(route.segments, 90)]
    if glow_stops:
        # Soft underlay so the ramp reads clearly on a dark background.
        spec.layers.append(
            StrokeLayer(
                segments=[chunk for chunk, _ in glow_stops],
                color=mix(stops[0], stops[-1], 0.5),
                width=width * 2.4,
                opacity=0.20,
                blur=10.0,
            )
        )
    for chunk, position in subdivide_route(route.segments, 140):
        spec.layers.append(
            StrokeLayer(
                segments=[chunk],
                color=ramp(stops, position),
                width=width,
                opacity=1.0,
            )
        )
    _markers(spec, route, options, START_COLOR, END_COLOR)
    _title_block(spec, options, route)
    _watermark(spec, options)
    return spec


def _build_poster(route: ProcessedRoute, options: ArtworkOptions) -> ArtSpec:
    background = normalize_hex(options.background, "#0b1120")
    accent = normalize_hex(options.route_color, DEFAULT_ACCENT)
    ink = readable_on(background)
    spec = ArtSpec(
        width=route.width,
        height=route.height,
        background=background,
        background_gradient=(mix(background, "#ffffff", 0.06), mix(background, "#000000", 0.35)),
        accent=accent,
    )

    margin = 56.0
    spec.frame = {
        "x": margin,
        "y": margin,
        "width": spec.width - 2 * margin,
        "height": spec.height - 2 * margin,
        "color": accent,
        "opacity": 0.35,
        "radius": 18.0,
    }

    width = options.line_width or 8.0
    spec.layers.append(
        StrokeLayer(segments=route.segments, color=accent, width=width * 2.6, opacity=0.16, blur=12.0)
    )
    spec.layers.append(
        StrokeLayer(segments=route.segments, color=accent, width=width, opacity=1.0)
    )
    _markers(spec, route, options, START_COLOR, END_COLOR)

    # Poster typography: eyebrow, title, rule, statistics footer.
    center = spec.width / 2.0
    spec.texts.append(
        TextLayer(
            text="GEOSKETCH  ·  GPS ROUTE ART",
            x=center,
            y=132,
            size=20,
            color=accent,
            anchor="middle",
            letter_spacing=4.0,
            opacity=0.9,
        )
    )
    poster_title = options.title.upper()[:48]
    spec.texts.append(
        TextLayer(
            text=poster_title,
            x=center,
            y=196,
            size=_fit_font_size(poster_title, 52.0, spec.width - 2 * margin - 60.0),
            color=ink,
            weight="bold",
            anchor="middle",
        )
    )
    spec.texts.append(
        TextLayer(
            text=f"{format_distance(route.distance_m)}   ·   "
            f"{format_duration(route.duration_seconds)}   ·   "
            f"{format_date(route.started_at)}",
            x=center,
            y=spec.height - 150,
            size=26,
            color=ink,
            anchor="middle",
            opacity=0.85,
        )
    )
    if options.subtitle:
        subtitle = options.subtitle[:80]
        spec.texts.append(
            TextLayer(
                text=subtitle,
                x=center,
                y=spec.height - 110,
                size=_fit_font_size(subtitle, 20.0, spec.width - 2 * margin - 40.0, minimum=14.0),
                color=ink,
                anchor="middle",
                opacity=0.6,
            )
        )
    spec.texts.append(
        TextLayer(
            text="Distance and duration are GPS estimates",
            x=center,
            y=spec.height - 74,
            size=16,
            color=ink,
            anchor="middle",
            opacity=0.45,
        )
    )
    return spec


def _build_custom(route: ProcessedRoute, options: ArtworkOptions) -> ArtSpec:
    background = normalize_hex(options.background, "#0b1120")
    route_color = normalize_hex(options.route_color, DEFAULT_ACCENT)
    width = options.line_width or 6.0
    spec = ArtSpec(
        width=route.width, height=route.height, background=background, accent=route_color
    )

    glow = True if options.glow is None else bool(options.glow)
    if glow:
        spec.layers.append(
            StrokeLayer(
                segments=route.segments,
                color=route_color,
                width=width * 3.2,
                opacity=0.18,
                blur=12.0,
            )
        )
    spec.layers.append(
        StrokeLayer(segments=route.segments, color=route_color, width=width, opacity=1.0)
    )
    _markers(
        spec,
        route,
        options,
        normalize_hex(options.accent_color, "#4ade80"),
        normalize_hex(options.accent_color, "#f87171"),
    )
    _title_block(spec, options, route)
    _watermark(spec, options)
    return spec


_BUILDERS = {
    ArtworkStyle.MINIMAL.value: _build_minimal,
    ArtworkStyle.NEON.value: _build_neon,
    ArtworkStyle.GRADIENT.value: _build_gradient,
    ArtworkStyle.POSTER.value: _build_poster,
    ArtworkStyle.CUSTOM.value: _build_custom,
}


def build_art_spec(
    route: ProcessedRoute, style: str, options: ArtworkOptions | None = None
) -> ArtSpec:
    """Build the renderer independent spec for ``style``."""
    options = options or ArtworkOptions()
    builder = _BUILDERS.get(style)
    if builder is None:
        raise ValueError(f"unknown artwork style: {style}")
    return builder(route, options)


def default_padding(style: str) -> float:
    """The poster needs more breathing room than the line-art styles."""
    return 150.0 if style == ArtworkStyle.POSTER.value else 72.0
