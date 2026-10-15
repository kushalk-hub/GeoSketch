"""GeoSketch API application factory.

Run locally with::

    uvicorn app.main:app --reload --port 8000

Interactive documentation: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.middleware import RateLimitMiddleware, RequestSizeLimitMiddleware
from app.database.session import SessionLocal, init_db
from app.models.device import Device

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("geosketch")

settings = get_settings()

DESCRIPTION = """
**GeoSketch** turns real GPS movement into route artwork.

Physical tracker: **ESP32-C3 + NEO-6M** built on top of **FastAPI + SQLite**
with a React/Leaflet dashboard and a dependency-free artwork engine.

* `POST /api/v1/gps/points` is the firmware entry point (device API key required).
* Journeys follow an explicit recording state machine
  (`recording -> paused -> recording -> stopped -> saved`).
* Artwork is rendered to **SVG** (vector) and **PNG** (raster, Pillow).
* Journey statistics come from the haversine formula and are always estimates.
"""


def serialize_validation_errors(exc: RequestValidationError) -> list[dict]:
    """Make pydantic validation errors JSON safe.

    Custom ``model_validator`` errors carry a ``ValueError`` object inside
    ``ctx``, which the default JSON encoder cannot serialise - that would turn a
    422 into a 500.  Only the stable keys are kept and ``ctx``/``input`` values
    are coerced to strings.
    """
    safe: list[dict] = []
    for error in exc.errors():
        item: dict = {
            "loc": [str(part) for part in error.get("loc", [])],
            "msg": str(error.get("msg", "invalid value")),
            "type": str(error.get("type", "value_error")),
        }
        if "ctx" in error:
            item["ctx"] = {key: str(value) for key, value in dict(error["ctx"]).items()}
        raw_input = error.get("input")
        if isinstance(raw_input, (str, int, float, bool)) or raw_input is None:
            item["input"] = raw_input
        safe.append(item)
    return safe


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the schema and bootstrap device credentials on startup."""
    init_db()
    db = SessionLocal()
    try:
        from app.services.device_service import sync_devices_from_settings

        created = sync_devices_from_settings(db, settings)
        configured = db.scalars(select(Device)).all()
        logger.info(
            "GeoSketch API ready - %s device(s) configured (%s created), artwork dir: %s",
            len(configured),
            created,
            settings.artwork_dir,
        )
        if not configured:
            logger.warning(
                "No devices configured. Set GEOSKETCH_DEVICE_KEYS in backend/.env "
                "to authenticate the ESP32-C3."
            )
    finally:
        db.close()
    yield
    logger.info("GeoSketch API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    # --- middleware ---------------------------------------------------------
    # Order matters: the last middleware added is the outermost one, so CORS is
    # added last and therefore also decorates the 413/429 error responses.
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Device-Id", "X-Device-Key", "X-Owner-Key"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # --- exception handlers: one consistent error envelope ------------------
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.exception("Unhandled application error on %s", request.url.path)
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_failed",
                    "message": "The request payload failed validation.",
                    "details": {"errors": serialize_validation_errors(exc)},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized"}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": codes.get(exc.status_code, "http_error"),
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected_handler(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        logger.exception("Unexpected error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred. Check the server log.",
                }
            },
        )

    # --- routes -------------------------------------------------------------
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["Meta"], summary="Project banner")
    def root() -> dict:
        return {
            "project": "GeoSketch",
            "tagline": "GPS route art from real movement (ESP32-C3 + NEO-6M)",
            "docs": "/docs",
            "api": settings.api_v1_prefix,
            "demo_mode": f"{settings.api_v1_prefix}/demo/routes",
        }

    return app


app = create_app()
