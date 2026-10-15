"""Artwork endpoints: metadata and PNG/SVG downloads."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import COMMON_ERROR_RESPONSES, current_owner
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.schemas.artwork import ArtworkOut
from app.services import artwork_service
from app.services.journey_service import get_journey

router = APIRouter(prefix="/artworks", tags=["Artwork"], responses=COMMON_ERROR_RESPONSES)

MEDIA_TYPES = {"png": "image/png", "svg": "image/svg+xml"}


def _authorized_artwork(db: Session, artwork_id: int, owner: str):
    """Load an artwork only when it belongs to a journey of this owner."""
    artwork = artwork_service.get_artwork(db, artwork_id)
    get_journey(db, artwork.journey_id, owner=owner)  # raises when foreign
    return artwork


@router.get("/{artwork_id}", response_model=ArtworkOut, summary="Artwork metadata")
def get_artwork(
    artwork_id: int,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> ArtworkOut:
    artwork = _authorized_artwork(db, artwork_id, owner)
    return artwork_service.artwork_to_out(artwork, settings=settings)


@router.get(
    "/{artwork_id}/download",
    summary="Download the artwork as PNG or SVG",
    response_class=FileResponse,
)
def download_artwork(
    artwork_id: int,
    format: str = Query(default="png", pattern="^(png|svg)$"),
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    artwork = _authorized_artwork(db, artwork_id, owner)
    path = artwork_service.artwork_file(artwork, format, settings=settings)
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[format],
        filename=f"geosketch-journey{artwork.journey_id}-{artwork.style}.{format}",
    )
