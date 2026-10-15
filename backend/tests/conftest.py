"""Shared pytest fixtures.

The environment is configured **before** ``app`` is imported, because the
SQLAlchemy engine and the settings singleton are created at import time.  Every
test therefore runs against a throw-away SQLite file and a temporary artwork
directory; nothing touches the developer's ``backend/geosketch.db``.

Between tests the journey tables are emptied (devices stay registered), so tests
cannot see each other's journeys - which is exactly what matters for the
"device active journey" logic.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TMP_ROOT = Path(tempfile.mkdtemp(prefix="geosketch-tests-"))

os.environ["GEOSKETCH_DATABASE_URL"] = f"sqlite:///{(TMP_ROOT / 'test.db').as_posix()}"
os.environ["GEOSKETCH_ARTWORK_DIR"] = str(TMP_ROOT / "artworks")
os.environ["GEOSKETCH_SAMPLE_ROUTES_DIR"] = str(PROJECT_ROOT / "data" / "sample_routes")
os.environ["GEOSKETCH_DEVICE_KEYS"] = (
    "geosketch-01:test-device-key-01,geosketch-02:test-device-key-02"
)
os.environ["GEOSKETCH_DEVICE_OFFLINE_AFTER_SECONDS"] = "30"
os.environ["GEOSKETCH_RATE_LIMIT_REQUESTS"] = "100000"
os.environ["GEOSKETCH_MAX_REQUEST_BYTES"] = "65536"
os.environ["GEOSKETCH_DEFAULT_OWNER"] = "local"

DEVICE_ID = "geosketch-01"
DEVICE_KEY = "test-device-key-01"


def pytest_sessionfinish(session, exitstatus):  # pragma: no cover - teardown helper
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_journey_tables(client):
    """Wipe journeys/points/artworks after every test (devices are kept)."""
    yield

    from sqlalchemy import delete, update

    from app.database.session import SessionLocal
    from app.models.artwork import Artwork
    from app.models.device import Device
    from app.models.gps_point import GPSPoint
    from app.models.journey import Journey

    with SessionLocal() as db:
        db.execute(delete(GPSPoint))
        db.execute(delete(Artwork))
        db.execute(delete(Journey))
        db.execute(
            update(Device).values(
                last_seen_at=None,
                last_latitude=None,
                last_longitude=None,
                last_satellites=None,
                last_fix_at=None,
                points_received=0,
                connection_status="unknown",
            )
        )
        db.commit()


@pytest.fixture()
def device_headers() -> dict:
    return {"X-Device-Id": DEVICE_ID, "X-Device-Key": DEVICE_KEY}


@pytest.fixture()
def second_device_headers() -> dict:
    return {"X-Device-Id": "geosketch-02", "X-Device-Key": "test-device-key-02"}


@pytest.fixture()
def hardware_journey(client):
    """A fresh hardware recording journey (the ESP32-C3 would post into this)."""
    response = client.post(
        "/api/v1/journeys",
        json={"title": "Test hardware journey", "source": "hardware"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def journey(client):
    """A fresh DEMO journey, for state-machine and artwork tests."""
    response = client.post(
        "/api/v1/journeys",
        json={"title": "Test demo journey", "source": "demo"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_demo_points(client, journey_id: int, points: list[dict]) -> dict:
    """Bulk-upload demo points (the path DEMO MODE replay uses)."""
    response = client.post(
        f"/api/v1/journeys/{journey_id}/points",
        json={"points": points, "source": "demo"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def gps_point(
    latitude: float,
    longitude: float,
    *,
    seconds: int = 0,
    client_point_id: str | None = None,
    **extra,
) -> dict:
    """Build a firmware-style payload with a UTC GPS timestamp."""
    from datetime import datetime, timedelta, timezone

    stamp = datetime(2026, 10, 15, 10, 30, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "altitude": 560.0,
        "speed_kmh": 4.5,
        "satellites": 8,
        "timestamp": stamp.isoformat().replace("+00:00", "Z"),
    }
    if client_point_id is not None:
        payload["client_point_id"] = client_point_id
    payload.update(extra)
    return payload


@pytest.fixture()
def walking_route() -> list[dict]:
    """A short, plausible walking route (about 1.4 m/s heading north)."""
    points = []
    latitude = 18.520400
    for index in range(12):
        latitude += 0.000063  # ~7 m per fix
        points.append(
            gps_point(latitude, 73.856700, seconds=index * 5, client_point_id=f"p{index}")
        )
    return points
