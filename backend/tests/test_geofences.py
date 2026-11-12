from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select


def test_two_fix_hysteresis_emits_one_arrived_and_left(client, monkeypatch):
    from app.core.config import reset_settings_cache
    from app.database.session import SessionLocal
    from app.models.parent import AlertEvent, Geofence, Parent
    from app.services.safe_trip_service import evaluate_point

    monkeypatch.setenv("GEOSKETCH_AUTH_SECRET", "geofence-test-secret-123456789")
    reset_settings_cache()
    with SessionLocal() as db:
        parent = Parent(email=f"zone-{uuid.uuid4().hex}@example.test", password_hash="salt:hash")
        db.add(parent)
        db.flush()
        zone = Geofence(
            parent_id=parent.id,
            device_id="geosketch-01",
            name="Home",
            latitude=18.5204,
            longitude=73.8567,
            radius_m=100,
            active=True,
        )
        db.add(zone)
        db.commit()
        assert evaluate_point(db, "geosketch-01", 18.5220, 73.8567) == []
        assert evaluate_point(db, "geosketch-01", 18.5204, 73.8567) == []
        arrived = evaluate_point(db, "geosketch-01", 18.5204, 73.8567)
        assert [x.type for x in arrived] == ["arrived"]
        assert evaluate_point(db, "geosketch-01", 18.5220, 73.8567) == []
        left = evaluate_point(db, "geosketch-01", 18.5220, 73.8567)
        assert [x.type for x in left] == ["left"]
        assert (
            len(db.scalars(select(AlertEvent).where(AlertEvent.parent_id == parent.id)).all()) == 2
        )
    reset_settings_cache()


def test_parent_geofence_crud_and_isolation(client, monkeypatch):
    import uuid

    from app.core.config import reset_settings_cache

    monkeypatch.setenv("GEOSKETCH_AUTH_SECRET", "geofence-crud-test-secret-123456")
    reset_settings_cache()
    first = client.post(
        "/api/v1/parent/register",
        json={"email": f"f-{uuid.uuid4().hex}@example.test", "password": "password123"},
    ).json()["token"]
    second = client.post(
        "/api/v1/parent/register",
        json={"email": f"s-{uuid.uuid4().hex}@example.test", "password": "password123"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {first}"}
    made = client.post(
        "/api/v1/parent/geofences",
        headers=headers,
        json={
            "device_id": "geosketch-01",
            "name": "School",
            "latitude": 18.52,
            "longitude": 73.85,
            "radius_m": 150,
        },
    )
    assert made.status_code == 201
    zone = made.json()
    assert client.get("/api/v1/parent/geofences", headers=headers).json()[0]["id"] == zone["id"]
    changed = client.patch(
        f"/api/v1/parent/geofences/{zone['id']}", headers=headers, json={"name": "New school"}
    )
    assert changed.json()["name"] == "New school"
    denied = client.delete(
        f"/api/v1/parent/geofences/{zone['id']}", headers={"Authorization": f"Bearer {second}"}
    )
    assert denied.status_code == 404
    assert client.get("/api/v1/parent/alerts", headers=headers).status_code == 200
    assert (
        client.delete(f"/api/v1/parent/geofences/{zone['id']}", headers=headers).status_code == 204
    )
    reset_settings_cache()


def test_offline_alert_is_once_then_back_online(client, hardware_journey, monkeypatch):
    import uuid
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.config import reset_settings_cache
    from app.database.session import SessionLocal
    from app.models.device import Device
    from app.models.journey import Journey
    from app.models.parent import AlertEvent, Parent, ShareLink
    from app.services.offline_watcher import check_offline_once
    from app.utils.time import utcnow

    monkeypatch.setenv("GEOSKETCH_OFFLINE_ALERT_MIN_MINUTES", "5")
    reset_settings_cache()
    with SessionLocal() as db:
        parent = Parent(email=f"offline-{uuid.uuid4().hex}@example.test", password_hash="x")
        db.add(parent)
        db.flush()
        db.add(
            ShareLink(
                parent_id=parent.id,
                device_id="geosketch-01",
                label="Child",
                token_hash=uuid.uuid4().hex * 2,
                expires_at=utcnow() + timedelta(days=1),
            )
        )
        db.get(Journey, hardware_journey["id"]).device_id = "geosketch-01"
        device = db.scalar(select(Device).where(Device.device_id == "geosketch-01"))
        device.last_seen_at = utcnow() - timedelta(minutes=10)
        db.commit()
    check_offline_once()
    check_offline_once()
    with SessionLocal() as db:
        events = db.scalars(
            select(AlertEvent)
            .where(AlertEvent.parent_id == parent.id)
            .order_by(AlertEvent.occurred_at)
        ).all()
        assert [e.type for e in events] == ["offline"]
        db.scalar(select(Device).where(Device.device_id == "geosketch-01")).last_seen_at = utcnow()
        db.commit()
    check_offline_once()
    with SessionLocal() as db:
        events = db.scalars(
            select(AlertEvent)
            .where(AlertEvent.parent_id == parent.id)
            .order_by(AlertEvent.occurred_at)
        ).all()
        assert [e.type for e in events] == ["offline", "back_online"]
    reset_settings_cache()


def test_sos_payload_and_alert_are_deduplicated(client, monkeypatch):
    import uuid
    from datetime import timedelta

    from pydantic import ValidationError
    from sqlalchemy import select

    from app.core.config import reset_settings_cache
    from app.database.session import SessionLocal
    from app.models.parent import AlertEvent, Parent, ShareLink
    from app.schemas.gps import GPSPointIn
    from app.services.safe_trip_service import safely_create_sos_alert
    from app.utils.time import utcnow

    assert GPSPointIn(latitude=18.5, longitude=73.8, sos=True).sos is True
    with pytest.raises(ValidationError):
        GPSPointIn(latitude=18.5, longitude=73.8, unknown=True)
    monkeypatch.setenv("GEOSKETCH_AUTH_SECRET", "sos-test-secret-123456789")
    reset_settings_cache()
    with SessionLocal() as db:
        parent = Parent(email=f"sos-{uuid.uuid4().hex}@example.test", password_hash="x")
        db.add(parent)
        db.flush()
        db.add(
            ShareLink(
                parent_id=parent.id,
                device_id="geosketch-01",
                label="Child",
                token_hash=uuid.uuid4().hex * 2,
                expires_at=utcnow() + timedelta(days=1),
            )
        )
        db.commit()
        assert len(safely_create_sos_alert(db, "geosketch-01")) >= 1
        assert safely_create_sos_alert(db, "geosketch-01") == []
        events = db.scalars(
            select(AlertEvent).where(AlertEvent.parent_id == parent.id, AlertEvent.type == "sos")
        ).all()
        assert len(events) == 1
    reset_settings_cache()
