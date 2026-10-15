"""Declarative base shared by every ORM model."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base.

    Using a single base with portable column types keeps the SQLite -> PostgreSQL
    migration path limited to the ``DATABASE_URL`` value.
    """
