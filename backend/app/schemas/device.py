"""Device schemas: connection status is always computed from ``last_seen_at``."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDateTime
from app.schemas.gps import GPSPointOut


class DeviceOut(ORMModel):
    device_id: str
    name: str
    connection_status: str
    firmware_version: Optional[str] = None
    last_seen_at: Optional[UTCDateTime] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_satellites: Optional[int] = None
    last_fix_at: Optional[UTCDateTime] = None
    points_received: int = 0
    #: True only when a point arrived within the offline threshold.
    is_live: bool = False
    seconds_since_last_seen: Optional[float] = None


class DeviceStatusOut(BaseModel):
    """Everything the dashboard needs in one poll."""

    device: Optional[DeviceOut] = None
    connected: bool = False
    active_journey_id: Optional[int] = None
    latest_point: Optional[GPSPointOut] = None
    offline_after_seconds: int = 30
    server_time: UTCDateTime


class DeviceRegister(BaseModel):
    device_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(default="GeoSketch tracker", max_length=120)
    firmware_version: Optional[str] = Field(default=None, max_length=32)
