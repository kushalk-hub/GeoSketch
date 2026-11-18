from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_parent
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError, ValidationFailed
from app.database.session import get_db
from app.models.device import Device
from app.models.parent import AlertEvent, Geofence, Parent
from app.utils.time import utc_iso

router = APIRouter(tags=["Safe zones and alerts"])


class FenceIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(ge=50, le=5000)
    active: bool = True


class FencePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_m: int | None = Field(default=None, ge=50, le=5000)
    active: bool | None = None


def out(x):
    return {
        "id": x.id,
        "device_id": x.device_id,
        "name": x.name,
        "latitude": x.latitude,
        "longitude": x.longitude,
        "radius_m": x.radius_m,
        "active": x.active,
        "created_at": utc_iso(x.created_at),
    }


def owned(fid, parent, db):
    x = db.scalar(select(Geofence).where(Geofence.id == fid, Geofence.parent_id == parent.id))
    if x is None:
        raise NotFoundError("Safe zone not found.", code="geofence_not_found")
    return x


@router.post("/parent/geofences", status_code=201)
def create_zone(body: FenceIn, p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    if db.scalar(select(Device).where(Device.device_id == body.device_id)) is None:
        raise NotFoundError("Device not found.", code="device_not_found")
    x = Geofence(parent_id=p.id, **body.model_dump())
    db.add(x)
    db.commit()
    db.refresh(x)
    return out(x)


@router.get("/parent/geofences")
def list_zones(p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    return [
        out(x)
        for x in db.scalars(
            select(Geofence).where(Geofence.parent_id == p.id).order_by(Geofence.id)
        ).all()
    ]


@router.patch("/parent/geofences/{fid}")
def patch_zone(
    fid: int, body: FencePatch, p: Parent = Depends(current_parent), db: Session = Depends(get_db)
):
    x = owned(fid, p, db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(x, k, v)
    db.commit()
    db.refresh(x)
    return out(x)


@router.delete("/parent/geofences/{fid}", status_code=204)
def delete_zone(fid: int, p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    db.delete(owned(fid, p, db))
    db.commit()


@router.get("/parent/alerts")
def list_alerts(
    limit: int = 50,
    offset: int = 0,
    p: Parent = Depends(current_parent),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(AlertEvent)
        .where(AlertEvent.parent_id == p.id)
        .order_by(AlertEvent.occurred_at.desc())
        .offset(max(0, offset))
        .limit(min(200, max(1, limit)))
    ).all()
    return [
        {
            "id": x.id,
            "device_id": x.device_id,
            "type": x.type,
            "geofence_id": x.geofence_id,
            "message": x.message,
            "occurred_at": utc_iso(x.occurred_at),
            "delivered_at": utc_iso(x.delivered_at),
            "delivery_error": x.delivery_error,
        }
        for x in rows
    ]


@router.post("/parent/alerts/{aid}/ack", status_code=204)
def ack_alert(aid: int, p: Parent = Depends(current_parent), db: Session = Depends(get_db)):
    x = db.scalar(select(AlertEvent).where(AlertEvent.id == aid, AlertEvent.parent_id == p.id))
    if x is None:
        raise NotFoundError("Alert not found.", code="alert_not_found")


class TelegramTestIn(BaseModel):
    chat_id: str | None = None


@router.post("/parent/telegram/test")
def test_telegram(
    body: TelegramTestIn,
    p: Parent = Depends(current_parent),
    db: Session = Depends(get_db),
):
    target_chat_id = (body.chat_id or "").strip() or p.telegram_chat_id
    if not target_chat_id:
        raise ValidationFailed("Please enter or save a Telegram Chat ID first.", code="no_chat_id")
    token = get_settings().telegram_bot_token
    if not token:
        raise AppError(
            "Telegram bot token is not configured in backend/.env (GEOSKETCH_TELEGRAM_BOT_TOKEN).",
            code="telegram_not_configured",
            status_code=400,
        )
    text = "🔔 GeoSketch Test Notification: Safe-Trip alerts and geofencing notifications are successfully connected!"
    data = urllib.parse.urlencode({"chat_id": target_chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode())
            if not res_data.get("ok"):
                raise RuntimeError(res_data.get("description", "Telegram API returned error"))
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode()
        try:
            err_json = json.loads(err_msg)
            err_desc = err_json.get("description", err_msg)
        except Exception:
            err_desc = err_msg
        raise AppError(f"Telegram API: {err_desc}", code="telegram_failed", status_code=400)
    except Exception as exc:
        raise AppError(f"Telegram delivery failed: {str(exc)}", code="telegram_failed", status_code=400)
    return {"ok": True, "message": "Test notification delivered to your Telegram!"}
