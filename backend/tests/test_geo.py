"""Geodesic maths, coordinate validation and jump detection."""

from __future__ import annotations

import math

import pytest

from app.core.errors import ValidationFailed
from app.services.geo import (
    bearing_degrees,
    haversine_m,
    is_implausible_jump,
    is_valid_coordinate,
    speed_kmh,
    validate_coordinates,
)


def test_haversine_known_distance():
    # Mumbai (CST) -> Pune is a well known ~117 km great-circle distance.
    distance = haversine_m(18.9398, 72.8355, 18.5204, 73.8567)
    assert 110_000 < distance < 125_000


def test_haversine_zero_for_same_point():
    assert haversine_m(18.5, 73.8, 18.5, 73.8) == pytest.approx(0.0, abs=1e-9)


def test_haversine_is_symmetric():
    forward = haversine_m(18.5204, 73.8567, 18.5304, 73.8667)
    backward = haversine_m(18.5304, 73.8667, 18.5204, 73.8567)
    assert forward == pytest.approx(backward, rel=1e-12)


def test_haversine_one_degree_latitude_is_about_111_km():
    assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=0.01)


def test_bearing_north_and_east():
    assert bearing_degrees(18.0, 73.0, 18.1, 73.0) == pytest.approx(0.0, abs=0.5)
    assert bearing_degrees(18.0, 73.0, 18.0, 73.1) == pytest.approx(90.0, abs=0.5)


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (18.5204, 73.8567),
        (-33.8688, 151.2093),
        (0.0, 73.0),
        (18.0, 0.0),
        (89.999, 179.999),
    ],
)
def test_valid_coordinates_are_accepted(latitude, longitude):
    assert is_valid_coordinate(latitude, longitude)
    assert validate_coordinates(latitude, longitude) == (latitude, longitude)


@pytest.mark.parametrize(
    "latitude,longitude,code",
    [
        (91.0, 73.0, "latitude_out_of_range"),
        (-91.0, 73.0, "latitude_out_of_range"),
        (18.0, 181.0, "longitude_out_of_range"),
        (18.0, -181.0, "longitude_out_of_range"),
        (0.0, 0.0, "no_fix_sentinel"),
        (float("nan"), 73.0, "invalid_coordinates"),
        (float("inf"), 73.0, "invalid_coordinates"),
        (1e-9, 1e-9, "no_fix_sentinel"),
    ],
)
def test_invalid_coordinates_are_rejected(latitude, longitude, code):
    assert not is_valid_coordinate(latitude, longitude)
    with pytest.raises(ValidationFailed) as excinfo:
        validate_coordinates(latitude, longitude)
    assert excinfo.value.code == code


def test_speed_kmh_needs_positive_time():
    assert speed_kmh(10.0, 10.0) == pytest.approx(3.6)
    assert speed_kmh(10.0, 0.0) is None
    assert speed_kmh(10.0, -5.0) is None


def test_implausible_jump_detection():
    # 14 km in 5 seconds is impossible for a pedestrian.
    assert is_implausible_jump(14_000.0, 5.0, 200.0) is True
    # 7 m in 5 seconds is a normal walk.
    assert is_implausible_jump(7.0, 5.0, 200.0) is False
    # Without a usable time delta the reading must never be discarded.
    assert is_implausible_jump(14_000.0, 0.0, 200.0) is False


def test_valid_coordinate_is_false_for_garbage():
    assert not is_valid_coordinate(None, 73.0)
    assert not is_valid_coordinate("not-a-number", 73.0)
    assert not is_valid_coordinate(math.nan, math.nan)
