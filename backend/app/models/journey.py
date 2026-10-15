"""Journey model: a recording session containing an ordered set of GPS points."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.utils.time import utcnow


class JourneyStatus(enum.StrEnum):
    """Recording state machine.

    recording -> paused -> recording      (pause / resume)
    recording|paused -> stopped           (stop / finish)
    stopped -> saved                      (save)
    stopped -> deleted                    (clear unsaved)
    """

    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    SAVED = "saved"


class JourneySource(enum.StrEnum):
    """Where the points came from.

    Hardware and demo data are never mixed inside a journey, so the UI can
    always state truthfully whether a route came from a real device.
    """

    HARDWARE = "hardware"
    DEMO = "demo"


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(160), default="Untitled journey", nullable=False)
    owner: Mapped[str] = mapped_column(String(64), default="local", index=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("devices.device_id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(16), default=JourneySource.HARDWARE.value)
    status: Mapped[str] = mapped_column(
        String(16), default=JourneyStatus.RECORDING.value, index=True, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Cached statistics (recomputed whenever points change / the journey ends).
    total_distance_m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    moving_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    point_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    start_latitude: Mapped[float | None] = mapped_column(nullable=True)
    start_longitude: Mapped[float | None] = mapped_column(nullable=True)
    end_latitude: Mapped[float | None] = mapped_column(nullable=True)
    end_longitude: Mapped[float | None] = mapped_column(nullable=True)

    points: Mapped[list[GPSPoint]] = relationship(  # noqa: F821
        back_populates="journey",
        cascade="all, delete-orphan",
        order_by="GPSPoint.sequence",
        lazy="selectin",
    )
    artworks: Mapped[list[Artwork]] = relationship(  # noqa: F821
        back_populates="journey", cascade="all, delete-orphan", lazy="selectin"
    )
    device: Mapped[Device | None] = relationship(back_populates="journeys")  # noqa: F821

    __table_args__ = (
        Index("ix_journeys_owner_status", "owner", "status"),
        Index("ix_journeys_device_created", "device_id", "created_at"),
    )

    @property
    def is_active(self) -> bool:
        return self.status in {JourneyStatus.RECORDING.value, JourneyStatus.PAUSED.value}

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Journey {self.id} {self.title!r} status={self.status}>"
