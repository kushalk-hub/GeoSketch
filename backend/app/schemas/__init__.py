"""Pydantic schemas."""

from app.schemas.artwork import ArtworkOut, ArtworkPreview, ArtworkRequest, CustomArtOptions
from app.schemas.common import ErrorBody, ErrorResponse, MessageResponse, ORMModel, UTCDateTime
from app.schemas.demo import (
    DemoImportRequest,
    SamplePoint,
    SampleRouteDetail,
    SampleRouteSummary,
)
from app.schemas.device import DeviceOut, DeviceRegister, DeviceStatusOut
from app.schemas.gps import (
    GPSIngestResponse,
    GPSPointBulkIn,
    GPSPointBulkResponse,
    GPSPointIn,
    GPSPointOut,
)
from app.schemas.journey import (
    JourneyCreate,
    JourneyDetail,
    JourneyOut,
    JourneyStatistics,
    JourneyUpdate,
)

__all__ = [
    "ArtworkOut",
    "ArtworkPreview",
    "ArtworkRequest",
    "CustomArtOptions",
    "DemoImportRequest",
    "DeviceOut",
    "DeviceRegister",
    "DeviceStatusOut",
    "ErrorBody",
    "ErrorResponse",
    "GPSIngestResponse",
    "GPSPointBulkIn",
    "GPSPointBulkResponse",
    "GPSPointIn",
    "GPSPointOut",
    "JourneyCreate",
    "JourneyDetail",
    "JourneyOut",
    "JourneyStatistics",
    "JourneyUpdate",
    "MessageResponse",
    "ORMModel",
    "SamplePoint",
    "SampleRouteDetail",
    "SampleRouteSummary",
    "UTCDateTime",
]
