"""Opt-in offline alert poller. Paused/stopped journeys are ignored."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.device import Device
from app.models.journey import Journey, JourneyStatus
from app.models.parent import AlertEvent, Geofence, ShareLink
from app.services.notifier import deliver
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def check_offline_once():
    settings = get_settings()
    now = utcnow()
    threshold = timedelta(minutes=settings.offline_alert_min_minutes)
    with SessionLocal() as db:
        devices = db.scalars(
            select(Device)
            .join(Journey, Journey.device_id == Device.device_id)
            .where(Journey.source == "hardware", Journey.status == JourneyStatus.RECORDING.value)
            .distinct()
        ).all()
        for device in devices:
            parents = set(
                db.scalars(
                    select(ShareLink.parent_id).where(
                        ShareLink.device_id == device.device_id,
                        ShareLink.revoked_at.is_(None),
                        ShareLink.expires_at > now,
                    )
                ).all()
            )
            parents.update(
                db.scalars(
                    select(Geofence.parent_id).where(Geofence.device_id == device.device_id)
                ).all()
            )
            if device.last_seen_at is None:
                continue
            is_offline = now - device.last_seen_at > threshold
            for pid in parents:
                latest = db.scalar(
                    select(AlertEvent)
                    .where(
                        AlertEvent.device_id == device.device_id,
                        AlertEvent.parent_id == pid,
                        AlertEvent.type.in_(["offline", "back_online"]),
                    )
                    .order_by(AlertEvent.occurred_at.desc())
                    .limit(1)
                )
                if is_offline and (latest is None or latest.type != "offline"):
                    event = AlertEvent(
                        device_id=device.device_id,
                        parent_id=pid,
                        type="offline",
                        message=f"Tracker offline: no GPS update for {settings.offline_alert_min_minutes} minutes",
                    )
                elif not is_offline and latest is not None and latest.type == "offline":
                    event = AlertEvent(
                        device_id=device.device_id,
                        parent_id=pid,
                        type="back_online",
                        message="Tracker is back online and sending GPS updates",
                    )
                else:
                    continue
                db.add(event)
                db.commit()
                db.refresh(event)
                deliver(db, event)


async def offline_watcher():
    settings = get_settings()
    while True:
        await asyncio.to_thread(check_offline_once)
        await asyncio.sleep(max(5, settings.offline_check_seconds))
