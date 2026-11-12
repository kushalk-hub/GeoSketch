"""Parent password hashing and signed session tokens (stdlib only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, AuthError
from app.models.parent import Parent
from app.utils.time import utcnow


def _secret() -> bytes:
    value = get_settings().auth_secret
    if not value:
        raise AppError(
            "Parent features are not configured.", code="auth_not_configured", status_code=503
        )
    return value.encode()


_DUMMY_SALT = b"geosketch-dummy-salt"
_DUMMY_DIGEST = hashlib.scrypt(b"not-a-real-password", salt=_DUMMY_SALT, n=2**14, r=8, p=1).hex()
DUMMY_PASSWORD_HASH = f"{_DUMMY_SALT.hex()}:{_DUMMY_DIGEST}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        candidate = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def issue_session(parent: Parent) -> str:
    secret = _secret()
    exp = int(
        (utcnow() + timedelta(hours=get_settings().session_ttl_hours))
        .replace(tzinfo=UTC)
        .timestamp()
    )
    payload = _b64(json.dumps({"sub": parent.id, "exp": exp}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def authenticate_session(token: str | None, db: Session) -> Parent:
    try:
        if not token:
            raise ValueError
        payload, signature = token.split(".", 1)
        expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) <= int(utcnow().replace(tzinfo=UTC).timestamp()):
            raise ValueError
        parent = db.get(Parent, int(data["sub"]))
        if parent is None:
            raise ValueError
        return parent
    except AppError:
        raise
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AuthError("Invalid or expired session.", code="invalid_session") from None


def parent_from_authorization(authorization: str | None, db: Session) -> Parent:
    scheme, _, token = (authorization or "").partition(" ")
    return authenticate_session(token if scheme.lower() == "bearer" else None, db)
