"""Geodesic maths and GPS sanity checks.

All distances use the haversine formula on a spherical Earth.  Haversine is
accurate to roughly 0.5 % for the path lengths involved in a walking/cycling
journey, which is far below the error introduced by consumer GPS noise itself.
"""

from __future__ import annotations

import math
from typing import Protocol

from app.core.errors import ValidationFailed

#: IUGG mean Earth radius in metres.
EARTH_RADIUS_M = 6371008.8

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


class HasCoordinates(Protocol):
    latitude: float
    longitude: float


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    # Clamp guards against floating point drift producing a > 1 argument.
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def distance_between(a: HasCoordinates, b: HasCoordinates) -> float:
    return haversine_m(a.latitude, a.longitude, b.latitude, b.longitude)


def is_null_island(latitude: float, longitude: float) -> bool:
    """True for the 0,0 sentinel the NEO-6M emits before it has a fix."""
    return abs(latitude) < 1e-7 and abs(longitude) < 1e-7


def is_valid_coordinate(latitude: float, longitude: float) -> bool:
    """Range and sentinel checks; does not raise."""
    if latitude is None or longitude is None:
        return False
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return False
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False
    if not (MIN_LATITUDE <= lat <= MAX_LATITUDE):
        return False
    if not (MIN_LONGITUDE <= lon <= MAX_LONGITUDE):
        return False
    return not is_null_island(lat, lon)


def validate_coordinates(latitude: float, longitude: float) -> tuple[float, float]:
    """Return ``(lat, lon)`` or raise :class:`ValidationFailed`."""
    if latitude is None or longitude is None:
        raise ValidationFailed(
            "latitude and longitude are required", code="missing_coordinates"
        )
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(
            "latitude and longitude must be numbers", code="invalid_coordinates"
        ) from exc

    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        raise ValidationFailed(
            "latitude/longitude must be finite numbers", code="invalid_coordinates"
        )
    if not (MIN_LATITUDE <= lat <= MAX_LATITUDE):
        raise ValidationFailed(
            f"latitude out of range: {lat}", code="latitude_out_of_range"
        )
    if not (MIN_LONGITUDE <= lon <= MAX_LONGITUDE):
        raise ValidationFailed(
            f"longitude out of range: {lon}", code="longitude_out_of_range"
        )
    if is_null_island(lat, lon):
        raise ValidationFailed(
            "coordinates 0,0 mean the GPS module had no fix", code="no_fix_sentinel"
        )
    return lat, lon


def speed_kmh(distance_m: float, seconds: float) -> float | None:
    """Speed in km/h, or ``None`` when the time delta makes it meaningless."""
    if seconds is None or seconds <= 0:
        return None
    return (distance_m / seconds) * 3.6


def is_implausible_jump(distance_m: float, seconds: float, max_speed_kmh: float) -> bool:
    """Detect a fix that would require an impossible speed.

    When the time delta is unknown or zero the check is skipped: without a
    reference we must not discard a real reading.
    """
    implied = speed_kmh(distance_m, seconds)
    if implied is None:
        return False
    return implied > max_speed_kmh


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees (0 = north)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def point_time(point) -> object | None:
    """Best available timestamp for a point: GPS first, server fallback."""
    return getattr(point, "gps_timestamp", None) or getattr(point, "server_timestamp", None)


def cumulative_distance(points) -> float:
    """Total haversine distance along an ordered point sequence, in metres."""
    total = 0.0
    previous = None
    for point in points:
        if previous is not None:
            total += distance_between(previous, point)
        previous = point
    return total
