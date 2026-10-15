"""DEMO MODE endpoints.

Everything here is clearly labelled: routes come from ``data/sample_routes`` and
imported journeys are stored with ``source = "demo"``, so the dashboard can never
present simulated data as a live ESP32-C3 recording.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import COMMON_ERROR_RESPONSES, current_owner
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.schemas.demo import DemoImportRequest, SampleRouteDetail, SampleRouteSummary
from app.schemas.journey import JourneyOut
from app.services import journey_service, sample_service

router = APIRouter(prefix="/demo", tags=["Demo mode"], responses=COMMON_ERROR_RESPONSES)


@router.get("/routes", response_model=List[SampleRouteSummary], summary="List sample routes")
def list_routes(settings: Settings = Depends(get_settings)) -> List[SampleRouteSummary]:
    return sample_service.list_sample_routes(settings)


@router.get(
    "/routes/{route_id}", response_model=SampleRouteDetail, summary="Get one sample route"
)
def get_route(
    route_id: str, settings: Settings = Depends(get_settings)
) -> SampleRouteDetail:
    return sample_service.load_sample_route(route_id, settings)


@router.post(
    "/routes/{route_id}/import",
    response_model=JourneyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Import a sample route as a finished DEMO journey",
)
def import_route(
    route_id: str,
    payload: DemoImportRequest | None = None,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> JourneyOut:
    journey = sample_service.import_sample_route(
        db,
        owner=owner,
        route_id=route_id,
        payload=payload or DemoImportRequest(),
        settings=settings,
    )
    return journey_service.to_journey_out(journey)
