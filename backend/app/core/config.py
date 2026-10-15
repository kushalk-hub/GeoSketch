"""Application configuration.

Everything configurable lives here and is overridable through environment
variables (prefix ``GEOSKETCH_``) or a ``backend/.env`` file.  No credential is
ever hard-coded in source: the real ``.env`` is git-ignored and only
``.env.example`` is committed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/  and  GeoSketch/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


def _split_csv(value: Any) -> Any:
    """Accept both ``"a,b"`` and ``'["a","b"]'`` style values."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            return value  # let pydantic parse the JSON list
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Runtime settings for the GeoSketch API."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        env_prefix="GEOSKETCH_",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    app_name: str = "GeoSketch API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # --- Persistence -------------------------------------------------------
    # SQLite by default.  Swapping to PostgreSQL only requires changing this
    # value (and installing the driver), because all data access goes through
    # SQLAlchemy with portable column types.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'geosketch.db').as_posix()}"

    # --- HTTP --------------------------------------------------------------
    # Kept as a plain string on purpose: pydantic-settings would try to JSON
    # decode a ``List[str]`` field before any validator runs, which makes the
    # documented comma separated form ("a,b") fail at import time.  Use
    # ``cors_origin_list`` to read it.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_request_bytes: int = 64 * 1024
    rate_limit_requests: int = 240
    rate_limit_window_seconds: int = 60

    # --- Device authentication --------------------------------------------
    # "device_id:api_key" pairs, comma separated.  Bootstrapped (hashed) into
    # the devices table at startup.
    device_keys: str = "geosketch-01:change-me-device-key"
    default_owner: str = "local"
    device_offline_after_seconds: int = 30

    # --- Route processing --------------------------------------------------
    min_point_distance_m: float = 1.0
    max_plausible_speed_kmh: float = 200.0
    max_gap_seconds: int = 180
    #: A fix is rejected when it implies an impossible speed from the previous
    #: fix.  If that keeps happening (for example the module reports a wrong
    #: date, making time deltas meaningless) the device has most likely really
    #: moved: after this many consecutive rejections the fix is trusted again so
    #: a recording can never silently stall.
    reanchor_after_rejects: int = 3

    # --- Storage -----------------------------------------------------------
    artwork_dir: Path = PROJECT_ROOT / "data" / "artworks"
    sample_routes_dir: Path = PROJECT_ROOT / "data" / "sample_routes"

    # ------------------------------------------------------------------
    @field_validator("artwork_dir", "sample_routes_dir", mode="before")
    @classmethod
    def _resolve_dir(cls, value: Any) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            # Relative paths are resolved against the backend directory so the
            # same .env works regardless of the shell's working directory.
            path = (BACKEND_DIR / path).resolve()
        return path

    # ------------------------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        """Browser origins allowed to call the API.

        Accepts ``"a,b"`` as well as a JSON-ish ``'["a","b"]'`` value, so both
        the .env.example form and a JSON form work.
        """
        parsed = _split_csv(self.cors_origins)
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                parsed = [self.cors_origins]
        return [str(origin).strip() for origin in parsed if str(origin).strip()]

    @property
    def device_key_map(self) -> dict[str, str]:
        """Parse ``device_keys`` into ``{device_id: api_key}``."""
        mapping: dict[str, str] = {}
        for chunk in self.device_keys.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" not in chunk:
                continue
            device_id, api_key = chunk.split(":", 1)
            device_id = device_id.strip()
            api_key = api_key.strip()
            if device_id and api_key:
                mapping[device_id] = api_key
        return mapping

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance."""
    settings = Settings()
    settings.artwork_dir.mkdir(parents=True, exist_ok=True)
    return settings


def reset_settings_cache() -> None:
    """Clear the cache (used by tests)."""
    get_settings.cache_clear()
