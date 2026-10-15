"""Service metadata: health check, system info and the artwork style catalogue."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.artwork.styles import all_styles
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.models.device import Device
from app.models.journey import Journey
from app.utils.time import utcnow

router = APIRouter(tags=["Meta"])


@router.get("/health", summary="Health check")
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> Dict:
    """Cheap readiness probe used by the frontend and by docker-compose."""
    devices = db.scalar(select(func.count(Device.id))) or 0
    journeys = db.scalar(select(func.count(Journey.id))) or 0
    return {
        "status": "ok",
        "service": settings.app_name,
        "time": utcnow().isoformat() + "Z",
        "database": "sqlite" if settings.is_sqlite else "sql",
        "devices": int(devices),
        "journeys": int(journeys),
        "device_offline_after_seconds": settings.device_offline_after_seconds,
        "artwork_styles": [style["id"] for style in all_styles()],
    }


@router.get(
    "/artwork/styles",
    summary="Available artwork styles",
    description="Catalogue consumed by the artwork studio to build the style picker.",
)
def artwork_styles() -> List[Dict]:
    return all_styles()
