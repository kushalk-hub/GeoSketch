"""Artwork request/response schemas."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.artwork.styles import ArtworkStyle
from app.schemas.common import ORMModel, UTCDateTime

_HEX_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class CustomArtOptions(BaseModel):
    """User customisation for the ``custom`` style (also nudges other styles)."""

    background: str | None = Field(default=None, pattern=_HEX_PATTERN)
    route_color: str | None = Field(default=None, pattern=_HEX_PATTERN)
    accent_color: str | None = Field(default=None, pattern=_HEX_PATTERN)
    line_width: float | None = Field(default=None, ge=0.5, le=40.0)
    glow: bool | None = None
    title: str | None = Field(default=None, max_length=120)
    subtitle: str | None = Field(default=None, max_length=160)
    show_start_marker: bool = True
    show_end_marker: bool = True


class ArtworkRequest(BaseModel):
    style: ArtworkStyle = ArtworkStyle.MINIMAL
    title: str | None = Field(default=None, max_length=120)
    export_format: str = Field(default="png", pattern="^(png|svg)$")
    palette: str | None = Field(default=None, max_length=40)
    width: int | None = Field(default=None, ge=400, le=4000)
    height: int | None = Field(default=None, ge=400, le=4000)
    customization: CustomArtOptions = Field(default_factory=CustomArtOptions)
    #: Persist the render as an Artwork row + files.  False = preview only.
    save: bool = True

    @field_validator("export_format")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()


class ArtworkOut(ORMModel):
    id: int
    journey_id: int
    title: str
    style: str
    export_format: str
    width: int
    height: int
    point_count: int
    segment_count: int
    distance_m: float
    created_at: UTCDateTime
    customization: dict[str, Any] = Field(default_factory=dict)
    png_url: str | None = None
    svg_url: str | None = None

    @field_validator("customization", mode="before")
    @classmethod
    def _parse_customization(cls, value: Any) -> Any:
        """The column stores JSON text; expose it as a ready-to-use dict."""
        if isinstance(value, str):
            try:
                parsed = json.loads(value or "{}")
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return value or {}


class ArtworkPreview(BaseModel):
    """Inline SVG preview so the studio can re-render instantly."""

    style: str
    title: str
    width: int
    height: int
    svg: str
    point_count: int
    segment_count: int
    distance_m: float
    duration_seconds: float
    processing: dict[str, Any] = {}
