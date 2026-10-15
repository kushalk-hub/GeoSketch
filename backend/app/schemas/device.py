"""Device schemas: connection status is always computed from ``last_seen_at``."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDateTime
from app.schemas.gps import GPSPointOut


class DeviceOut(ORMModel):
    device_id: str
    name: str
    connection_status: str
    firmware_version: str | None = None
    last_seen_at: UTCDateTime | None = None
    last_latitude: float | None = None
    last_longitude: float | None = None
    last_satellites: int | None = None
    last_fix_at: UTCDateTime | None = None
    points_received: int = 0
    #: True only when a point arrived within the offline threshold.
    is_live: bool = False
    seconds_since_last_seen: float | None = None


class DeviceStatusOut(BaseModel):
    """Everything the dashboard needs in one poll."""

    device: DeviceOut | None = None
    connected: bool = False
    active_journey_id: int | None = None
    latest_point: GPSPointOut | None = None
    offline_after_seconds: int = 30
    server_time: UTCDateTime


class DeviceRegister(BaseModel):
    device_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(default="GeoSketch tracker", max_length=120)
    firmware_version: str | None = Field(default=None, max_length=32)
