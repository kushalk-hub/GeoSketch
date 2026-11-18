from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def auth_parent(client, monkeypatch):
    from app.core.config import reset_settings_cache

    monkeypatch.setenv("GEOSKETCH_AUTH_SECRET", "test-only-parent-secret-1234567890")
    reset_settings_cache()
    email = f"family-{uuid.uuid4().hex}@example.test"
    response = client.post(
        "/api/v1/parent/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text
    yield email, response.json()["token"]
    reset_settings_cache()


def test_registration_login_and_me(client, auth_parent):
    email, token = auth_parent
    login = client.post(
        "/api/v1/parent/login", json={"email": email.upper(), "password": "correct horse"}
    )
    assert login.status_code == 200
    assert (
        client.get("/api/v1/parent/me", headers={"Authorization": f"Bearer {token}"}).json()[
            "email"
        ]
        == email
    )


def test_wrong_password_is_generic(client, auth_parent):
    email, _ = auth_parent
    wrong = client.post("/api/v1/parent/login", json={"email": email, "password": "incorrect pass"})
    missing = client.post(
        "/api/v1/parent/login",
        json={"email": f"missing-{uuid.uuid4().hex}@example.test", "password": "incorrect pass"},
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_missing_auth_secret_is_only_a_parent_route_failure(
    client, monkeypatch, device_headers, hardware_journey
):
    from app.core.config import reset_settings_cache

    monkeypatch.setenv("GEOSKETCH_AUTH_SECRET", "")
    reset_settings_cache()
    response = client.post(
        "/api/v1/parent/register",
        json={"email": "no-secret@example.test", "password": "password123"},
    )
    assert response.status_code == 503 and response.json()["error"]["code"] == "auth_not_configured"
    assert client.get("/api/v1/health").status_code == 200
    ingest = client.post(
        "/api/v1/gps/points",
        headers=device_headers,
        json={"latitude": 18.5204, "longitude": 73.8567, "journey_id": hardware_journey["id"]},
    )
    assert ingest.status_code == 201
    reset_settings_cache()
