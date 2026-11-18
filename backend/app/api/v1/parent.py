from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_parent
from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError, ValidationFailed
from app.database.session import get_db
from app.models.device import Device
from app.models.gps_point import GPSPoint
from app.models.parent import Geofence, Parent, ShareLink
from app.services.device_service import is_live
from app.services.geo import haversine_m
from app.services.parent_auth import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    issue_session,
    verify_password,
)
from app.utils.time import utc_iso, utcnow

router = APIRouter(tags=["Family Safe-Trip"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class ShareCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    ttl_hours: int | None = Field(default=None, ge=1, le=168)


def configured():
    if not get_settings().auth_secret:
        raise AppError(
            "Parent features are not configured.", code="auth_not_configured", status_code=503
        )


def clean_email(value):
    value = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValidationFailed("Enter a valid email address.", code="invalid_email")
    return value


@router.post("/parent/register")
def register(body: Credentials, db: Session = Depends(get_db)):
    configured()
    if not get_settings().allow_parent_registration:
        raise AppError(
            "Parent registration is disabled.", code="registration_disabled", status_code=403
        )
    email = clean_email(body.email)
    if db.scalar(select(Parent).where(Parent.email == email)):
        raise ConflictError("Account already exists.", code="email_exists")
    p = Parent(email=email, password_hash=hash_password(body.password))
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"token": issue_session(p), "parent": {"id": p.id, "email": p.email}}


@router.post("/parent/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    configured()
    email = clean_email(body.email)
    p = db.scalar(select(Parent).where(Parent.email == email))
    if p is None:
        verify_password(body.password, DUMMY_PASSWORD_HASH)
        raise AppError("Email or password is incorrect.", code="login_failed", status_code=401)
    if not verify_password(body.password, p.password_hash):
        raise AppError("Email or password is incorrect.", code="login_failed", status_code=401)
    return {"token": issue_session(p), "parent": {"id": p.id, "email": p.email}}


@router.get("/parent/me")
def me(p: Parent = Depends(current_parent)):
    return {"id": p.id, "email": p.email, "telegram_chat_id": p.telegram_chat_id}


class MeUpdate(BaseModel):
    telegram_chat_id: str | None = Field(default=None, max_length=128)


@router.patch("/parent/me")
def update_me(body: MeUpdate, p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    p.telegram_chat_id = body.telegram_chat_id
    db.commit()
    return {"id": p.id, "email": p.email, "telegram_chat_id": p.telegram_chat_id}


@router.post("/parent/share-links")
def create_share(
    body: ShareCreate, p: Parent = Depends(current_parent), db: Session = Depends(get_db)
):
    configured()
    s = get_settings()
    d = db.scalar(select(Device).where(Device.device_id == body.device_id))
    if d is None:
        raise NotFoundError("Device not found.", code="device_not_found")
    ttl = body.ttl_hours or s.share_default_ttl_hours
    if ttl > s.share_max_ttl_hours:
        raise ValidationFailed("Expiry exceeds configured maximum.", code="ttl_too_long")
    token = secrets.token_urlsafe(32)
    expiry = utcnow() + timedelta(hours=ttl)
    link = ShareLink(
        parent_id=p.id,
        device_id=d.device_id,
        label=body.label.strip(),
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=expiry,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return {
        "id": link.id,
        "url": f"{s.public_base_url.rstrip('/')}/live/{token}",
        "token": token,
        "expires_at": utc_iso(expiry),
    }


@router.get("/parent/share-links")
def list_shares(p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    links = db.scalars(
        select(ShareLink).where(ShareLink.parent_id == p.id).order_by(ShareLink.created_at.desc())
    ).all()
    return [
        {
            "id": x.id,
            "device_id": x.device_id,
            "label": x.label,
            "expires_at": utc_iso(x.expires_at),
            "revoked_at": utc_iso(x.revoked_at),
            "created_at": utc_iso(x.created_at),
        }
        for x in links
    ]


@router.delete("/parent/share-links/{link_id}", status_code=204)
def revoke_share(link_id: int, p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    link = db.scalar(select(ShareLink).where(ShareLink.id == link_id, ShareLink.parent_id == p.id))
    if link is None:
        raise NotFoundError("Share link not found.", code="share_not_found")
    link.revoked_at = utcnow()
    db.commit()


@router.get("/live/{token}")
def live_view(token: str, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    digest = hashlib.sha256(token.encode()).hexdigest()
    link = db.scalar(select(ShareLink).where(ShareLink.token_hash == digest))
    now = utcnow()
    if (
        link is None
        or not hmac.compare_digest(link.token_hash, digest)
        or link.revoked_at
        or link.expires_at <= now
    ):
        raise NotFoundError("Share link not found.", code="not_found")
    d = db.scalar(select(Device).where(Device.device_id == link.device_id))
    if d is None:
        raise NotFoundError("Share link not found.", code="not_found")
    link.last_viewed_at = now
    db.commit()
    cutoff = now - timedelta(minutes=60)
    points = list(
        reversed(
            db.scalars(
                select(GPSPoint)
                .where(
                    GPSPoint.device_id == d.device_id,
                    GPSPoint.source == "hardware",
                    GPSPoint.is_plausible.is_(True),
                    GPSPoint.server_timestamp >= cutoff,
                )
                .order_by(GPSPoint.server_timestamp.desc())
                .limit(200)
            ).all()
        )
    )
    zones = db.scalars(
        select(Geofence).where(
            Geofence.parent_id == link.parent_id,
            Geofence.device_id == d.device_id,
            Geofence.active.is_(True),
        )
    ).all()
    latest = points[-1] if points else None
    latitude = latest.latitude if latest else d.last_latitude
    longitude = latest.longitude if latest else d.last_longitude
    satellites = latest.satellites if latest else d.last_satellites
    age = (now - d.last_seen_at).total_seconds() if d.last_seen_at else None
    state = "online" if is_live(d, now=now) else "stale" if age is not None and age <= 300 else "offline"
    return {
        "label": link.label,
        "status": state,
        "last_seen": utc_iso(d.last_seen_at),
        "position": {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy_hint": "GPS estimate (~2.5 m)",
            "satellites": satellites,
        }
        if latitude is not None and longitude is not None
        else None,
        "trail": [
            {
                "latitude": x.latitude,
                "longitude": x.longitude,
                "timestamp": utc_iso(x.server_timestamp),
            }
            for x in points
        ],
        "zones": [
            {
                "name": z.name,
                "latitude": z.latitude,
                "longitude": z.longitude,
                "radius_m": z.radius_m,
                "inside": (
                    haversine_m(latitude, longitude, z.latitude, z.longitude) <= z.radius_m
                    if latitude is not None and longitude is not None
                    else None
                ),
            }
            for z in zones
        ],
        "expires_at": utc_iso(link.expires_at),
    }
