"""GPS point schemas (ESP32-C3 -> backend payload and API representations)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel, UTCDateTime


class GPSPointIn(BaseModel):
    """Payload posted by the firmware.

    Only ``latitude``/``longitude`` are mandatory.  Everything the NEO-6M could
    not provide must be sent as ``null`` rather than as a made-up value, so the
    API can distinguish "unknown" from a real reading.
    """

    model_config = {"extra": "forbid"}

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Decimal degrees, WGS84")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Decimal degrees, WGS84")
    altitude: Optional[float] = Field(
        default=None, ge=-500.0, le=20000.0, description="Metres above mean sea level"
    )
    speed_kmh: Optional[float] = Field(default=None, ge=0.0, le=1200.0)
    satellites: Optional[int] = Field(default=None, ge=0, le=64)
    hdop: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    #: UTC time reported by the GPS module; absent until the first valid fix.
    timestamp: Optional[UTCDateTime] = None
    #: Optional when the X-Device-Id header is supplied instead.
    device_id: Optional[str] = Field(default=None, max_length=64)
    #: Monotonic counter from the device; used for idempotent retries.
    client_point_id: Optional[str] = Field(default=None, max_length=64)
    #: Attach to a specific journey instead of the device's active journey.
    journey_id: Optional[int] = None
    fix_quality: Optional[int] = Field(default=None, ge=0, le=9)

    @model_validator(mode="after")
    def _reject_null_island(self) -> "GPSPointIn":
        # A NEO-6M without a fix streams 0.0/0.0; never accept it as a position.
        if abs(self.latitude) < 1e-7 and abs(self.longitude) < 1e-7:
            raise ValueError(
                "latitude/longitude 0,0 indicates the GPS module has no fix and "
                "must not be transmitted"
            )
        return self


class GPSPointOut(ORMModel):
    id: int
    journey_id: int
    device_id: Optional[str] = None
    sequence: int
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed_kmh: Optional[float] = None
    satellites: Optional[int] = None
    gps_timestamp: Optional[UTCDateTime] = None
    server_timestamp: UTCDateTime
    source: str
    is_plausible: bool
    rejected_reason: Optional[str] = None


class GPSIngestResponse(BaseModel):
    """Outcome of a GPS point POST.

    ``accepted`` is False when the journey is paused (the point is deliberately
    dropped) - the firmware treats any 2xx as "do not retry this point".
    """

    accepted: bool
    stored: bool
    duplicate: bool
    journey_id: int
    point_id: Optional[int] = None
    sequence: Optional[int] = None
    server_timestamp: UTCDateTime
    reason: Optional[str] = None
    message: Optional[str] = None


class GPSPointBulkIn(BaseModel):
    """Bulk upload used by demo replay (never by the firmware)."""

    model_config = {"extra": "forbid"}

    points: list[GPSPointIn] = Field(..., min_length=1, max_length=2000)
    source: str = Field(default="demo", pattern="^(demo|hardware)$")


class GPSPointBulkResponse(BaseModel):
    received: int
    stored: int
    duplicates: int
    rejected: int
    journey_id: int
