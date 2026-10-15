"""Device service: bootstrap, authentication and status reporting.

Connection state is *derived*, never guessed: a device is "live" only when a GPS
point arrived within ``device_offline_after_seconds``.  The dashboard therefore
shows the last successful update time instead of pretending to have live data.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AuthError, NotFoundError
from app.core.security import hash_api_key, verify_api_key
from app.models.device import Device, DeviceStatus
from app.models.gps_point import GPSPoint
from app.models.journey import Journey, JourneyStatus
from app.schemas.device import DeviceOut, DeviceStatusOut
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def sync_devices_from_settings(db: Session, settings: Optional[Settings] = None) -> int:
    """Create/refresh device rows from ``GEOSKETCH_DEVICE_KEYS``.

    Runs on startup so a fresh database always knows the configured trackers.
    Existing rows keep their history and only have the key digest refreshed.
    """
    settings = settings or get_settings()
    created = 0
    for device_id, api_key in settings.device_key_map.items():
        device = db.scalar(select(Device).where(Device.device_id == device_id))
        digest = hash_api_key(api_key)
        if device is None:
            device = Device(
                device_id=device_id,
                name=f"GeoSketch {device_id}",
                api_key_hash=digest,
                owner=settings.default_owner,
                first_seen_at=utcnow(),
                connection_status=DeviceStatus.UNKNOWN.value,
            )
            db.add(device)
            created += 1
        elif device.api_key_hash != digest:
            device.api_key_hash = digest
    db.commit()
    return created


def get_device(db: Session, device_id: str) -> Optional[Device]:
    return db.scalar(select(Device).where(Device.device_id == device_id))


def require_device(db: Session, device_id: Optional[str], api_key: Optional[str]) -> Device:
    """Authenticate a physical device from its id + API key."""
    if not device_id:
        raise AuthError("X-Device-Id header is required", code="missing_device_id")
    if not api_key:
        raise AuthError("X-Device-Key header is required", code="missing_device_key")

    device = get_device(db, device_id)
    # Same error for unknown device and wrong key: do not help enumerating ids.
    if device is None or not verify_api_key(api_key, device.api_key_hash):
        logger.warning("Rejected device credentials for device_id=%s", device_id)
        raise AuthError("Unknown device or invalid API key", code="invalid_device_credentials")
    return device


def register_device(
    db: Session,
    *,
    device_id: str,
    name: str,
    firmware_version: Optional[str] = None,
    owner: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Device:
    """Create or update a device row (used by the admin/setup endpoint)."""
    settings = get_settings()
    device = get_device(db, device_id)
    if device is None:
        if not api_key:
            raise AuthError(
                "an api_key is required when registering a new device",
                code="missing_device_key",
            )
        device = Device(
            device_id=device_id,
            name=name,
            api_key_hash=hash_api_key(api_key),
            owner=owner or settings.default_owner,
            first_seen_at=utcnow(),
            connection_status=DeviceStatus.UNKNOWN.value,
        )
        db.add(device)
    device.name = name or device.name
    if firmware_version:
        device.firmware_version = firmware_version
    db.commit()
    db.refresh(device)
    return device


def is_live(device: Device, settings: Optional[Settings] = None, now: Optional[datetime] = None) -> bool:
    settings = settings or get_settings()
    if device.last_seen_at is None:
        return False
    now = now or utcnow()
    return (now - device.last_seen_at).total_seconds() <= settings.device_offline_after_seconds


def mark_seen(
    db: Session,
    device: Device,
    *,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    satellites: Optional[int] = None,
    fix_at: Optional[datetime] = None,
    when: Optional[datetime] = None,
    firmware_version: Optional[str] = None,
) -> Device:
    """Record that the device just delivered a valid fix."""
    when = when or utcnow()
    device.last_seen_at = when
    device.connection_status = DeviceStatus.ONLINE.value
    device.points_received = (device.points_received or 0) + 1
    if latitude is not None and longitude is not None:
        device.last_latitude = latitude
        device.last_longitude = longitude
        device.last_fix_at = fix_at or when
    if satellites is not None:
        device.last_satellites = satellites
    if firmware_version:
        device.firmware_version = firmware_version
    return device


def refresh_connection_status(db: Session, devices: List[Device]) -> None:
    """Persist the derived online/offline state (keeps DB reports accurate)."""
    settings = get_settings()
    now = utcnow()
    changed = False
    for device in devices:
        status = (
            DeviceStatus.ONLINE.value
            if is_live(device, settings, now)
            else (
                DeviceStatus.OFFLINE.value
                if device.last_seen_at is not None
                else DeviceStatus.UNKNOWN.value
            )
        )
        if device.connection_status != status:
            device.connection_status = status
            changed = True
    if changed:
        db.commit()


def to_device_out(device: Device, settings: Optional[Settings] = None) -> DeviceOut:
    settings = settings or get_settings()
    now = utcnow()
    live = is_live(device, settings, now)
    seconds = None
    if device.last_seen_at is not None:
        seconds = max(0.0, (now - device.last_seen_at).total_seconds())
    return DeviceOut(
        device_id=device.device_id,
        name=device.name,
        connection_status=DeviceStatus.ONLINE.value if live else device.connection_status,
        firmware_version=device.firmware_version,
        last_seen_at=device.last_seen_at,
        last_latitude=device.last_latitude,
        last_longitude=device.last_longitude,
        last_satellites=device.last_satellites,
        last_fix_at=device.last_fix_at,
        points_received=device.points_received or 0,
        is_live=live,
        seconds_since_last_seen=seconds,
    )


def list_devices(db: Session, owner: Optional[str] = None) -> List[DeviceOut]:
    settings = get_settings()
    statement = select(Device).order_by(Device.device_id)
    if owner:
        statement = statement.where(Device.owner == owner)
    devices = list(db.scalars(statement))
    refresh_connection_status(db, devices)
    return [to_device_out(device, settings) for device in devices]


def device_status(
    db: Session, *, device_id: str, owner: Optional[str] = None
) -> DeviceStatusOut:
    settings = get_settings()
    device = get_device(db, device_id)
    if device is None:
        raise NotFoundError(f"device '{device_id}' is not registered", code="device_not_found")
    if owner and device.owner != owner:
        raise NotFoundError(f"device '{device_id}' is not registered", code="device_not_found")

    refresh_connection_status(db, [device])
    latest = db.scalar(
        select(GPSPoint)
        .where(GPSPoint.device_id == device.device_id, GPSPoint.is_plausible.is_(True))
        .order_by(GPSPoint.server_timestamp.desc(), GPSPoint.id.desc())
        .limit(1)
    )
    active = db.scalar(
        select(Journey)
        .where(
            Journey.device_id == device.device_id,
            Journey.status.in_([JourneyStatus.RECORDING.value, JourneyStatus.PAUSED.value]),
        )
        .order_by(Journey.created_at.desc())
        .limit(1)
    )

    from app.schemas.gps import GPSPointOut

    return DeviceStatusOut(
        device=to_device_out(device, settings),
        connected=is_live(device, settings),
        active_journey_id=active.id if active else None,
        latest_point=GPSPointOut.model_validate(latest) if latest else None,
        offline_after_seconds=settings.device_offline_after_seconds,
        server_time=utcnow(),
    )
