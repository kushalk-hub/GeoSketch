"""Artwork model: metadata for a generated route artwork."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.utils.time import utcnow


class Artwork(Base):
    """A rendered piece of route art.

    The rendered files live under ``data/artworks`` and are addressed by
    ``file_stem``.  Both an SVG (vector, hand written) and a PNG (raster, Pillow)
    are produced for every artwork so either format can be downloaded.
    """

    __tablename__ = "artworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journey_id: Mapped[int] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(160), default="Route artwork", nullable=False)
    style: Mapped[str] = mapped_column(String(32), nullable=False)
    # JSON blob with the exact customisation used, so a style can be reproduced.
    customization: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    export_format: Mapped[str] = mapped_column(String(8), default="png", nullable=False)

    file_stem: Mapped[str] = mapped_column(String(80), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    point_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    journey: Mapped[Journey] = relationship(back_populates="artworks")  # noqa: F821

    __table_args__ = (Index("ix_artworks_journey_created", "journey_id", "created_at"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Artwork {self.id} {self.style} journey={self.journey_id}>"
