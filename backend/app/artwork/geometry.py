"""Coordinate processing for the artwork canvas.

The raw GPS points are never modified - this module only produces a *derived*
canvas-space representation:

1. validate + drop implausible/0,0 fixes (delegated to ``segment_route``),
2. segment on recording gaps and impossible jumps,
3. project lon/lat to local metres with the equirectangular approximation
   (accurate at the scale of a single journey, and dependency free),
4. normalise the route into the canvas preserving the aspect ratio,
5. thin consecutive points that land on the same pixel,
6. hand the result to the style builders.

The thinning step is deliberately conservative (at most ~3 px between kept
points) so the shape of the route is always preserved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from app.artwork.styles import sequence_length
from app.utils.segmentation import SegmentationResult, segment_route

Point = Tuple[float, float]

#: Metres per degree of latitude (WGS84 mean) and the equatorial value for
#: longitude (scaled by cos(lat) at the projection origin).
METRES_PER_DEG_LAT = 110574.0
METRES_PER_DEG_LON = 111320.0

MIN_THIN_PX = 0.5
MAX_THIN_PX = 3.0


@dataclass
class ProcessedRoute:
    """A canvas-ready route plus the metadata needed to describe it."""

    width: int
    height: int
    padding: float
    segments: List[List[Point]] = field(default_factory=list)

    origin_latitude: float = 0.0
    origin_longitude: float = 0.0
    scale: float = 1.0  # canvas pixels per metre
    offset: Tuple[float, float] = (0.0, 0.0)

    source_points: int = 0
    used_points: int = 0
    redundant_removed: int = 0
    gap_cuts: int = 0
    jump_cuts: int = 0
    excluded_points: int = 0

    distance_m: float = 0.0
    duration_seconds: float = 0.0
    moving_seconds: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    start_point: Optional[Point] = None
    end_point: Optional[Point] = None
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None

    geo_bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    projected_bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    @property
    def point_count(self) -> int:
        """Points actually drawn (after thinning)."""
        return sum(len(segment) for segment in self.segments)

    @property
    def segment_count(self) -> int:
        return len([segment for segment in self.segments if len(segment) >= 2])

    @property
    def is_empty(self) -> bool:
        return self.point_count == 0

    def to_canvas(self, latitude: float, longitude: float) -> Point:
        """Project a geographic coordinate into canvas pixels."""
        x_m = (longitude - self.origin_longitude) * METRES_PER_DEG_LON * math.cos(
            math.radians(self.origin_latitude)
        )
        y_m = -(latitude - self.origin_latitude) * METRES_PER_DEG_LAT
        min_x, min_y, _, _ = self.projected_bounds
        return (
            self.offset[0] + (x_m - min_x) * self.scale,
            self.offset[1] + (y_m - min_y) * self.scale,
        )

    def processing_summary(self) -> Dict[str, object]:
        """Transparency block returned with every preview."""
        return {
            "source_points": self.source_points,
            "drawn_points": self.point_count,
            "redundant_removed": self.redundant_removed,
            "excluded_points": self.excluded_points,
            "gap_cuts": self.gap_cuts,
            "jump_cuts": self.jump_cuts,
            "segments": self.segment_count,
            "scale_px_per_m": round(self.scale, 4),
            "projection": "local equirectangular",
        }


def _project_points(points: Sequence, origin_lat: float, origin_lon: float) -> List[Point]:
    cos_lat = math.cos(math.radians(origin_lat))
    projected: List[Point] = []
    for point in points:
        x_m = (point.longitude - origin_lon) * METRES_PER_DEG_LON * cos_lat
        y_m = -(point.latitude - origin_lat) * METRES_PER_DEG_LAT
        projected.append((x_m, y_m))
    return projected


def _thin_segment(segment: List[Point], min_px: float) -> List[Point]:
    """Drop points closer than ``min_px`` to the previous kept point.

    First and last points of a segment are always kept, and a point that turns a
    corner sharply is kept even when close, because removing it would cut the
    corner off.
    """
    if len(segment) <= 2:
        return list(segment)

    kept: List[Point] = [segment[0]]
    for index in range(1, len(segment) - 1):
        previous_kept = kept[-1]
        candidate = segment[index]
        distance = math.dist(previous_kept, candidate)
        if distance < min_px:
            # Look ahead: keep the point when it defines a real direction change.
            next_point = segment[index + 1]
            first = math.atan2(candidate[1] - previous_kept[1], candidate[0] - previous_kept[0])
            second = math.atan2(next_point[1] - candidate[1], next_point[0] - candidate[0])
            turn = abs((second - first + math.pi) % (2 * math.pi) - math.pi)
            if turn < math.radians(20.0):
                continue
        kept.append(candidate)

    kept.append(segment[-1])
    return kept


def process_route(
    points: Sequence,
    *,
    width: int,
    height: int,
    padding: float = 72.0,
    min_point_distance_m: float = 1.0,
    max_gap_seconds: float = 180.0,
    max_plausible_speed_kmh: float = 200.0,
) -> ProcessedRoute:
    """Turn raw GPS points into a canvas-space route."""
    segmentation: SegmentationResult = segment_route(
        points,
        max_gap_seconds=max_gap_seconds,
        max_plausible_speed_kmh=max_plausible_speed_kmh,
    )

    route = ProcessedRoute(
        width=width,
        height=height,
        padding=padding,
        source_points=segmentation.source_points,
        excluded_points=segmentation.excluded_points,
        gap_cuts=segmentation.gap_cuts,
        jump_cuts=segmentation.jump_cuts,
        distance_m=segmentation.distance_m,
        moving_seconds=segmentation.moving_seconds,
        started_at=segmentation.started_at,
        finished_at=segmentation.finished_at,
    )
    if segmentation.started_at and segmentation.finished_at:
        route.duration_seconds = max(
            0.0, (segmentation.finished_at - segmentation.started_at).total_seconds()
        )

    flat_points = [point for segment in segmentation.segments for point in segment]
    if not flat_points:
        return route

    origin_lat = sum(point.latitude for point in flat_points) / len(flat_points)
    origin_lon = sum(point.longitude for point in flat_points) / len(flat_points)
    route.origin_latitude = origin_lat
    route.origin_longitude = origin_lon

    projected_segments = [
        _project_points(segment, origin_lat, origin_lon) for segment in segmentation.segments
    ]
    all_x = [x for segment in projected_segments for x, _ in segment]
    all_y = [y for segment in projected_segments for _, y in segment]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    span_x, span_y = max_x - min_x, max_y - min_y
    route.projected_bounds = (min_x, min_y, max_x, max_y)

    usable_w = max(1.0, width - 2.0 * padding)
    usable_h = max(1.0, height - 2.0 * padding)

    candidates = []
    if span_x > 1e-6:
        candidates.append(usable_w / span_x)
    if span_y > 1e-6:
        candidates.append(usable_h / span_y)
    scale = min(candidates) if candidates else 1.0
    route.scale = scale

    # Centre the drawing inside the padded canvas (aspect ratio preserved by the
    # single uniform scale factor above).
    route.offset = (
        padding + max(0.0, (usable_w - span_x * scale) / 2.0),
        padding + max(0.0, (usable_h - span_y * scale) / 2.0),
    )

    def _to_canvas_local(x_m: float, y_m: float) -> Point:
        return (
            route.offset[0] + (x_m - min_x) * scale,
            route.offset[1] + (y_m - min_y) * scale,
        )

    min_px = min(MAX_THIN_PX, max(MIN_THIN_PX, min_point_distance_m * scale))

    canvas_segments: List[List[Point]] = []
    for segment in projected_segments:
        canvas_segment = _thin_segment([_to_canvas_local(x, y) for x, y in segment], min_px)
        route.redundant_removed += max(0, len(segment) - len(canvas_segment))
        canvas_segments.append(canvas_segment)
    route.segments = canvas_segments
    route.used_points = route.point_count

    route.start_point = canvas_segments[0][0]
    route.end_point = canvas_segments[-1][-1]
    first_raw = segmentation.segments[0][0]
    last_raw = segmentation.segments[-1][-1]
    route.start_latitude = first_raw.latitude
    route.start_longitude = first_raw.longitude
    route.end_latitude = last_raw.latitude
    route.end_longitude = last_raw.longitude

    latitudes = [point.latitude for point in flat_points]
    longitudes = [point.longitude for point in flat_points]
    route.geo_bounds = (min(latitudes), min(longitudes), max(latitudes), max(longitudes))
    return route


def subdivide_route(
    segments: Sequence[Sequence[Point]], steps: int = 120
) -> List[Tuple[List[Point], float]]:
    """Split the route into ~``steps`` equal-length chunks for gradient colouring.

    Chunks are produced by resampling along the arc length (not by slicing the
    recorded points), so the ramp stays smooth even when the GPS only provided a
    handful of fixes.  Segment boundaries are never crossed: a recording gap
    stays a gap.

    Returns ``(polyline, t)`` pairs where ``t`` is the normalised position along
    the route (0 = start, 1 = end) so a colour ramp can be applied.
    """
    total = sum(sequence_length(segment) for segment in segments)
    if total <= 0:
        flat = [point for segment in segments for point in segment]
        return [(flat, 0.0)] if len(flat) >= 2 else []

    spacing = max(total / max(2, steps), 0.5)
    chunks: List[Tuple[List[Point], float]] = []
    current: List[Point] = []
    arc = 0.0
    mark = spacing

    for segment in segments:
        if len(segment) < 2:
            continue
        # A new segment always starts a new chunk (the gap must stay visible).
        current = [segment[0]]
        for start_point, end_point in zip(segment, segment[1:]):
            length = math.dist(start_point, end_point)
            current.append(end_point)
            arc += length
            while length > 1e-9 and arc >= mark:
                ratio = max(0.0, min(1.0, 1.0 - (arc - mark) / length))
                crossing = (
                    start_point[0] + (end_point[0] - start_point[0]) * ratio,
                    start_point[1] + (end_point[1] - start_point[1]) * ratio,
                )
                current[-1] = crossing
                chunks.append((current, min(1.0, mark / total)))
                current = [crossing]
                mark += spacing

    if len(current) >= 2:
        chunks.append((current, 1.0))
    elif chunks and current:
        # Only a stray dot left over: tack it onto the previous chunk.
        chunks[-1][0].append(current[-1])

    if chunks:
        # The final chunk is the end of the route, so it must sample the very
        # end of the colour ramp (and the first chunk its start).
        chunks[-1] = (chunks[-1][0], 1.0)
        chunks[0] = (chunks[0][0], min(chunks[0][1], spacing / total))
    return chunks
