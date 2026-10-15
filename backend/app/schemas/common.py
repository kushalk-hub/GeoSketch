"""Shared Pydantic building blocks."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

from app.utils.time import parse_timestamp, utc_iso


def _serialize_datetime(value: datetime | None) -> str | None:
    return utc_iso(value)


def _normalize_datetime(value: Any) -> Any:
    """Accept ``"2026-10-15T10:30:00Z"`` and offset-aware input alike."""
    if isinstance(value, str):
        parsed = parse_timestamp(value)
        if parsed is None:
            raise ValueError("timestamp must be an ISO-8601 string")
        return parsed
    if isinstance(value, datetime):
        return parse_timestamp(value)
    return value


#: A UTC datetime that always serialises with an explicit ``Z`` suffix.
UTCDateTime = Annotated[
    datetime,
    BeforeValidator(_normalize_datetime),
    PlainSerializer(_serialize_datetime, return_type=str),
]


class ORMModel(BaseModel):
    """Base for response models built from ORM instances."""

    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """The single error shape returned by every failing endpoint."""

    error: ErrorBody


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None
