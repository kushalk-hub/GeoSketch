"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import owner_from_header
from app.database.session import get_db
from app.models.device import Device
from app.schemas.common import ErrorResponse


def settings_dependency() -> Settings:
    return get_settings()


def current_owner(
    x_owner_key: str | None = Header(default=None, alias="X-Owner-Key"),
) -> str:
    """Ownership scope for journey queries (single tenant by default)."""
    return owner_from_header(x_owner_key, get_settings().default_owner)


def require_device(
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: Session = Depends(get_db),
) -> Device:
    """Authenticate the ESP32-C3 from its headers."""
    from app.services.device_service import require_device as _require_device

    return _require_device(db, x_device_id, x_device_key)


#: Documented error responses reused by the routers.
COMMON_ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Missing or invalid device credentials"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Invalid state transition"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {"model": ErrorResponse, "description": "Validation failed"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
}
