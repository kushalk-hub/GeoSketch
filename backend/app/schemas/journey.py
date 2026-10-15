"""Journey and statistics schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.journey import JourneySource, JourneyStatus
from app.schemas.common import ORMModel, UTCDateTime
from app.schemas.gps import GPSPointOut


class JourneyCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=160)
    device_id: Optional[str] = Field(default=None, max_length=64)
    source: JourneySource = JourneySource.HARDWARE
    notes: Optional[str] = Field(default=None, max_length=500)
    #: False creates the journey in the ``paused`` state until /start is called.
    start_immediately: bool = True
    #: DEMO/import only: pin the start time so a replayed sample route keeps its
    #: realistic duration.  Ignored (and rejected) for hardware journeys, whose
    #: start is always the moment the recording began.
    started_at: Optional[UTCDateTime] = None


class JourneyUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=500)


class JourneyOut(ORMModel):
    id: int
    title: str
    device_id: Optional[str] = None
    source: str
    status: JourneyStatus
    notes: Optional[str] = None
    created_at: UTCDateTime
    started_at: UTCDateTime
    paused_at: Optional[UTCDateTime] = None
    finished_at: Optional[UTCDateTime] = None
    saved_at: Optional[UTCDateTime] = None
    total_distance_m: float
    duration_seconds: float
    moving_seconds: float
    point_count: int
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    artwork_count: int = 0


class JourneyDetail(JourneyOut):
    """Journey metadata plus every recorded point in chronological order."""

    points: List[GPSPointOut] = []


class JourneyStatistics(BaseModel):
    """Derived metrics.  Distance is a GPS estimate, not a surveyed value."""

    journey_id: int
    source: str
    status: JourneyStatus
    distance_m: float
    distance_km: float
    duration_seconds: float
    moving_seconds: float
    average_speed_kmh: Optional[float] = None
    max_speed_kmh: Optional[float] = None
    total_points: int
    used_points: int
    #: Points stored but excluded from the route (impossible jumps, 0,0 fixes).
    filtered_points: int
    #: Of the filtered points, how many were rejected as impossible jumps.
    rejected_points: int = 0
    gap_count: int
    jump_count: int
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    started_at: Optional[UTCDateTime] = None
    finished_at: Optional[UTCDateTime] = None
    is_estimate: bool = True
    note: str = (
        "Distance and speed are derived from GPS fixes and are estimates; "
        "they differ from the true travelled distance because of satellite "
        "noise, filtering and recording gaps."
    )
