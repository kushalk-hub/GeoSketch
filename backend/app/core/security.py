"""Device authentication helpers.

Device credentials are high-entropy random strings issued out of band (see
``GEOSKETCH_DEVICE_KEYS``).  Only a SHA-256 digest is persisted, so the database
never holds a usable credential, and comparisons are constant time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_api_key(nbytes: int = 24) -> str:
    """Create a URL-safe random API key for a device."""
    return secrets.token_urlsafe(nbytes)


def hash_api_key(api_key: str) -> str:
    """Return the hex SHA-256 digest stored for a device API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, expected_hash: str) -> bool:
    """Constant-time comparison of a presented key against a stored digest."""
    if not api_key or not expected_hash:
        return False
    return hmac.compare_digest(hash_api_key(api_key), expected_hash)


def owner_from_header(value: str | None, default: str) -> str:
    """Resolve the ownership scope of a request.

    GeoSketch is single-tenant out of the box: when no ``X-Owner-Key`` header is
    supplied the configured default owner is used.  The hook exists so that
    journeys are never exposed across owners once a real user system is added.
    """
    if value is None:
        return default
    cleaned = value.strip()
    if not cleaned:
        return default
    return cleaned[:64]
