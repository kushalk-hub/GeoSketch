"""Demo mode: bundled sample routes for presentations without hardware.

Sample files live in ``data/sample_routes/*.json``.  They are *never* mixed with
hardware data: an imported sample produces a journey with ``source = "demo"``.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationFailed
from app.models.journey import Journey, JourneySource
from app.schemas.demo import DemoImportRequest, SampleRouteDetail, SampleRouteSummary
from app.schemas.gps import GPSPointIn
from app.schemas.journey import JourneyCreate
from app.services.geo import haversine_m
from app.services.journey_service import (
    create_journey,
    ingest_points,
    stop_journey,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def _routes_dir(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    return settings.sample_routes_dir


def _route_paths(settings: Optional[Settings] = None) -> Dict[str, Path]:
    directory = _routes_dir(settings)
    found: Dict[str, Path] = {}
    if not directory.exists():
        logger.warning("Sample route directory %s does not exist", directory)
        return found
    for path in sorted(directory.glob("*.json")):
        found[path.stem] = path
    return found


def _load(path: Path) -> SampleRouteDetail:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailed(
            f"sample route '{path.stem}' could not be read", code="sample_route_invalid"
        ) from exc

    raw.setdefault("id", path.stem)
    raw.setdefault("name", path.stem.replace("_", " ").title())
    raw.setdefault("description", "")
    raw.setdefault("source", "demo")
    try:
        detail = SampleRouteDetail.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ValidationFailed(
            f"sample route '{path.stem}' is malformed", code="sample_route_invalid"
        ) from exc

    # Fill in the derived values when the file does not carry them.
    if not detail.points:
        raise ValidationFailed(
            f"sample route '{path.stem}' has no points", code="sample_route_invalid"
        )
    points = sorted(detail.points, key=lambda point: point.t)
    detail.points = points
    if detail.point_count <= 0:
        detail.point_count = len(points)
    if detail.distance_m <= 0:
        detail.distance_m = route_distance_m(points)
    if detail.duration_seconds <= 0:
        detail.duration_seconds = max(point.t for point in points)
    return detail


def route_distance_m(points) -> float:
    total = 0.0
    for previous, point in zip(points, points[1:]):
        total += haversine_m(
            previous.latitude, previous.longitude, point.latitude, point.longitude
        )
    return total


def list_sample_routes(settings: Optional[Settings] = None) -> List[SampleRouteSummary]:
    summaries: List[SampleRouteSummary] = []
    for route_id, path in _route_paths(settings).items():
        try:
            detail = _load(path)
        except ValidationFailed as exc:
            logger.warning("Skipping sample route %s: %s", route_id, exc.message)
            continue
        summaries.append(
            SampleRouteSummary(
                id=detail.id,
                name=detail.name,
                description=detail.description,
                source="demo",
                point_count=detail.point_count,
                distance_m=round(detail.distance_m, 1),
                duration_seconds=round(detail.duration_seconds, 1),
            )
        )
    return summaries


def load_sample_route(route_id: str, settings: Optional[Settings] = None) -> SampleRouteDetail:
    paths = _route_paths(settings)
    path = paths.get(route_id)
    if path is None:
        raise NotFoundError(
            f"sample route '{route_id}' not found",
            code="sample_route_not_found",
            details={"available": sorted(paths.keys())},
        )
    return _load(path)


def import_sample_route(
    db: Session,
    *,
    owner: str,
    route_id: str,
    payload: Optional[DemoImportRequest] = None,
    settings: Optional[Settings] = None,
) -> Journey:
    """Create a finished DEMO journey from a bundled sample route.

    Timestamps are rebuilt so statistics (duration, average speed) are realistic
    while remaining clearly labelled as demo data.
    """
    settings = settings or get_settings()
    payload = payload or DemoImportRequest()
    detail = load_sample_route(route_id, settings)

    span = max(point.t for point in detail.points)
    scale = payload.duration_scale
    now = utcnow()
    started_at = now - timedelta(seconds=span / scale if scale else span)

    journey = create_journey(
        db,
        owner=owner,
        payload=JourneyCreate(
            title=payload.title or detail.name,
            source=JourneySource.DEMO,
            notes=f"Bundled demo route '{detail.id}' (simulated, not hardware data).",
            start_immediately=True,
        ),
    )
    # Pin the journey start to the simulated route start.
    journey.started_at = started_at
    db.commit()

    ingest_payloads = [
        GPSPointIn(
            latitude=point.latitude,
            longitude=point.longitude,
            altitude=point.altitude,
            speed_kmh=point.speed_kmh,
            satellites=point.satellites if point.satellites is not None else 9,
            timestamp=started_at + timedelta(seconds=point.t / scale),
            client_point_id=f"{route_id}:{index}",
        )
        for index, point in enumerate(detail.points)
    ]

    summary = ingest_points(
        db,
        journey=journey,
        payloads=ingest_payloads,
        source="demo",
        settings=settings,
    )
    journey = stop_journey(db, journey)
    journey.notes = (
        f"Demo mode: bundled sample route '{detail.id}' with {summary.stored} simulated "
        "GPS points. Not recorded by an ESP32-C3."
    )
    db.commit()
    db.refresh(journey)
    logger.info("Imported demo route %s as journey %s", route_id, journey.id)
    return journey
