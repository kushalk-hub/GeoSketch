"""DEMO MODE, service metadata, error envelope and middleware behaviour."""

from __future__ import annotations

import pytest

JOURNEYS = "/api/v1/journeys"
DEMO = "/api/v1/demo/routes"


# ---------------------------------------------------------------------------
# demo mode
# ---------------------------------------------------------------------------
def test_sample_routes_are_listed_and_flagged_as_demo(client):
    routes = client.get(DEMO).json()
    assert routes, "at least one bundled sample route is required"
    identifiers = {route["id"] for route in routes}
    assert {"marine_drive_loop", "riverfront_walk", "hill_switchbacks", "city_grid_walk"} <= identifiers
    for route in routes:
        assert route["source"] == "demo"
        assert route["is_demo"] is True
        assert route["point_count"] > 100
        assert route["distance_m"] > 500
        assert route["duration_seconds"] > 60


def test_sample_route_detail_is_chronological(client):
    detail = client.get(f"{DEMO}/riverfront_walk").json()
    assert detail["name"]
    assert len(detail["points"]) == detail["point_count"]
    offsets = [point["t"] for point in detail["points"]]
    assert offsets == sorted(offsets)
    for point in detail["points"][:5]:
        assert -90 <= point["latitude"] <= 90
        assert -180 <= point["longitude"] <= 180


def test_unknown_sample_route_returns_404_with_alternatives(client):
    response = client.get(f"{DEMO}/not_a_route")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "sample_route_not_found"
    assert "marine_drive_loop" in error["details"]["available"]


def test_import_sample_route_creates_a_demo_journey(client):
    response = client.post(f"{DEMO}/riverfront_walk/import", json={"title": "Demo walk"})
    assert response.status_code == 201, response.text
    journey = response.json()
    assert journey["source"] == "demo"
    assert journey["status"] == "stopped"
    assert journey["point_count"] > 100

    statistics = client.get(f"{JOURNEYS}/{journey['id']}/statistics").json()
    assert statistics["source"] == "demo"
    assert statistics["distance_km"] > 1.0
    assert statistics["gap_count"] >= 1  # the bundled 5-minute outage
    assert statistics["average_speed_kmh"] is not None


def test_imported_demo_route_can_produce_artwork(client):
    journey = client.post(f"{DEMO}/city_grid_walk/import", json={}).json()
    response = client.post(f"{JOURNEYS}/{journey['id']}/artwork", json={"style": "gradient"})
    assert response.status_code == 201, response.text
    artwork = response.json()
    png = client.get(f"/api/v1/artworks/{artwork['id']}/download", params={"format": "png"})
    svg = client.get(f"/api/v1/artworks/{artwork['id']}/download", params={"format": "svg"})
    assert png.content.startswith(b"\x89PNG")
    assert b"<svg" in svg.content


def test_demo_data_is_never_mixed_into_a_hardware_journey(client, device_headers, walking_route):
    hardware = client.post(JOURNEYS, json={"title": "Hardware", "source": "hardware"}).json()
    client.post(
        "/api/v1/gps/points",
        json={**walking_route[0], "journey_id": hardware["id"]},
        headers=device_headers,
    )
    # The bulk endpoint (used by demo replay) refuses to write hardware points...
    assert (
        client.post(
            f"{JOURNEYS}/{hardware['id']}/points",
            json={"points": walking_route, "source": "hardware"},
        ).status_code
        == 422
    )
    # ...and the device endpoint is the only way hardware data can enter.
    detail = client.get(f"{JOURNEYS}/{hardware['id']}").json()
    assert detail["source"] == "hardware"
    assert all(point["source"] == "hardware" for point in detail["points"])


# ---------------------------------------------------------------------------
# service metadata
# ---------------------------------------------------------------------------
def test_health_endpoint(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["devices"] >= 2
    assert body["database"] == "sqlite"
    assert set(body["artwork_styles"]) == {"minimal", "neon", "gradient", "poster", "custom"}


def test_root_banner(client):
    body = client.get("/").json()
    assert body["project"] == "GeoSketch"


def test_openapi_schema_is_served(client):
    schema = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/gps/points" in schema["paths"]
    assert "/api/v1/journeys/{journey_id}/artwork" in schema["paths"]
    assert "/api/v1/journeys/{journey_id}/statistics" in schema["paths"]


# ---------------------------------------------------------------------------
# error handling and middleware
# ---------------------------------------------------------------------------
def test_unknown_route_uses_the_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_validation_error_envelope_lists_fields(client):
    response = client.post(JOURNEYS, json={"device_id": 12345, "source": "car"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert len(error["details"]["errors"]) >= 1


def test_oversized_request_body_is_rejected(client, device_headers):
    payload = {"latitude": 18.52, "longitude": 73.85, "padding": "x" * 80_000}
    response = client.post("/api/v1/gps/points", json=payload, headers=device_headers)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_rate_limit_middleware_returns_429():
    """Unit test of the limiter with a tiny window (kept out of the main app)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.middleware import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests=3, window_seconds=60)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as limited:
        codes = [limited.get("/ping").status_code for _ in range(5)]

    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
    assert codes[4] == 429


def test_rate_limit_headers_are_exposed(client):
    response = client.get("/api/v1/health")
    assert response.headers["X-RateLimit-Limit"]
    assert "X-RateLimit-Remaining" in response.headers


def test_credentials_are_not_leaked_in_device_responses(client):
    devices = client.get("/api/v1/devices").json()
    for device in devices:
        assert "api_key_hash" not in device
        assert "api_key" not in device


def test_cors_origins_accept_a_comma_separated_env_value():
    """Regression: a List field would make pydantic-settings crash at import."""
    from app.core.config import Settings

    settings = Settings(cors_origins="http://localhost:5173,http://127.0.0.1:5173")
    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]

    single = Settings(cors_origins="http://example.test")
    assert single.cors_origin_list == ["http://example.test"]


def test_settings_load_from_the_documented_env_format(monkeypatch):
    """Every value in .env.example must be parseable without raising."""
    from pathlib import Path

    from app.core.config import Settings

    env_example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(
        encoding="utf-8"
    )
    for line in env_example.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        monkeypatch.setenv(key.strip(), value.strip())

    settings = Settings()
    assert settings.device_key_map
    origins = settings.cors_origin_list
    assert origins and all(origin.startswith("http") for origin in origins)
    assert settings.device_offline_after_seconds > 0
    assert settings.max_request_bytes > 1024
    assert settings.artwork_dir.is_absolute()


def test_postgres_ready_configuration_is_documented():
    """The project must stay a DATABASE_URL swap away from PostgreSQL."""
    from pathlib import Path

    env_example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "postgresql" in env_example
    assert "GEOSKETCH_DATABASE_URL" in env_example


@pytest.mark.parametrize("method,path", [("get", "/api/v1/health")])
def test_content_type_is_json(client, method, path):
    response = getattr(client, method)(path)
    assert response.headers["content-type"].startswith("application/json")
