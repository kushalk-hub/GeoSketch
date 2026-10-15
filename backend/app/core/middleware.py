"""HTTP middleware: request size limiting and in-memory rate limiting.

Both middlewares are dependency-free so the project runs with a plain
``pip install -r requirements.txt``.  For a multi-worker deployment the rate
limiter state should move to Redis (documented in docs/architecture.md).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

PAYLOAD_TOO_LARGE = 413
RATE_LIMITED = 429


def _json_error(code: str, message: str, status_code: int) -> JSONResponse:
    """Same error envelope the exception handlers use."""
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies before they reach the route handlers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        limit = get_settings().max_request_bytes
        header = request.headers.get("content-length")
        if header is not None:
            try:
                if int(header) > limit:
                    return _json_error(
                        "payload_too_large",
                        f"Request body exceeds the {limit} byte limit.",
                        PAYLOAD_TOO_LARGE,
                    )
            except ValueError:
                return _json_error(
                    "payload_too_large", "Invalid Content-Length header.", PAYLOAD_TOO_LARGE
                )

        # Streaming bodies (no Content-Length) are counted as they arrive.
        if header is None and request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > limit:
                return _json_error(
                    "payload_too_large",
                    f"Request body exceeds the {limit} byte limit.",
                    PAYLOAD_TOO_LARGE,
                )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window request counter keyed by device id (falling back to IP)."""

    def __init__(self, app, requests: int | None = None, window_seconds: int | None = None):
        super().__init__(app)
        settings = get_settings()
        self.limit = requests or settings.rate_limit_requests
        self.window = window_seconds or settings.rate_limit_window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def _key(self, request: Request) -> str:
        device_id = request.headers.get("x-device-id")
        if device_id:
            return f"device:{device_id}"
        if request.client and request.client.host:
            return f"ip:{request.client.host}"
        return "anonymous"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Cheap pre-flight and documentation requests are never throttled.
        if request.method == "OPTIONS" or request.url.path in {"/health", "/"}:
            return await call_next(request)

        now = time.monotonic()
        bucket = self._hits[self._key(request)]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = max(1, int(self.window - (now - bucket[0])))
            response = _json_error(
                "rate_limited",
                f"Too many requests. Retry in {retry_after} seconds.",
                RATE_LIMITED,
            )
            response.headers["Retry-After"] = str(retry_after)
            return response

        bucket.append(now)

        # Occasionally drop idle buckets so the dict cannot grow forever.
        if len(self._hits) > 512:
            for key in [k for k, v in self._hits.items() if not v]:
                self._hits.pop(key, None)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.limit - len(bucket)))
        return response
