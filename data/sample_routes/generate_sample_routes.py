"""Deterministic generator for the bundled DEMO MODE sample routes.

The generated JSON files in this directory are simulated GPS traces: they exist
so the whole pipeline (map, statistics, artwork, exports) can be demonstrated
without carrying the ESP32-C3 outdoors.  They are always imported as journeys
with ``source = "demo"`` and are never presented as hardware data.

Usage (from this directory)::

    python generate_sample_routes.py

The script is standard-library only and deterministic: re-running it reproduces
byte-identical output for the same Python version.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

EARTH_RADIUS_M = 6371008.8
METRES_PER_DEG_LAT = 110574.0
METRES_PER_DEG_LON = 111320.0

DEFAULT_SPEED_MPS = 1.35  # ~4.9 km/h, a normal walking pace
SAMPLE_INTERVAL_S = 5.0  # matches the firmware's transmit interval
OUTPUT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Local flat-earth helpers (good enough at the scale of a single route)
# ---------------------------------------------------------------------------
def to_local(lat: float, lon: float, origin: Tuple[float, float]) -> Tuple[float, float]:
    origin_lat, origin_lon = origin
    x = (lon - origin_lon) * METRES_PER_DEG_LON * math.cos(math.radians(origin_lat))
    y = (lat - origin_lat) * METRES_PER_DEG_LAT
    return x, y


def to_geo(x: float, y: float, origin: Tuple[float, float]) -> Tuple[float, float]:
    origin_lat, origin_lon = origin
    lat = origin_lat + y / METRES_PER_DEG_LAT
    lon = origin_lon + x / (METRES_PER_DEG_LON * math.cos(math.radians(origin_lat)))
    return lat, lon


def resample_polyline(
    points: Sequence[Tuple[float, float]], step_m: float
) -> List[Tuple[float, float]]:
    """Resample a local-space polyline at a constant spacing."""
    if len(points) < 2:
        return list(points)
    out: List[Tuple[float, float]] = [points[0]]
    remaining = step_m
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        segment = math.dist((x1, y1), (x2, y2))
        if segment <= 0:
            continue
        travelled = 0.0
        while travelled + remaining <= segment:
            travelled += remaining
            ratio = travelled / segment
            out.append((x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio))
            remaining = step_m
        remaining -= segment - travelled
    return out


# ---------------------------------------------------------------------------
# Route shapes (defined in local metres around an origin)
# ---------------------------------------------------------------------------
def marine_drive_loop() -> List[Tuple[float, float]]:
    """Queen's Neck, Mumbai: a closed coastal loop (~3 km).

    A pinched ellipse: two long promenade legs joined by rounded ends, which is
    what the real seafront walk looks like from above.
    """
    points: List[Tuple[float, float]] = []
    for index in range(220):
        t = 2.0 * math.pi * index / 219.0
        x = 560.0 * math.cos(t)
        y = 380.0 * math.sin(t) * (1.0 + 0.18 * math.cos(2.0 * t))
        points.append((x, y))
    # a short spur at the north end (the loop around the fountain)
    centre = points[0]
    for index in range(1, 61):
        angle = 2.0 * math.pi * index / 60.0
        points.append(
            (centre[0] + 70.0 * math.cos(angle), centre[1] + 70.0 * math.sin(angle))
        )
    points.append(centre)
    return points


def riverfront_walk() -> List[Tuple[float, float]]:
    """Pune riverfront: a meandering walk with a bench rest at the midpoint."""
    origin = (18.5240, 73.8420)
    points: List[Tuple[float, float]] = []
    for index in range(260):
        t = index / 259.0
        x = 1650.0 * t
        y = 150.0 * math.sin(t * math.pi * 2.4) + 60.0 * math.sin(t * math.pi * 6.0)
        points.append((x, y))
    return points


def hill_switchbacks() -> List[Tuple[float, float]]:
    """A climb up a hill road: six switchbacks (~2.6 km) - a route-art favourite."""
    points: List[Tuple[float, float]] = []
    half_width = 210.0
    leg_rise = 88.0
    for leg in range(6):
        start_x = -half_width if leg % 2 == 0 else half_width
        end_x = -start_x
        y0 = leg * leg_rise
        for index in range(23):
            t = index / 22.0
            # rounded hairpin at the ends: bulge the leg slightly outwards
            x = start_x + (end_x - start_x) * t
            y = y0 + math.sin(t * math.pi) * 26.0
            points.append((x, y))
        # the hairpin turn itself: a short outward bulge, then onto the next leg
        bulge = 16.0 if end_x > 0 else -16.0
        points.append((end_x + bulge, y0 + leg_rise * 0.5))
        points.append((end_x, y0 + leg_rise))
    return points


def city_grid_walk() -> List[Tuple[float, float]]:
    """A city-block walk: four blocks and back to the start."""
    origin = (18.5204, 73.8567)
    corners = [
        (0.0, 0.0),
        (520.0, 0.0),
        (520.0, 430.0),
        (0.0, 430.0),
        (-260.0, 430.0),
        (-260.0, 0.0),
        (0.0, 0.0),
    ]
    points: List[Tuple[float, float]] = []
    for (x1, y1), (x2, y2) in zip(corners, corners[1:]):
        for index in range(24):
            t = index / 24.0
            points.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    points.append(corners[-1])
    return points


# ---------------------------------------------------------------------------
# Trace synthesis
# ---------------------------------------------------------------------------
def build_trace(
    shape: Sequence[Tuple[float, float]],
    origin: Tuple[float, float],
    *,
    seed: int,
    speed_mps: float = DEFAULT_SPEED_MPS,
    base_altitude: float = 12.0,
    altitude_amplitude: float = 4.0,
    outage: Tuple[int, int] | None = None,
    rest_at: int | None = None,
    rest_seconds: float = 240.0,
    noise_m: float = 3.5,
) -> List[Dict[str, float]]:
    """Turn a local-space shape into a noisy, timed GPS trace.

    ``outage`` drops an index range to emulate losing satellite lock (used to
    demonstrate how gaps are never joined by a straight line).  ``rest_at``
    inserts stationary points, which is how a real pause looks to the device.
    """
    rng = random.Random(seed)
    step_m = speed_mps * SAMPLE_INTERVAL_S
    samples = resample_polyline(shape, step_m)

    trace: List[Dict[str, float]] = []
    elapsed = 0.0
    for index, (x, y) in enumerate(samples):
        if outage and outage[0] <= index < outage[1]:
            elapsed += SAMPLE_INTERVAL_S
            continue

        if rest_at is not None and index == rest_at:
            for _ in range(int(rest_seconds / SAMPLE_INTERVAL_S)):
                elapsed += SAMPLE_INTERVAL_S
                jitter_x = rng.gauss(0.0, 1.2)
                jitter_y = rng.gauss(0.0, 1.2)
                lat, lon = to_geo(x + jitter_x, y + jitter_y, origin)
                trace.append(
                    {
                        "t": round(elapsed, 1),
                        "latitude": round(lat, 7),
                        "longitude": round(lon, 7),
                        "altitude": round(base_altitude + rng.gauss(0.0, 0.6), 1),
                        "speed_kmh": round(abs(rng.gauss(0.4, 0.5)), 2),
                        "satellites": rng.randint(7, 11),
                    }
                )

        previous = trace[-1] if trace else None
        latitude, longitude = to_geo(
            x + rng.gauss(0.0, noise_m * 0.5), y + rng.gauss(0.0, noise_m * 0.5), origin
        )
        elapsed += SAMPLE_INTERVAL_S

        if previous is None:
            instant_speed = speed_mps
        else:
            distance = math.dist(
                to_local(previous["latitude"], previous["longitude"], origin), (x, y)
            )
            instant_speed = distance / SAMPLE_INTERVAL_S

        altitude = base_altitude + altitude_amplitude * math.sin(index / 90.0) + rng.gauss(0.0, 0.8)
        trace.append(
            {
                "t": round(elapsed, 1),
                "latitude": round(latitude, 7),
                "longitude": round(longitude, 7),
                "altitude": round(altitude, 1),
                "speed_kmh": round(max(0.0, instant_speed * 3.6 + rng.gauss(0.0, 0.25)), 2),
                "satellites": rng.randint(6, 12),
            }
        )
    return trace


def haversine_m(a: Dict[str, float], b: Dict[str, float]) -> float:
    phi1, phi2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    d_phi = phi2 - phi1
    d_lambda = math.radians(b["longitude"] - a["longitude"])
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def distance_m(trace: Sequence[Dict[str, float]]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(trace, trace[1:]))


def write_route(filename: str, payload: Dict) -> None:
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(
        f"  {filename:<28} points={len(payload['points']):>4} "
        f"distance={payload['distance_m'] / 1000:.2f} km "
        f"duration={payload['duration_seconds'] / 60:.1f} min"
    )


def polyline_length_m(points: Sequence[Tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def main() -> None:
    print("Generating DEMO sample routes (simulated GPS, not hardware data):")
    for name, shape in (
        ("marine_drive_loop", marine_drive_loop()),
        ("riverfront_walk", riverfront_walk()),
        ("hill_switchbacks", hill_switchbacks()),
        ("city_grid_walk", city_grid_walk()),
    ):
        print(f"  shape {name:<20} {polyline_length_m(shape) / 1000:.2f} km")

    marine = build_trace(
        marine_drive_loop(), (18.9400, 72.8180), seed=101, base_altitude=8.0
    )
    write_route(
        "marine_drive_loop.json",
        {
            "id": "marine_drive_loop",
            "name": "Marine Drive Loop",
            "description": (
                "Coastal promenade walk in Mumbai that closes into a small loop at "
                "the north end. Simulated demo data."
            ),
            "source": "demo",
            "point_count": len(marine),
            "distance_m": round(distance_m(marine), 1),
            "duration_seconds": marine[-1]["t"],
            "points": marine,
        },
    )

    river = build_trace(
        riverfront_walk(),
        (18.5240, 73.8420),
        seed=202,
        base_altitude=560.0,
        outage=(120, 180),  # 5 minutes without a fix -> route must be split
    )
    write_route(
        "riverfront_walk.json",
        {
            "id": "riverfront_walk",
            "name": "Riverfront Walk (with GPS outage)",
            "description": (
                "Meandering riverfront walk in Pune containing a deliberate "
                "5-minute loss of satellite lock, so DEMO MODE can show how gaps "
                "are split instead of being joined by a straight line."
            ),
            "source": "demo",
            "point_count": len(river),
            "distance_m": round(distance_m(river), 1),
            "duration_seconds": river[-1]["t"],
            "points": river,
        },
    )

    hill = build_trace(
        hill_switchbacks(),
        (18.7520, 73.4020),
        seed=303,
        speed_mps=1.15,
        base_altitude=620.0,
        altitude_amplitude=26.0,
    )
    write_route(
        "hill_switchbacks.json",
        {
            "id": "hill_switchbacks",
            "name": "Hill Switchbacks",
            "description": (
                "Six hairpin switchbacks on a climb - a shape that looks striking "
                "in every artwork style. Simulated demo data."
            ),
            "source": "demo",
            "point_count": len(hill),
            "distance_m": round(distance_m(hill), 1),
            "duration_seconds": hill[-1]["t"],
            "points": hill,
        },
    )

    grid = build_trace(
        city_grid_walk(),
        (18.5204, 73.8567),
        seed=404,
        base_altitude=560.0,
        rest_at=60,  # a bench stop: stationary fixes, no movement
    )
    write_route(
        "city_grid_walk.json",
        {
            "id": "city_grid_walk",
            "name": "City Grid Walk (with rest stop)",
            "description": (
                "Four city blocks in Pune with a 4-minute rest stop, which shows "
                "how average speed is computed over moving time only. Simulated "
                "demo data."
            ),
            "source": "demo",
            "point_count": len(grid),
            "distance_m": round(distance_m(grid), 1),
            "duration_seconds": grid[-1]["t"],
            "points": grid,
        },
    )

    print("Done.")


if __name__ == "__main__":
    main()
