"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import artworks, demo, devices, gps, journeys, meta

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(gps.router)
api_router.include_router(journeys.router)
api_router.include_router(devices.router)
api_router.include_router(artworks.router)
api_router.include_router(demo.router)

__all__ = ["api_router"]
