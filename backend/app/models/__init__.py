"""ORM models.  Importing this package registers every table on the metadata."""

from app.models.artwork import Artwork
from app.models.device import Device, DeviceStatus
from app.models.gps_point import GPSPoint, PointSource
from app.models.journey import Journey, JourneySource, JourneyStatus
from app.models.parent import AlertEvent, Geofence, GeofenceState, Parent, ShareLink

__all__ = [
    "AlertEvent",
    "Artwork",
    "Device",
    "DeviceStatus",
    "GPSPoint",
    "Geofence",
    "GeofenceState",
    "Journey",
    "JourneySource",
    "JourneyStatus",
    "Parent",
    "PointSource",
    "ShareLink",
]
