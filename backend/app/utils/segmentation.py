"""Route segmentation: the single place that decides where a route is broken.

Both the statistics service and the artwork engine use this module, so the
distance reported on the dashboard always matches the distance drawn on the
artwork.

Two kinds of break are detected:

* **gap**  - the time between consecutive fixes exceeds ``max_gap_seconds``
  (paused recording, device switched off, lost sky view).  Connecting across a
  gap would draw a straight line the user never walked.
* **jump** - the implied speed between consecutive fixes is impossible
  (multipath reflection, a fix taken a few hundred metres away).  The offending
  point starts a new segment instead of being connected to the previous one.

Points already flagged ``is_plausible = False`` by the ingest service and the
0,0 "no fix" sentinel are dropped before segmenting.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar

from app.services.geo import (
    distance_between,
    haversine_m,
    is_implausible_jump,
    is_valid_coordinate,
    point_time,
    speed_kmh,
)

T = TypeVar("T")


@dataclass
class SegmentationResult(Generic[T]):
    segments: list[list[T]] = field(default_factory=list)
    distance_m: float = 0.0
    moving_seconds: float = 0.0
    max_speed_kmh: float | None = None
    gap_cuts: int = 0
    jump_cuts: int = 0
    implausible_skipped: int = 0
    invalid_skipped: int = 0
    source_points: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def used_points(self) -> int:
        return sum(len(segment) for segment in self.segments)

    @property
    def excluded_points(self) -> int:
        return self.implausible_skipped + self.invalid_skipped

    @property
    def average_speed_kmh(self) -> float | None:
        """Average speed over moving time only (never over wall-clock pauses)."""
        if self.moving_seconds < 5.0 or self.distance_m <= 0:
            return None
        return (self.distance_m / self.moving_seconds) * 3.6


def _seconds_between(first, second) -> float | None:
    start = point_time(first)
    end = point_time(second)
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds()
    if delta <= 0:
        # Duplicated or out-of-order timestamps: no usable rate, do not judge.
        return None
    return delta


def pair_metrics(
    previous,
    point,
    *,
    max_gap_seconds: float = 180.0,
    max_plausible_speed_kmh: float = 200.0,
):
    """Classify two consecutive fixes: ``(is_cut, distance_m, delta_seconds)``.

    Single source of truth for the gap/jump rules, shared by the batch
    segmenter below and the incremental ingest path in the journey service, so
    the live distance counter can never disagree with the recomputed value.
    """
    distance = distance_between(previous, point)
    delta = _seconds_between(previous, point)
    if delta is not None and delta > max_gap_seconds:
        return True, distance, delta
    if is_implausible_jump(distance, delta or 0.0, max_plausible_speed_kmh):
        return True, distance, delta
    return False, distance, delta


def segment_route(
    points: Sequence,
    *,
    max_gap_seconds: float = 180.0,
    max_plausible_speed_kmh: float = 200.0,
) -> SegmentationResult:
    """Split ``points`` (already in chronological order) into drawable segments."""
    result: SegmentationResult = SegmentationResult(source_points=len(points))

    cleaned: list = []
    for point in points:
        if getattr(point, "is_plausible", True) is False:
            result.implausible_skipped += 1
            continue
        if not is_valid_coordinate(point.latitude, point.longitude):
            result.invalid_skipped += 1
            continue
        cleaned.append(point)

    if not cleaned:
        return result

    result.started_at = point_time(cleaned[0])
    result.finished_at = point_time(cleaned[-1])

    current: list = [cleaned[0]]
    for previous, point in itertools.pairwise(cleaned):
        cut, distance, delta = pair_metrics(
            previous,
            point,
            max_gap_seconds=max_gap_seconds,
            max_plausible_speed_kmh=max_plausible_speed_kmh,
        )
        if cut:
            if delta is not None and delta > max_gap_seconds:
                result.gap_cuts += 1
            else:
                result.jump_cuts += 1

        if cut:
            result.segments.append(current)
            current = [point]
            continue

        current.append(point)
        result.distance_m += distance
        if delta is not None:
            result.moving_seconds += delta
        segment_speed = speed_kmh(distance, delta or 0.0)
        if segment_speed is not None and (
            result.max_speed_kmh is None or segment_speed > result.max_speed_kmh
        ):
            result.max_speed_kmh = segment_speed

    result.segments.append(current)
    return result


def straight_line_distance(points: Sequence) -> float:
    """Haversine distance that ignores segment breaks (used for diagnostics)."""
    total = 0.0
    for previous, point in itertools.pairwise(points):
        total += haversine_m(
            previous.latitude, previous.longitude, point.latitude, point.longitude
        )
    return total
