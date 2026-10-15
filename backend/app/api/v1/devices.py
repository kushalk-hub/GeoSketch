"""Device endpoints: connection status, heartbeat and registration."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import COMMON_ERROR_RESPONSES, current_owner, require_device
from app.core.config import Settings, get_settings
from app.core.errors import AuthError
from app.database.session import get_db
from app.models.device import Device
from app.schemas.common import MessageResponse
from app.schemas.device import DeviceOut, DeviceRegister, DeviceStatusOut
from app.services.device_service import (
    device_status,
    list_devices,
    register_device,
    sync_devices_from_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["Devices"], responses=COMMON_ERROR_RESPONSES)


@router.get("", response_model=List[DeviceOut], summary="List registered devices")
def get_devices(
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> List[DeviceOut]:
    return list_devices(db, owner=owner)


@router.get(
    "/{device_id}/status",
    response_model=DeviceStatusOut,
    summary="Live connection status of a device",
    description=(
        "`connected` is true only when a GPS point arrived within the offline "
        "threshold. The latest stored point is returned separately so the UI can "
        "always show *when* the last real update happened."
    ),
)
def get_device_status(
    device_id: str,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> DeviceStatusOut:
    return device_status(db, device_id=device_id, owner=owner)


@router.post(
    "/register",
    response_model=DeviceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register / refresh a device (must match the configured device key)",
)
def register(
    payload: DeviceRegister,
    api_key: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DeviceOut:
    """Setup helper: the api_key must match ``GEOSKETCH_DEVICE_KEYS`` for that id."""
    configured = settings.device_key_map.get(payload.device_id)
    if configured is None or configured != api_key:
        raise AuthError(
            "device_id/api_key does not match the configured device keys",
            code="invalid_device_credentials",
        )
    device = register_device(
        db,
        device_id=payload.device_id,
        name=payload.name,
        firmware_version=payload.firmware_version,
        api_key=api_key,
    )
    from app.services.device_service import to_device_out

    return to_device_out(device, settings)


@router.post(
    "/heartbeat",
    response_model=MessageResponse,
    summary="Firmware heartbeat (device credentials required)",
)
def heartbeat(
    db: Session = Depends(get_db),
    device: Device = Depends(require_device),
    firmware_version: str | None = None,
) -> MessageResponse:
    """Lets the firmware report itself online before it has a GPS fix."""
    if firmware_version:
        device.firmware_version = firmware_version
    db.commit()
    return MessageResponse(
        message="heartbeat received",
        detail=f"device_id={device.device_id}",
    )


@router.post(
    "/sync",
    response_model=List[DeviceOut],
    summary="Re-synchronise devices from the environment configuration",
)
def sync_devices(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[DeviceOut]:
    sync_devices_from_settings(db, settings)
    return list_devices(db)
