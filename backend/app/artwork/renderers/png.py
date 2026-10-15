"""PNG renderer built on Pillow.

The drawing is supersampled (rendered at 2x and downscaled with LANCZOS) which
gives clean anti-aliased edges, matching the quality of the SVG export.

Performance notes: layers that are fully opaque and unblurred are batched into a
single overlay, so the 140 colour chunks of the gradient style cost one alpha
composite instead of 140.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Sequence, Tuple  # noqa: F401

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.artwork.colors import hex_to_rgb, normalize_hex
from app.artwork.styles import ArtSpec, StrokeLayer

#: Supersampling factor (2 keeps 1600x1000 canvases well under a second).
SUPERSAMPLE = 2

_FONT_REGULAR = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/SegoeUI.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
_FONT_BOLD = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/SegoeUI-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

_TEXT_ANCHORS = {"start": "ls", "middle": "ms", "end": "rs"}


@lru_cache(maxsize=64)
def _load_font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_BOLD if bold else _FONT_REGULAR:
        try:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        except OSError:  # pragma: no cover - unreadable font file
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _rgba(color: str, opacity: float) -> Tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(color)
    return (r, g, b, max(0, min(255, int(round(opacity * 255)))))


def _scaled(points: Sequence[Tuple[float, float]], factor: float) -> List[Tuple[float, float]]:
    return [(x * factor, y * factor) for x, y in points]


def _draw_layer(draw: ImageDraw.ImageDraw, layer: StrokeLayer, factor: float) -> None:
    width = max(1, int(round(layer.width * factor)))
    fill = _rgba(layer.color, 1.0)
    radius = layer.width * factor / 2.0
    for segment in layer.segments:
        if len(segment) == 1:
            x, y = segment[0][0] * factor, segment[0][1] * factor
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)
            continue
        if len(segment) < 2:
            continue
        draw.line(_scaled(segment, factor), fill=fill, width=width, joint="curve")
        if layer.cap == "round":
            # Pillow has no line caps: add them manually so joins look right.
            for x, y in (segment[0], segment[-1]):
                cx, cy = x * factor, y * factor
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fill)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: Tuple[float, float],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    anchor: str,
    letter_spacing: float,
) -> None:
    if letter_spacing <= 0:
        draw.text(xy, text, font=font, fill=fill, anchor=_TEXT_ANCHORS.get(anchor, "ls"))
        return

    widths = [draw.textlength(char, font=font) for char in text]
    spacing = letter_spacing
    total = sum(widths) + spacing * max(0, len(text) - 1)
    x, y = xy
    if anchor == "middle":
        x -= total / 2.0
    elif anchor == "end":
        x -= total
    for char, char_width in zip(text, widths):
        draw.text((x, y), char, font=font, fill=fill, anchor="ls")
        x += char_width + spacing


def render_png(spec: ArtSpec, supersample: int = SUPERSAMPLE) -> bytes:  # noqa: C901
    """Render an :class:`ArtSpec` to PNG bytes."""
    factor = max(1, int(supersample))
    canvas_size = (spec.width * factor, spec.height * factor)

    if spec.background_gradient:
        top = hex_to_rgb(spec.background_gradient[0])
        bottom = hex_to_rgb(spec.background_gradient[1])
        gradient = Image.linear_gradient("L").resize(canvas_size, Image.BILINEAR)
        base = ImageOps.colorize(gradient, black=top, white=bottom).convert("RGBA")
    else:
        base = Image.new("RGBA", canvas_size, _rgba(spec.background, 1.0))

    if spec.frame:
        frame = spec.frame
        overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        pen = ImageDraw.Draw(overlay)
        pen.rounded_rectangle(
            [
                float(frame["x"]) * factor,
                float(frame["y"]) * factor,
                (float(frame["x"]) + float(frame["width"])) * factor,
                (float(frame["y"]) + float(frame["height"])) * factor,
            ],
            radius=float(frame.get("radius", 0)) * factor,
            outline=_rgba(str(frame.get("color")), float(frame.get("opacity", 1.0))),
            width=max(1, int(2 * factor)),
        )
        base = Image.alpha_composite(base, overlay)

    # --- route layers, batching the cheap (opaque, unblurred) ones ----------
    pending = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    pending_draw = ImageDraw.Draw(pending)
    pending_dirty = False

    def flush() -> None:
        nonlocal base, pending, pending_draw, pending_dirty
        if pending_dirty:
            base = Image.alpha_composite(base, pending)
            pending = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            pending_draw = ImageDraw.Draw(pending)
            pending_dirty = False

    for layer in spec.layers:
        mergeable = layer.blur <= 0 and layer.opacity >= 0.999
        if mergeable:
            _draw_layer(pending_draw, layer, factor)
            pending_dirty = True
            continue

        flush()
        overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        _draw_layer(ImageDraw.Draw(overlay), layer, factor)
        if layer.blur > 0:
            overlay = overlay.filter(ImageFilter.GaussianBlur(radius=layer.blur * factor))
        if layer.opacity < 0.999:
            alpha = overlay.getchannel("A").point(lambda value: int(value * layer.opacity))
            overlay.putalpha(alpha)
        base = Image.alpha_composite(base, overlay)

    flush()

    # --- markers ------------------------------------------------------------
    markers = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(markers)
    for marker in spec.markers:
        cx, cy = marker.x * factor, marker.y * factor
        radius = marker.radius * factor
        pen.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=_rgba(marker.color, marker.opacity),
            outline=_rgba("#ffffff", 0.85) if marker.ring else None,
            width=max(1, int(3 * factor)) if marker.ring else 0,
        )
    base = Image.alpha_composite(base, markers)

    # --- text ---------------------------------------------------------------
    texts = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(texts)
    for text in spec.texts:
        font = _load_font(max(6, int(round(text.size * factor))), text.weight == "bold")
        _draw_text(
            pen,
            text.text,
            (text.x * factor, text.y * factor),
            font,
            _rgba(text.color, text.opacity),
            text.anchor,
            text.letter_spacing * factor,
        )
    base = Image.alpha_composite(base, texts)

    image = base.convert("RGB")
    if factor != 1:
        image = image.resize((spec.width, spec.height), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_png_file(spec: ArtSpec, path: Path, supersample: int = SUPERSAMPLE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_png(spec, supersample=supersample))
    return path


def available_font_source() -> Optional[str]:  # pragma: no cover - diagnostics
    for candidate in _FONT_BOLD + _FONT_REGULAR:
        if Path(candidate).exists():
            return candidate
    return None
