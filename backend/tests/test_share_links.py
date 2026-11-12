from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select


def create_parent(client, secret, monkeypatch):
    from app.core.config import reset_settings_cache

    monkeypatch.setenv("GEOSKETCH_AUTH_SECRET", secret)
    reset_settings_cache()
    email = f"share-{uuid.uuid4().hex}@example.test"
    response = client.post(
        "/api/v1/parent/register", json={"email": email, "password": "password123"}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_share_token_is_only_returned_once_and_live_is_limited(client, monkeypatch):
    from app.database.session import SessionLocal
    from app.models.parent import ShareLink

    token = create_parent(client, "share-secret-for-tests-123456789", monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/parent/share-links",
        headers=headers,
        json={"device_id": "geosketch-01", "label": "Aarav"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    raw = body["token"]
    with SessionLocal() as db:
        link = db.scalar(select(ShareLink).where(ShareLink.id == body["id"]))
        assert link.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert raw not in link.token_hash
    listed = client.get("/api/v1/parent/share-links", headers=headers).json()
    assert all("token" not in item for item in listed)
    live = client.get(f"/api/v1/live/{raw}")
    assert live.status_code == 200
    assert live.headers["cache-control"] == "no-store"
    assert live.headers["referrer-policy"] == "no-referrer"
    assert set(live.json()) == {
        "label",
        "status",
        "last_seen",
        "position",
        "trail",
        "zones",
        "expires_at",
    }
    assert "device_id" not in live.json()
    from app.core.config import reset_settings_cache

    reset_settings_cache()


def test_parent_cannot_revoke_another_parents_link(client, monkeypatch):
    token1 = create_parent(client, "share-secret-for-tests-123456789", monkeypatch)
    first = client.post(
        "/api/v1/parent/share-links",
        headers={"Authorization": f"Bearer {token1}"},
        json={"device_id": "geosketch-01", "label": "Child"},
    )
    token2 = create_parent(client, "share-secret-for-tests-123456789", monkeypatch)
    denied = client.delete(
        f"/api/v1/parent/share-links/{first.json()['id']}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert denied.status_code == 404
    revoked = client.delete(
        f"/api/v1/parent/share-links/{first.json()['id']}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert revoked.status_code == 204
    assert client.get(f"/api/v1/live/{first.json()['token']}").status_code == 404
    from app.core.config import reset_settings_cache

    reset_settings_cache()


def test_unknown_and_expired_links_share_the_same_not_found(client, monkeypatch):
    from datetime import timedelta

    from app.core.config import reset_settings_cache
    from app.database.session import SessionLocal
    from app.models.parent import ShareLink
    from app.utils.time import utcnow

    token = create_parent(client, "share-secret-for-tests-123456789", monkeypatch)
    created = client.post(
        "/api/v1/parent/share-links",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_id": "geosketch-01", "label": "Child"},
    ).json()
    with SessionLocal() as db:
        link = db.scalar(select(ShareLink).where(ShareLink.id == created["id"]))
        link.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    expired = client.get(f"/api/v1/live/{created['token']}")
    unknown = client.get("/api/v1/live/not-a-real-link")
    assert expired.status_code == unknown.status_code == 404
    assert expired.json() == unknown.json()
    reset_settings_cache()
