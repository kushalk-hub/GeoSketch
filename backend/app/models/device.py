"""Device model: one row per physical ESP32-C3 tracker."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DeviceStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"


class Device(Base):
    """A registered GeoSketch tracker.

    Authentication uses a SHA-256 digest of the API key; the plaintext key is
    never stored.  ``last_seen_at`` is refreshed on every accepted GPS point and
    is what the dashboard uses to decide between "live" and "last known".
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), default="GeoSketch tracker", nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    connection_status: Mapped[str] = mapped_column(
        String(16), default=DeviceStatus.UNKNOWN.value, nullable=False
    )
    owner: Mapped[str] = mapped_column(String(64), default="local", index=True, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    # Last position the device reported (kept for "last known position" UI).
    last_latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    last_longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    last_satellites: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_fix_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    points_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    journeys: Mapped[List["Journey"]] = relationship(  # noqa: F821
        back_populates="device", cascade="save-update"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Device {self.device_id} status={self.connection_status}>"
