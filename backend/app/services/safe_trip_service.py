"""Safe-zone evaluation after successful hardware storage."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.parent import AlertEvent, Geofence, GeofenceState
from app.services.geo import haversine_m
from app.utils.time import utcnow

logger = logging.getLogger(__name__)
HYSTERESIS_M = 20
REQUIRED_FIXES = 2


def evaluate_point(
    db: Session,
    device_id: str,
    latitude: float,
    longitude: float,
    *,
    satellites: int | None = None,
    hdop: float | None = None,
):
    zones = db.scalars(
        select(Geofence).where(Geofence.device_id == device_id, Geofence.active.is_(True))
    ).all()
    created = []
    for zone in zones:
        if (satellites is not None and satellites < 4) or (hdop is not None and hdop > 8):
            continue
        distance = haversine_m(latitude, longitude, zone.latitude, zone.longitude)
        candidate = (
            True
            if distance <= zone.radius_m
            else False
            if distance > zone.radius_m + HYSTERESIS_M
            else None
        )
        state = db.get(GeofenceState, zone.id)
        if state is None:
            db.add(GeofenceState(geofence_id=zone.id, inside=candidate, updated_at=utcnow()))
            continue
        if candidate is None or candidate == state.inside:
            state.pending_inside = None
            state.pending_count = 0
            state.updated_at = utcnow()
            continue
        if candidate != state.pending_inside:
            state.pending_inside = candidate
            state.pending_count = 1
        else:
            state.pending_count += 1
        if state.pending_count < REQUIRED_FIXES:
            continue
        old = state.inside
        state.inside = candidate
        state.pending_inside = None
        state.pending_count = 0
        state.updated_at = utcnow()
        if candidate is True or old is True:
            event_type = "arrived" if candidate else "left"
            event = AlertEvent(
                device_id=device_id,
                parent_id=zone.parent_id,
                type=event_type,
                geofence_id=zone.id,
                message=f"{zone.name}: {'arrived' if candidate else 'left'} safe zone",
            )
            db.add(event)
            created.append(event)
    db.commit()
    from app.services.notifier import deliver

    for event in created:
        deliver(db, event)
    return created


def safely_evaluate_point(db, device_id, latitude, longitude, satellites=None, hdop=None):
    try:
        return evaluate_point(db, device_id, latitude, longitude, satellites=satellites, hdop=hdop)
    except Exception:
        db.rollback()
        logger.exception("Safe-zone evaluation failed for %s", device_id)
        return []


def safely_create_sos_alert(db, device_id: str):
    """Create one SOS alert per parent/device within a 60 second window."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.models.parent import ShareLink
    from app.utils.time import utcnow

    try:
        now = utcnow()
        parents = set(
            db.scalars(
                select(ShareLink.parent_id).where(
                    ShareLink.device_id == device_id,
                    ShareLink.revoked_at.is_(None),
                    ShareLink.expires_at > now,
                )
            ).all()
        )
        parents.update(
            db.scalars(select(Geofence.parent_id).where(Geofence.device_id == device_id)).all()
        )
        events = []
        for parent_id in parents:
            recent = db.scalar(
                select(AlertEvent.id)
                .where(
                    AlertEvent.device_id == device_id,
                    AlertEvent.parent_id == parent_id,
                    AlertEvent.type == "sos",
                    AlertEvent.occurred_at >= now - timedelta(seconds=60),
                )
                .limit(1)
            )
            if recent is None:
                event = AlertEvent(
                    device_id=device_id,
                    parent_id=parent_id,
                    type="sos",
                    message="SOS button pressed on the tracker",
                    occurred_at=now,
                )
                db.add(event)
                events.append(event)
        db.commit()
        from app.services.notifier import deliver

        for event in events:
            deliver(db, event)
        return events
    except Exception:
        db.rollback()
        logger.exception("SOS alert processing failed for %s", device_id)
        return []
