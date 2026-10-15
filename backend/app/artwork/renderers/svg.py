"""SVG renderer.

The SVG is emitted directly as text - no templating dependency - which keeps the
export dependency free and produces small, scalable, editable files.
"""

from __future__ import annotations

from app.artwork.colors import normalize_hex
from app.artwork.styles import ArtSpec, StrokeLayer

FONT_STACK = (
    "'Segoe UI', 'Inter', 'Helvetica Neue', Arial, 'DejaVu Sans', sans-serif"
)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt(value: float) -> str:
    """Compact coordinate formatting keeps the file size down."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _points(segment) -> str:
    return " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in segment)


def _layer_markup(layer: StrokeLayer, index: int) -> list[str]:
    attributes = [
        f'stroke="{normalize_hex(layer.color)}"',
        f'stroke-width="{_fmt(layer.width)}"',
        'fill="none"',
        'stroke-linecap="round"',
        'stroke-linejoin="round"',
    ]
    if layer.opacity < 1.0:
        attributes.append(f'opacity="{layer.opacity:.3f}"')
    if layer.blur > 0:
        attributes.append(f'filter="url(#blur{index})"')

    lines = [f"  <g {' '.join(attributes)}>"]
    for segment in layer.segments:
        if len(segment) == 1:
            x, y = segment[0]
            radius = max(0.5, layer.width / 2.0)
            lines.append(f'    <circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="{_fmt(radius)}"/>')
        elif len(segment) >= 2:
            lines.append(f'    <polyline points="{_points(segment)}"/>')
    lines.append("  </g>")
    return lines


def render_svg(spec: ArtSpec) -> str:
    """Serialise an :class:`ArtSpec` to an SVG document."""
    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{spec.width}" '
        f'height="{spec.height}" viewBox="0 0 {spec.width} {spec.height}" '
        f'role="img" aria-label="GPS route artwork">'
    )

    # --- defs ---------------------------------------------------------------
    lines.append("  <defs>")
    if spec.background_gradient:
        top, bottom = spec.background_gradient
        lines.append(
            '    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{normalize_hex(top)}"/>'
            f'<stop offset="100%" stop-color="{normalize_hex(bottom)}"/>'
            "</linearGradient>"
        )
    for index, layer in enumerate(spec.layers):
        if layer.blur > 0:
            lines.append(
                f'    <filter id="blur{index}" x="-25%" y="-25%" width="150%" height="150%">'
                f'<feGaussianBlur stdDeviation="{_fmt(layer.blur)}"/>'
                "</filter>"
            )
    lines.append("  </defs>")

    # --- background ---------------------------------------------------------
    fill = "url(#bg)" if spec.background_gradient else normalize_hex(spec.background)
    lines.append(
        f'  <rect x="0" y="0" width="{spec.width}" height="{spec.height}" fill="{fill}"/>'
    )

    # --- frame (poster) -----------------------------------------------------
    if spec.frame:
        frame = spec.frame
        lines.append(
            f'  <rect x="{_fmt(float(frame["x"]))}" y="{_fmt(float(frame["y"]))}" '
            f'width="{_fmt(float(frame["width"]))}" height="{_fmt(float(frame["height"]))}" '
            f'rx="{_fmt(float(frame.get("radius", 0)))}" fill="none" '
            f'stroke="{normalize_hex(str(frame.get("color")))}" '
            f'stroke-width="2" opacity="{float(frame.get("opacity", 1.0)):.2f}"/>'
        )

    # --- route layers -------------------------------------------------------
    for index, layer in enumerate(spec.layers):
        lines.extend(_layer_markup(layer, index))

    # --- markers ------------------------------------------------------------
    for marker in spec.markers:
        lines.append(
            f'  <circle cx="{_fmt(marker.x)}" cy="{_fmt(marker.y)}" r="{_fmt(marker.radius)}" '
            f'fill="{normalize_hex(marker.color)}" opacity="{marker.opacity:.2f}"'
            + (
                ' stroke="#ffffff" stroke-width="3" stroke-opacity="0.85"'
                if marker.ring
                else ""
            )
            + "/>"
        )

    # --- text ---------------------------------------------------------------
    for text in spec.texts:
        letter_spacing = (
            f' letter-spacing="{_fmt(text.letter_spacing)}"' if text.letter_spacing else ""
        )
        lines.append(
            f'  <text x="{_fmt(text.x)}" y="{_fmt(text.y)}" font-family="{FONT_STACK}" '
            f'font-size="{_fmt(text.size)}" font-weight="{text.weight}" '
            f'fill="{normalize_hex(text.color)}" text-anchor="{text.anchor}"'
            f' opacity="{text.opacity:.2f}"{letter_spacing}>{_escape(text.text)}</text>'
        )

    if spec.watermark:
        lines.append(
            f'  <text x="{_fmt(spec.width - 48)}" y="{_fmt(spec.height - 40)}" '
            f'font-family="{FONT_STACK}" font-size="20" fill="{normalize_hex(spec.accent)}" '
            f'text-anchor="end" opacity="0.5">{_escape(spec.watermark)}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"
