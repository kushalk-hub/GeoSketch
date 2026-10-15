"""GPS point model: one row per accepted NMEA position fix."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.utils.time import utcnow


class PointSource(enum.StrEnum):
    HARDWARE = "hardware"
    DEMO = "demo"


class GPSPoint(Base):
    """A single validated GPS fix.

    * ``sequence``      - server assigned, guarantees chronological order.
    * ``server_timestamp`` - when the backend stored the point (always present).
    * ``gps_timestamp``  - the module's UTC time, only present once it has a fix
      and a valid date, so it is nullable.
    * ``dedupe_key``    - unique per journey; makes retries idempotent.
    * ``is_plausible``  - False when the fix implies an impossible jump.  Such
      points are stored for transparency but excluded from route drawing,
      statistics and artwork.
    """

    __tablename__ = "gps_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journey_id: Mapped[int] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("devices.device_id", ondelete="SET NULL"), nullable=True, index=True
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    satellites: Mapped[int | None] = mapped_column(Integer, nullable=True)

    gps_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    server_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    source: Mapped[str] = mapped_column(String(16), default=PointSource.HARDWARE.value)
    client_point_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)

    is_plausible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rejected_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    journey: Mapped[Journey] = relationship(back_populates="points")  # noqa: F821

    __table_args__ = (
        # Idempotency: the same physical fix can never be stored twice, even if
        # the ESP32 retries the request after a dropped connection.
        UniqueConstraint("journey_id", "dedupe_key", name="uq_gps_points_journey_dedupe"),
        UniqueConstraint("journey_id", "sequence", name="uq_gps_points_journey_sequence"),
        Index("ix_gps_points_journey_time", "journey_id", "server_timestamp"),
        Index("ix_gps_points_device_time", "device_id", "server_timestamp"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<GPSPoint {self.id} j{self.journey_id} #{self.sequence} "
            f"{self.latitude:.5f},{self.longitude:.5f} plausible={self.is_plausible}>"
        )
