"""Time helpers.  Every timestamp handled by the backend is naive UTC.

SQLite (and MySQL) do not retain time zone offsets, so the whole application
normalises to naive UTC internally and the API layer re-attaches ``Z`` when
serialising.  That keeps ordering comparisons correct and avoids the classic
"stored 14:00 local, read back as if UTC" bug.
"""

from __future__ import annotations

from datetime import UTC, datetime

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (DB representation)."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_utc(value: datetime | None) -> datetime | None:
    """Normalise any datetime to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def parse_timestamp(value: str | datetime | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (``Z`` or offset aware) into naive UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return to_utc(value)
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return to_utc(parsed)


def utc_iso(value: datetime | None) -> str | None:
    """Serialise a (naive UTC) datetime as an ISO-8601 string with ``Z``."""
    if value is None:
        return None
    return to_utc(value).strftime(ISO_FORMAT)


def elapsed_seconds(start: datetime | None, end: datetime | None) -> float:
    """Seconds between two naive-UTC datetimes, never negative."""
    if start is None or end is None:
        return 0.0
    return max(0.0, (end - start).total_seconds())
