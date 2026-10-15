"""Engine, session factory and schema bootstrap."""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine: Engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver level
        cursor = dbapi_connection.cursor()
        # Foreign keys are OFF by default in SQLite; the schema relies on them.
        cursor.execute("PRAGMA foreign_keys=ON")
        # WAL keeps the API responsive while the artwork worker reads.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables.  Called on application startup.

    ``create_all`` is idempotent and sufficient for this project; introduce
    Alembic migrations when the schema starts to evolve in production.
    """
    # Importing the models package registers every mapper on ``Base.metadata``.
    from app import models  # noqa: F401
    from app.database.base import Base

    Base.metadata.create_all(bind=engine)
    logger.info("Database ready at %s", settings.database_url)
