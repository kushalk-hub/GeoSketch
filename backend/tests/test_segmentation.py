"""Route segmentation: gaps, jumps, moving time and artwork thinning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.artwork.geometry import process_route
from app.utils.segmentation import segment_route

BASE = datetime(2026, 10, 15, 10, 30, 0, tzinfo=timezone.utc)


def point(latitude, longitude, offset_seconds, plausible=True):
    return SimpleNamespace(
        latitude=latitude,
        longitude=longitude,
        is_plausible=plausible,
        gps_timestamp=(BASE + timedelta(seconds=offset_seconds)).replace(tzinfo=None),
        server_timestamp=(BASE + timedelta(seconds=offset_seconds)).replace(tzinfo=None),
    )


def northward(count=10, spacing=0.000063, start_offset=0.0, step_seconds=5, plausible=True):
    """A plausible walk heading north (~7 m per fix)."""
    return [
        point(18.5204 + index * spacing, 73.8567, start_offset + index * step_seconds, plausible)
        for index in range(count)
    ]


def test_single_segment_when_walking_normally():
    result = segment_route(northward(10))
    assert len(result.segments) == 1
    assert result.used_points == 10
    assert result.gap_cuts == 0
    assert result.jump_cuts == 0
    assert 55 < result.distance_m < 75  # 9 segments of ~7 m
    assert result.moving_seconds == 45.0
    assert result.average_speed_kmh is not None
    assert 3.0 < result.average_speed_kmh < 7.0


def test_recording_gap_splits_the_route():
    points = northward(5) + northward(5, start_offset=600)
    result = segment_route(points, max_gap_seconds=180)
    assert len(result.segments) == 2
    assert result.gap_cuts == 1
    # The distance across the gap must not be counted.
    assert result.distance_m < 60


def test_impossible_jump_splits_the_route():
    points = northward(3)
    far = point(18.6204, 73.8567, 15)  # ~11 km north in 5 s
    points.append(far)
    points.append(point(18.62046, 73.8567, 20))
    result = segment_route(points)
    assert result.jump_cuts == 1
    assert len(result.segments) == 2


def test_implausible_points_are_excluded():
    points = northward(4)
    points.append(point(18.99, 73.99, 100, plausible=False))
    points.extend(northward(4, start_offset=105))
    result = segment_route(points)
    assert result.implausible_skipped == 1
    assert result.used_points == 8
    assert result.excluded_points == 1


def test_null_island_points_are_excluded():
    points = northward(3)
    points.append(point(0.0, 0.0, 15))
    result = segment_route(points)
    assert result.invalid_skipped == 1
    assert result.used_points == 3


def test_average_speed_is_none_without_movement():
    stationary = [point(18.52, 73.85, index * 5) for index in range(6)]
    result = segment_route(stationary)
    assert result.distance_m == 0.0
    assert result.average_speed_kmh is None


def test_process_route_normalises_into_canvas_and_keeps_aspect():
    route = process_route(northward(30, spacing=0.0002), width=1000, height=600, padding=60)
    xs = [x for segment in route.segments for x, _ in segment]
    ys = [y for segment in route.segments for _, y in segment]
    assert min(xs) >= 55 and max(xs) <= 945
    assert min(ys) >= 55 and max(ys) <= 545
    # A north-south route on a landscape canvas must not be stretched sideways.
    assert (max(xs) - min(xs)) < (max(ys) - min(ys))
    assert route.scale > 0
    summary = route.processing_summary()
    assert summary["projection"] == "local equirectangular"
    assert summary["source_points"] == 30


def test_process_route_thins_redundant_points_but_keeps_ends():
    # 400 fixes 1 cm apart: far denser than any canvas can show.
    dense = [point(18.5204 + index * 1e-8, 73.8567, index) for index in range(400)]
    route = process_route(dense, width=1200, height=800, min_point_distance_m=1.0)
    assert route.source_points == 400
    assert route.point_count < 400
    assert route.redundant_removed > 0
    assert route.start_point is not None and route.end_point is not None
    # The ends must survive the thinning.
    assert route.start_point == route.segments[0][0]
    assert route.end_point == route.segments[-1][-1]


def test_process_route_handles_empty_input():
    route = process_route([], width=800, height=600)
    assert route.is_empty
    assert route.segment_count == 0


def test_process_route_single_point():
    route = process_route(northward(1), width=800, height=600)
    assert route.point_count == 1
    assert route.segment_count == 0  # a dot is not a segment
    assert route.start_point == route.end_point
