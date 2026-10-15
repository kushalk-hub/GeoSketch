"""Journey and statistics schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.journey import JourneySource, JourneyStatus
from app.schemas.common import ORMModel, UTCDateTime
from app.schemas.gps import GPSPointOut


class JourneyCreate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    device_id: str | None = Field(default=None, max_length=64)
    source: JourneySource = JourneySource.HARDWARE
    notes: str | None = Field(default=None, max_length=500)
    #: False creates the journey in the ``paused`` state until /start is called.
    start_immediately: bool = True
    #: DEMO/import only: pin the start time so a replayed sample route keeps its
    #: realistic duration.  Ignored (and rejected) for hardware journeys, whose
    #: start is always the moment the recording began.
    started_at: UTCDateTime | None = None


class JourneyUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)


class JourneyOut(ORMModel):
    id: int
    title: str
    device_id: str | None = None
    source: str
    status: JourneyStatus
    notes: str | None = None
    created_at: UTCDateTime
    started_at: UTCDateTime
    paused_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    saved_at: UTCDateTime | None = None
    total_distance_m: float
    duration_seconds: float
    moving_seconds: float
    point_count: int
    start_latitude: float | None = None
    start_longitude: float | None = None
    end_latitude: float | None = None
    end_longitude: float | None = None
    artwork_count: int = 0


class JourneyDetail(JourneyOut):
    """Journey metadata plus every recorded point in chronological order."""

    points: list[GPSPointOut] = Field(default_factory=list)


class JourneyStatistics(BaseModel):
    """Derived metrics.  Distance is a GPS estimate, not a surveyed value."""

    journey_id: int
    source: str
    status: JourneyStatus
    distance_m: float
    distance_km: float
    duration_seconds: float
    moving_seconds: float
    average_speed_kmh: float | None = None
    max_speed_kmh: float | None = None
    total_points: int
    used_points: int
    #: Points stored but excluded from the route (impossible jumps, 0,0 fixes).
    filtered_points: int
    #: Of the filtered points, how many were rejected as impossible jumps.
    rejected_points: int = 0
    gap_count: int
    jump_count: int
    start_latitude: float | None = None
    start_longitude: float | None = None
    end_latitude: float | None = None
    end_longitude: float | None = None
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    is_estimate: bool = True
    note: str = (
        "Distance and speed are derived from GPS fixes and are estimates; "
        "they differ from the true travelled distance because of satellite "
        "noise, filtering and recording gaps."
    )
