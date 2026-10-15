"""Formatting helpers shared by the artwork engine and the API."""

from __future__ import annotations

from datetime import datetime


def format_distance(metres: float | None) -> str:
    if metres is None:
        return "distance unknown"
    if metres < 1000:
        return f"{metres:.0f} m"
    return f"{metres / 1000.0:.2f} km"


def format_duration(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return "duration unknown"
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_speed(kmh: float | None) -> str:
    if kmh is None:
        return "n/a"
    return f"{kmh:.1f} km/h"


def format_date(value: datetime | None, fmt: str = "%d %b %Y") -> str:
    if value is None:
        return "date unknown"
    return value.strftime(fmt)


def format_coordinate(latitude: float, longitude: float) -> str:
    return f"{latitude:.5f}, {longitude:.5f}"
