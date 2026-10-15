"""GPS ingestion, called by the ESP32-C3 firmware over Wi-Fi."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import COMMON_ERROR_RESPONSES, require_device
from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.database.session import get_db
from app.models.device import Device
from app.models.gps_point import PointSource
from app.models.journey import JourneySource
from app.schemas.gps import GPSIngestResponse, GPSPointIn
from app.services.journey_service import (
    get_journey,
    get_or_create_active_journey,
    ingest_point,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gps", tags=["GPS ingestion"], responses=COMMON_ERROR_RESPONSES)


@router.post(
    "/points",
    response_model=GPSIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest one GPS fix from the ESP32-C3",
    description=(
        "Authenticated with the X-Device-Id and X-Device-Key headers. The point is "
        "attached to the device's active journey (created automatically when none "
        "exists) or to the journey referenced by `journey_id`.\n\n"
        "A 2xx response always means 'do not retry this point': duplicates and "
        "points received while recording is paused are reported in the body with "
        "`stored: false`."
    ),
)
def create_gps_point(
    payload: GPSPointIn,
    response: Response,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device),
    settings: Settings = Depends(get_settings),
) -> GPSIngestResponse:
    if payload.device_id and payload.device_id != device.device_id:
        raise ForbiddenError(
            "the device_id in the body does not match the authenticated device",
            code="device_id_mismatch",
        )

    if payload.journey_id is not None:
        journey = get_journey(db, payload.journey_id, owner=device.owner)
        if journey.device_id and journey.device_id != device.device_id:
            raise ForbiddenError(
                "this journey belongs to another device", code="journey_device_mismatch"
            )
    else:
        journey = get_or_create_active_journey(
            db, device_id=device.device_id, owner=device.owner
        )

    if journey.source != JourneySource.HARDWARE.value:
        raise ForbiddenError(
            "this is a demo journey; hardware points can only be recorded into a "
            "journey whose source is 'hardware'",
            code="journey_source_mismatch",
            details={"journey_id": journey.id, "source": journey.source},
        )

    outcome = ingest_point(
        db,
        journey=journey,
        payload=payload,
        device=device,
        source=PointSource.HARDWARE.value,
        settings=settings,
    )

    # 201 when a new row was written, 200 for an idempotent / dropped point.
    response.status_code = (
        status.HTTP_201_CREATED if outcome.stored else status.HTTP_200_OK
    )

    point = outcome.point
    return GPSIngestResponse(
        accepted=outcome.accepted,
        stored=outcome.stored,
        duplicate=outcome.duplicate,
        journey_id=journey.id,
        point_id=point.id if point is not None else None,
        sequence=point.sequence if point is not None else None,
        server_timestamp=point.server_timestamp if point is not None else utcnow(),
        reason=outcome.reason,
        message=outcome.message,
    )
