"""
Defines the shared SQLAlchemy declarative base for database models.

All ORM models inherit from Base so SQLAlchemy can register their table definitions in a single metadata collection.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all Checkmate database models."""

    pass
