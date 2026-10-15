"""Demo mode schemas.

Sample routes are bundled with the repository and always carry
``source = "demo"``; a journey created from them is stamped as demo data so the
UI can never present it as a real ESP32-C3 recording.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SamplePoint(BaseModel):
    model_config = {"extra": "ignore"}

    #: Seconds from the start of the route; used to rebuild realistic timing.
    t: float = 0.0
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    altitude: float | None = None
    speed_kmh: float | None = None
    satellites: int | None = Field(default=None, ge=0, le=64)


class SampleRouteSummary(BaseModel):
    id: str
    name: str
    description: str
    source: str = "demo"
    point_count: int
    distance_m: float
    duration_seconds: float
    is_demo: bool = True


class SampleRouteDetail(SampleRouteSummary):
    points: list[SamplePoint]


class DemoImportRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    #: 1.0 keeps the recorded timing; 60.0 compresses 1 h of route into 1 min.
    duration_scale: float = Field(default=1.0, gt=0.0, le=600.0)
    #: Keep the journey open (recording) instead of finishing it immediately.
    keep_recording: bool = False
