"""Journey service: recording state machine, GPS ingestion and statistics.

Recording states
----------------
``recording`` -> ``paused``                 pause
``paused``    -> ``recording``              resume
``recording`` or ``paused`` -> ``stopped``  stop / finish
``stopped``   -> ``saved``                  save
``stopped``   -> (deleted)                  clear unsaved journey

Any other transition is refused with HTTP 409, so the API can never resume a
finished journey, save twice, or delete a saved one.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.models.device import Device
from app.models.gps_point import GPSPoint, PointSource
from app.models.journey import Journey, JourneySource, JourneyStatus
from app.schemas.gps import GPSPointIn
from app.schemas.journey import JourneyCreate, JourneyDetail, JourneyOut, JourneyStatistics, JourneyUpdate
from app.services.geo import point_time, validate_coordinates
from app.utils.segmentation import pair_metrics, segment_route
from app.utils.time import elapsed_seconds, utcnow

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS = {
    JourneyStatus.RECORDING.value: {JourneyStatus.PAUSED.value, JourneyStatus.STOPPED.value},
    JourneyStatus.PAUSED.value: {JourneyStatus.RECORDING.value, JourneyStatus.STOPPED.value},
    JourneyStatus.STOPPED.value: {JourneyStatus.SAVED.value},
    JourneyStatus.SAVED.value: set(),
}

ACTIVE_STATUSES = (JourneyStatus.RECORDING.value, JourneyStatus.PAUSED.value)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class IngestOutcome:
    """What happened to one incoming GPS point."""

    accepted: bool
    stored: bool
    duplicate: bool
    point: Optional[GPSPoint] = None
    reason: Optional[str] = None
    message: Optional[str] = None


@dataclass
class BulkIngestSummary:
    received: int = 0
    stored: int = 0
    duplicates: int = 0
    rejected: int = 0
    journey_id: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def default_journey_title(source: str, moment: Optional[datetime] = None) -> str:
    moment = moment or utcnow()
    prefix = "Demo journey" if source == JourneySource.DEMO.value else "Journey"
    return f"{prefix} - {moment.strftime('%d %b %Y %H:%M')}"


def compute_dedupe_key(journey_id: int, payload: GPSPointIn) -> str:
    """Deterministic idempotency key for one physical fix.

    The firmware sends ``client_point_id`` (boot counter + sequence) so a retried
    HTTP request can never insert the same point twice.  When a third-party
    client omits it, the rounded position plus the GPS timestamp is used.
    """
    if payload.client_point_id:
        basis = f"cpid:{payload.client_point_id}"
    else:
        stamp = payload.timestamp.isoformat() if payload.timestamp else "no-time"
        basis = f"pos:{payload.latitude:.6f}|{payload.longitude:.6f}|{stamp}"
    return hashlib.sha256(f"{journey_id}:{basis}".encode("utf-8")).hexdigest()


def _next_sequence(db: Session, journey_id: int) -> int:
    current = db.scalar(
        select(func.coalesce(func.max(GPSPoint.sequence), 0)).where(
            GPSPoint.journey_id == journey_id
        )
    )
    return int(current or 0) + 1


def last_point(
    db: Session, journey_id: int, *, plausible_only: bool = False
) -> Optional[GPSPoint]:
    statement = select(GPSPoint).where(GPSPoint.journey_id == journey_id)
    if plausible_only:
        statement = statement.where(GPSPoint.is_plausible.is_(True))
    statement = statement.order_by(GPSPoint.sequence.desc()).limit(1)
    return db.scalar(statement)


def consecutive_rejections(db: Session, journey_id: int, ceiling: int) -> int:
    """How many of the most recent stored fixes were rejected as jumps."""
    recent = list(
        db.scalars(
            select(GPSPoint.is_plausible)
            .where(GPSPoint.journey_id == journey_id)
            .order_by(GPSPoint.sequence.desc())
            .limit(max(1, ceiling))
        )
    )
    count = 0
    for is_plausible in recent:
        if is_plausible:
            break
        count += 1
    return count


def ordered_points(db: Session, journey_id: int) -> List[GPSPoint]:
    """Every point of a journey in recorded order."""
    return list(
        db.scalars(
            select(GPSPoint)
            .where(GPSPoint.journey_id == journey_id)
            .order_by(GPSPoint.sequence.asc())
        )
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def create_journey(db: Session, *, owner: str, payload: JourneyCreate) -> Journey:
    if payload.device_id:
        device = db.scalar(select(Device).where(Device.device_id == payload.device_id))
        if device is None:
            raise NotFoundError(
                f"device '{payload.device_id}' is not registered", code="device_not_found"
            )

    source = payload.source.value if isinstance(payload.source, JourneySource) else str(payload.source)
    now = utcnow()

    started_at = now
    if payload.started_at is not None:
        if source == JourneySource.HARDWARE.value:
            raise ValidationFailed(
                "started_at can only be set on a demo journey; a hardware journey "
                "always starts when the recording begins",
                code="started_at_not_allowed",
            )
        candidate = payload.started_at
        if candidate > now + timedelta(minutes=1):
            raise ValidationFailed(
                "started_at cannot be in the future", code="started_at_in_future"
            )
        if candidate < now - timedelta(days=30):
            raise ValidationFailed(
                "started_at is too far in the past (max 30 days)",
                code="started_at_too_old",
            )
        started_at = candidate

    journey = Journey(
        title=payload.title or default_journey_title(source, now),
        owner=owner,
        device_id=payload.device_id,
        source=source,
        notes=payload.notes,
        created_at=now,
        started_at=started_at,
        status=(
            JourneyStatus.RECORDING.value
            if payload.start_immediately
            else JourneyStatus.PAUSED.value
        ),
    )
    db.add(journey)
    db.commit()
    db.refresh(journey)
    logger.info("Created journey %s (owner=%s, source=%s)", journey.id, owner, source)
    return journey


def get_journey(
    db: Session, journey_id: int, *, owner: Optional[str] = None
) -> Journey:
    journey = db.get(Journey, journey_id)
    if journey is None or (owner is not None and journey.owner != owner):
        raise NotFoundError(f"journey {journey_id} not found", code="journey_not_found")
    return journey


def list_journeys(
    db: Session,
    *,
    owner: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    saved_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Journey], int]:
    filters = []
    if owner:
        filters.append(Journey.owner == owner)
    if status:
        filters.append(Journey.status == status)
    if source:
        filters.append(Journey.source == source)
    if saved_only:
        filters.append(Journey.status == JourneyStatus.SAVED.value)

    total = db.scalar(select(func.count(Journey.id)).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Journey)
            .where(*filters)
            .order_by(Journey.created_at.desc(), Journey.id.desc())
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        )
    )
    return items, int(total)


def active_journey(
    db: Session, *, owner: Optional[str] = None, device_id: Optional[str] = None
) -> Optional[Journey]:
    filters = [Journey.status.in_(ACTIVE_STATUSES)]
    if owner:
        filters.append(Journey.owner == owner)
    if device_id:
        filters.append(Journey.device_id == device_id)
    return db.scalar(
        select(Journey).where(*filters).order_by(Journey.created_at.desc(), Journey.id.desc()).limit(1)
    )


def get_or_create_active_journey(db: Session, *, device_id: str, owner: str) -> Journey:
    """Used by device ingestion so the tracker works without the web UI open."""
    journey = active_journey(db, owner=owner, device_id=device_id)
    if journey is not None:
        return journey
    return create_journey(
        db,
        owner=owner,
        payload=JourneyCreate(
            device_id=device_id,
            source=JourneySource.HARDWARE,
            start_immediately=True,
        ),
    )


def transition(db: Session, journey: Journey, target: JourneyStatus) -> Journey:
    allowed = ALLOWED_TRANSITIONS.get(journey.status, set())
    if target.value not in allowed:
        raise ConflictError(
            f"cannot change journey from '{journey.status}' to '{target.value}'",
            code="invalid_transition",
            details={
                "current": journey.status,
                "requested": target.value,
                "allowed": sorted(allowed),
            },
        )

    now = utcnow()
    journey.status = target.value
    if target == JourneyStatus.RECORDING:
        journey.paused_at = None
        if journey.finished_at is not None:
            # Should be unreachable thanks to ALLOWED_TRANSITIONS, kept for safety.
            journey.finished_at = None
    elif target == JourneyStatus.PAUSED:
        journey.paused_at = now
    elif target == JourneyStatus.STOPPED:
        journey.finished_at = now
        refresh_journey_cache(db, journey)
    elif target == JourneyStatus.SAVED:
        journey.saved_at = now
    db.commit()
    db.refresh(journey)
    logger.info("Journey %s -> %s", journey.id, target.value)
    return journey


def start_journey(db: Session, journey: Journey) -> Journey:
    """Start / resume.  A stopped or saved journey can never be restarted."""
    return transition(db, journey, JourneyStatus.RECORDING)


def pause_journey(db: Session, journey: Journey) -> Journey:
    return transition(db, journey, JourneyStatus.PAUSED)


def resume_journey(db: Session, journey: Journey) -> Journey:
    return transition(db, journey, JourneyStatus.RECORDING)


def stop_journey(db: Session, journey: Journey) -> Journey:
    return transition(db, journey, JourneyStatus.STOPPED)


def save_journey(db: Session, journey: Journey) -> Journey:
    if (journey.point_count or 0) == 0:
        raise ValidationFailed(
            "a journey with no recorded GPS points cannot be saved",
            code="empty_journey",
        )
    return transition(db, journey, JourneyStatus.SAVED)


def update_journey(db: Session, journey: Journey, payload: JourneyUpdate) -> Journey:
    if payload.title is not None:
        journey.title = payload.title.strip() or journey.title
    if payload.notes is not None:
        journey.notes = payload.notes
    db.commit()
    db.refresh(journey)
    return journey


def delete_journey(db: Session, journey: Journey) -> None:
    """Remove an unsaved journey ("clear unsaved journey" in the UI)."""
    if journey.status == JourneyStatus.SAVED.value:
        raise ConflictError(
            "saved journeys cannot be cleared; delete it explicitly first",
            code="journey_saved",
            details={"journey_id": journey.id},
        )
    journey_id = journey.id
    db.delete(journey)
    db.commit()
    logger.info("Deleted journey %s", journey_id)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def ingest_point(
    db: Session,
    *,
    journey: Journey,
    payload: GPSPointIn,
    device: Optional[Device] = None,
    source: str = PointSource.HARDWARE.value,
    commit: bool = True,
    settings: Optional[Settings] = None,
) -> IngestOutcome:
    """Validate, de-duplicate and store a single fix.

    Returns an outcome instead of raising for the "expected" refusals (paused /
    finished journey, duplicate) so the firmware gets a clear 2xx answer and does
    not retry a point forever.
    """
    settings = settings or get_settings()

    if journey.status == JourneyStatus.PAUSED.value:
        return IngestOutcome(
            accepted=False,
            stored=False,
            duplicate=False,
            reason="journey_paused",
            message="Recording is paused; the point was not stored.",
        )
    if journey.status in {JourneyStatus.STOPPED.value, JourneyStatus.SAVED.value}:
        return IngestOutcome(
            accepted=False,
            stored=False,
            duplicate=False,
            reason="journey_not_recording",
            message=f"Journey is '{journey.status}'; start a new journey to record.",
        )

    latitude, longitude = validate_coordinates(payload.latitude, payload.longitude)
    timestamp = payload.timestamp

    dedupe_key = compute_dedupe_key(journey.id, payload)
    existing = db.scalar(
        select(GPSPoint).where(
            GPSPoint.journey_id == journey.id, GPSPoint.dedupe_key == dedupe_key
        )
    )
    if existing is not None:
        return IngestOutcome(
            accepted=True,
            stored=False,
            duplicate=True,
            point=existing,
            reason="duplicate",
            message="This point was already stored (retry ignored).",
        )

    probe = GPSPoint(
        journey_id=journey.id,
        sequence=0,
        latitude=latitude,
        longitude=longitude,
        gps_timestamp=timestamp,
        server_timestamp=utcnow(),
        dedupe_key="probe",
    )

    # Plausibility is judged against the *immediately previous* fix: an outlier
    # is dropped, while the next fix is judged against the outlier (which is
    # consistent with the new position) so a real relocation is not punished
    # forever.
    previous = last_point(db, journey.id)
    is_plausible = True
    rejected_reason: Optional[str] = None

    if previous is not None:
        rejections = consecutive_rejections(db, journey.id, settings.reanchor_after_rejects)
        if rejections >= settings.reanchor_after_rejects:
            logger.warning(
                "Journey %s: re-anchored after %s consecutive rejected fixes",
                journey.id,
                rejections,
            )
        else:
            cut, _distance, delta = pair_metrics(
                previous,
                probe,
                max_gap_seconds=settings.max_gap_seconds,
                max_plausible_speed_kmh=settings.max_plausible_speed_kmh,
            )
            is_gap = delta is not None and delta > settings.max_gap_seconds
            if cut and not is_gap:
                # Impossible speed between two consecutive fixes: keep the point
                # for transparency but exclude it from route/statistics/artwork.
                is_plausible = False
                rejected_reason = "implausible_jump"

    # Journey totals always accumulate between *consecutive accepted* fixes, so
    # the live counter uses exactly the same rule as the offline recalculation.
    cut = False
    distance = 0.0
    delta: Optional[float] = None
    if is_plausible:
        anchor = last_point(db, journey.id, plausible_only=True)
        if anchor is not None:
            cut, distance, delta = pair_metrics(
                anchor,
                probe,
                max_gap_seconds=settings.max_gap_seconds,
                max_plausible_speed_kmh=settings.max_plausible_speed_kmh,
            )

    stored_point: Optional[GPSPoint] = None
    for attempt in range(2):
        sequence = _next_sequence(db, journey.id)
        point = GPSPoint(
            journey_id=journey.id,
            device_id=device.device_id if device is not None else journey.device_id,
            sequence=sequence,
            latitude=latitude,
            longitude=longitude,
            altitude=payload.altitude,
            speed_kmh=payload.speed_kmh,
            satellites=payload.satellites,
            gps_timestamp=timestamp,
            server_timestamp=utcnow(),
            source=source,
            client_point_id=payload.client_point_id,
            dedupe_key=dedupe_key,
            is_plausible=is_plausible,
            rejected_reason=rejected_reason,
        )
        db.add(point)
        try:
            db.flush()
            stored_point = point
            break
        except IntegrityError:
            # Lost a race against a concurrent retry: fall back to the stored row.
            db.rollback()
            existing = db.scalar(
                select(GPSPoint).where(
                    GPSPoint.journey_id == journey.id, GPSPoint.dedupe_key == dedupe_key
                )
            )
            if existing is not None:
                return IngestOutcome(
                    accepted=True,
                    stored=False,
                    duplicate=True,
                    point=existing,
                    reason="duplicate",
                    message="Concurrent duplicate insert ignored.",
                )
            if attempt == 1:
                raise ConflictError(
                    "could not assign a unique sequence number for this point",
                    code="sequence_conflict",
                )

    if stored_point is None:  # pragma: no cover - defensive
        raise ConflictError("failed to store GPS point", code="store_failed")

    _apply_point_to_cache(journey, stored_point, cut=cut, distance=distance, delta=delta)

    if device is not None:
        from app.services.device_service import mark_seen

        mark_seen(
            db,
            device,
            latitude=latitude if is_plausible else None,
            longitude=longitude if is_plausible else None,
            satellites=payload.satellites,
            fix_at=timestamp,
        )

    if commit:
        db.commit()

    return IngestOutcome(accepted=True, stored=True, duplicate=False, point=stored_point)


def ingest_points(
    db: Session,
    *,
    journey: Journey,
    payloads: Sequence[GPSPointIn],
    device: Optional[Device] = None,
    source: str = PointSource.DEMO.value,
    settings: Optional[Settings] = None,
) -> BulkIngestSummary:
    """Bulk ingest used by demo replay (hardware posts one point at a time)."""
    summary = BulkIngestSummary(received=len(payloads), journey_id=journey.id)
    for payload in payloads:
        outcome = ingest_point(
            db,
            journey=journey,
            payload=payload,
            device=device,
            source=source,
            commit=False,
            settings=settings,
        )
        if outcome.stored:
            summary.stored += 1
        elif outcome.duplicate:
            summary.duplicates += 1
        else:
            summary.rejected += 1
    db.commit()
    return summary


def _apply_point_to_cache(
    journey: Journey, point: GPSPoint, *, cut: bool, distance: float, delta: Optional[float]
) -> None:
    """Incremental journey totals.

    Uses exactly the same gap/jump rules as :func:`segment_route`, and the totals
    are recomputed from the stored points whenever the journey is stopped, so the
    cached values can never drift.
    """
    journey.point_count = (journey.point_count or 0) + 1
    if point.is_plausible:
        if not cut:
            journey.total_distance_m = (journey.total_distance_m or 0.0) + distance
            if delta:
                journey.moving_seconds = (journey.moving_seconds or 0.0) + delta
        if journey.start_latitude is None:
            journey.start_latitude = point.latitude
            journey.start_longitude = point.longitude
        journey.end_latitude = point.latitude
        journey.end_longitude = point.longitude
    moment = point_time(point)
    journey.duration_seconds = elapsed_seconds(journey.started_at, moment)


def journey_span(
    journey: Journey, plausible: Sequence[GPSPoint]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Earliest and latest instant that belong to the journey.

    Neither the server clock nor the GPS clock is trusted blindly: the journey
    duration is measured from the earliest known instant (server start *or* the
    first fix) to the latest one (server stop *or* the last fix).  That keeps the
    duration correct when the GPS module reports UTC time that differs from the
    server clock - a very common situation with a cold-start NEO-6M.
    """
    start = journey.started_at
    end = journey.finished_at
    if plausible:
        first = point_time(plausible[0])
        last = point_time(plausible[-1])
        if first is not None and (start is None or first < start):
            start = first
        if last is not None and (end is None or last > end):
            end = last
    if end is None:
        end = start
    return start, end


def refresh_journey_cache(db: Session, journey: Journey) -> Journey:
    """Recompute the cached totals from the stored points."""
    points = ordered_points(db, journey.id)
    result = segment_route(
        points,
        max_gap_seconds=get_settings().max_gap_seconds,
        max_plausible_speed_kmh=get_settings().max_plausible_speed_kmh,
    )
    journey.point_count = len(points)
    journey.total_distance_m = result.distance_m
    journey.moving_seconds = result.moving_seconds

    plausible = [point for point in points if point.is_plausible]
    if plausible:
        journey.start_latitude = plausible[0].latitude
        journey.start_longitude = plausible[0].longitude
        journey.end_latitude = plausible[-1].latitude
        journey.end_longitude = plausible[-1].longitude

    start, end = journey_span(journey, plausible)
    journey.duration_seconds = elapsed_seconds(start, end)
    return journey


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def compute_statistics(
    db: Session, journey: Journey, settings: Optional[Settings] = None
) -> JourneyStatistics:
    settings = settings or get_settings()
    points = ordered_points(db, journey.id)
    result = segment_route(
        points,
        max_gap_seconds=settings.max_gap_seconds,
        max_plausible_speed_kmh=settings.max_plausible_speed_kmh,
    )

    plausible = [point for point in points if point.is_plausible]
    start = plausible[0] if plausible else None
    end = plausible[-1] if plausible else None

    span_start, span_end = journey_span(journey, plausible)
    duration = elapsed_seconds(span_start, span_end)

    return JourneyStatistics(
        journey_id=journey.id,
        source=journey.source,
        status=JourneyStatus(journey.status),
        distance_m=round(result.distance_m, 3),
        distance_km=round(result.distance_m / 1000.0, 6),
        duration_seconds=round(duration, 3),
        moving_seconds=round(result.moving_seconds, 3),
        average_speed_kmh=(
            round(result.average_speed_kmh, 2) if result.average_speed_kmh is not None else None
        ),
        max_speed_kmh=(
            round(result.max_speed_kmh, 2) if result.max_speed_kmh is not None else None
        ),
        total_points=len(points),
        used_points=result.used_points,
        filtered_points=len(points) - result.used_points,
        rejected_points=result.implausible_skipped + result.invalid_skipped,
        gap_count=result.gap_cuts,
        jump_count=result.jump_cuts,
        start_latitude=start.latitude if start else journey.start_latitude,
        start_longitude=start.longitude if start else journey.start_longitude,
        end_latitude=end.latitude if end else journey.end_latitude,
        end_longitude=end.longitude if end else journey.end_longitude,
        started_at=span_start,
        finished_at=span_end,
    )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------
def to_journey_out(journey: Journey, artwork_count: Optional[int] = None) -> JourneyOut:
    model = JourneyOut.model_validate(journey)
    model.artwork_count = (
        artwork_count if artwork_count is not None else len(journey.artworks or [])
    )
    return model


def to_journey_detail(journey: Journey) -> JourneyDetail:
    detail = JourneyDetail.model_validate(journey)
    detail.artwork_count = len(journey.artworks or [])
    detail.points = sorted(detail.points, key=lambda item: item.sequence)
    return detail
