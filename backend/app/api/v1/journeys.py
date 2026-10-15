"""Journey endpoints: recording controls, statistics and route artwork."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import COMMON_ERROR_RESPONSES, current_owner
from app.core.config import Settings, get_settings
from app.core.errors import ValidationFailed
from app.database.session import get_db
from app.schemas.artwork import ArtworkOut, ArtworkPreview, ArtworkRequest
from app.schemas.common import MessageResponse
from app.schemas.gps import GPSPointBulkIn, GPSPointBulkResponse
from app.schemas.journey import (
    JourneyCreate,
    JourneyDetail,
    JourneyOut,
    JourneyStatistics,
    JourneyUpdate,
)
from app.services import artwork_service, journey_service
from app.services.device_service import list_devices

router = APIRouter(prefix="/journeys", tags=["Journeys"], responses=COMMON_ERROR_RESPONSES)


def _get(db: Session, journey_id: int, owner: str):
    return journey_service.get_journey(db, journey_id, owner=owner)


@router.post(
    "",
    response_model=JourneyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create (and start) a new journey",
)
def create_journey(
    payload: JourneyCreate,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> JourneyOut:
    journey = journey_service.create_journey(db, owner=owner, payload=payload)
    return journey_service.to_journey_out(journey, artwork_count=0)


@router.get("", response_model=List[JourneyOut], summary="List journeys")
def list_journeys(
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    journey_status: Optional[str] = Query(default=None, alias="status"),
    source: Optional[str] = Query(default=None, pattern="^(hardware|demo)$"),
    saved_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[JourneyOut]:
    journeys, _total = journey_service.list_journeys(
        db,
        owner=owner,
        status=journey_status,
        source=source,
        saved_only=saved_only,
        limit=limit,
        offset=offset,
    )
    return [journey_service.to_journey_out(journey) for journey in journeys]


@router.get("/{journey_id}", response_model=JourneyDetail, summary="Journey with its GPS points")
def get_journey(
    journey_id: int,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> JourneyDetail:
    return journey_service.to_journey_detail(_get(db, journey_id, owner))


@router.patch("/{journey_id}", response_model=JourneyOut, summary="Rename / annotate a journey")
def update_journey(
    journey_id: int,
    payload: JourneyUpdate,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> JourneyOut:
    journey = journey_service.update_journey(db, _get(db, journey_id, owner), payload)
    return journey_service.to_journey_out(journey)


@router.delete("/{journey_id}", response_model=MessageResponse, summary="Clear an unsaved journey")
def delete_journey(
    journey_id: int,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> MessageResponse:
    journey = _get(db, journey_id, owner)
    artworks = artwork_service.list_artworks(db, journey.id)
    artwork_service.delete_artwork_files(artworks)
    journey_service.delete_journey(db, journey)
    return MessageResponse(message="Journey cleared.", detail=f"journey_id={journey_id}")


# --- recording controls ----------------------------------------------------
@router.post("/{journey_id}/start", response_model=JourneyOut, summary="Start recording")
def start_journey(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> JourneyOut:
    return journey_service.to_journey_out(
        journey_service.start_journey(db, _get(db, journey_id, owner))
    )


@router.post("/{journey_id}/pause", response_model=JourneyOut, summary="Pause recording")
def pause_journey(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> JourneyOut:
    return journey_service.to_journey_out(
        journey_service.pause_journey(db, _get(db, journey_id, owner))
    )


@router.post("/{journey_id}/resume", response_model=JourneyOut, summary="Resume recording")
def resume_journey(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> JourneyOut:
    return journey_service.to_journey_out(
        journey_service.resume_journey(db, _get(db, journey_id, owner))
    )


@router.post("/{journey_id}/stop", response_model=JourneyOut, summary="Stop / finish recording")
def stop_journey(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> JourneyOut:
    return journey_service.to_journey_out(
        journey_service.stop_journey(db, _get(db, journey_id, owner))
    )


@router.post(
    "/{journey_id}/finish",
    response_model=JourneyOut,
    summary="Finish the recording session (alias of /stop)",
)
def finish_journey(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> JourneyOut:
    return journey_service.to_journey_out(
        journey_service.stop_journey(db, _get(db, journey_id, owner))
    )


@router.post("/{journey_id}/save", response_model=JourneyOut, summary="Save the journey")
def save_journey(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> JourneyOut:
    return journey_service.to_journey_out(
        journey_service.save_journey(db, _get(db, journey_id, owner))
    )


# --- statistics -----------------------------------------------------------
@router.get(
    "/{journey_id}/statistics",
    response_model=JourneyStatistics,
    summary="Journey statistics (GPS estimates)",
)
def journey_statistics(
    journey_id: int,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> JourneyStatistics:
    journey = _get(db, journey_id, owner)
    return journey_service.compute_statistics(db, journey, settings)


# --- bulk points (demo replay) -------------------------------------------
@router.post(
    "/{journey_id}/points",
    response_model=GPSPointBulkResponse,
    summary="Bulk upload points (demo replay only)",
    description=(
        "Used by DEMO MODE to replay a sample route. Real device data must go "
        "through `POST /api/v1/gps/points` with device credentials, so simulated "
        "points can never be mixed into a hardware journey."
    ),
)
def add_points(
    journey_id: int,
    payload: GPSPointBulkIn,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> GPSPointBulkResponse:
    if payload.source == "hardware":
        raise ValidationFailed(
            "hardware points must be posted to /api/v1/gps/points with device credentials",
            code="hardware_source_not_allowed",
        )
    journey = _get(db, journey_id, owner)
    if journey.source != "demo":
        raise ValidationFailed(
            "demo points can only be added to a journey whose source is 'demo'",
            code="source_mismatch",
            details={"journey_id": journey.id, "source": journey.source},
        )
    summary = journey_service.ingest_points(
        db,
        journey=journey,
        payloads=payload.points,
        source=payload.source,
        settings=settings,
    )
    return GPSPointBulkResponse(
        received=summary.received,
        stored=summary.stored,
        duplicates=summary.duplicates,
        rejected=summary.rejected,
        journey_id=journey.id,
    )


# --- artwork --------------------------------------------------------------
@router.post(
    "/{journey_id}/artwork",
    response_model=ArtworkOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate route artwork",
    description=(
        "Renders the selected style from the stored GPS points and stores a PNG "
        "and an SVG export. Set `save: false` to render without persisting."
    ),
)
def generate_artwork(
    journey_id: int,
    payload: ArtworkRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> ArtworkOut:
    journey = _get(db, journey_id, owner)
    artwork, _result = artwork_service.generate_artwork(db, journey, payload, settings=settings)
    return artwork_service.artwork_to_out(artwork, settings=settings)


@router.post(
    "/{journey_id}/artwork/preview",
    response_model=ArtworkPreview,
    summary="Preview artwork (inline SVG, nothing stored)",
)
def preview_artwork(
    journey_id: int,
    payload: ArtworkRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> ArtworkPreview:
    journey = _get(db, journey_id, owner)
    return artwork_service.preview_artwork(db, journey, payload, settings=settings)


@router.get(
    "/{journey_id}/artworks",
    response_model=List[ArtworkOut],
    summary="List generated artworks for a journey",
)
def list_artworks(
    journey_id: int,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> List[ArtworkOut]:
    journey = _get(db, journey_id, owner)
    return [
        artwork_service.artwork_to_out(artwork, settings=settings)
        for artwork in artwork_service.list_artworks(db, journey.id)
    ]


@router.get(
    "/{journey_id}/device",
    summary="Device that recorded this journey (if any)",
)
def journey_device(
    journey_id: int, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> dict:
    journey = _get(db, journey_id, owner)
    if not journey.device_id:
        return {"device_id": None, "device": None, "source": journey.source}
    devices = {device.device_id: device for device in list_devices(db, owner=owner)}
    device = devices.get(journey.device_id)
    return {
        "device_id": journey.device_id,
        "device": device.model_dump(mode="json") if device else None,
        "source": journey.source,
    }
