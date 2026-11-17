"""
Database initialization utilities.

Creates all registered SQLAlchemy tables in the configured database.

ORM models must be imported before create_all() so their table
definitions are registered with Base.metadata.
"""

import logging

from app.database.base import Base
from app.database.models import FileReview, ReviewRun  # noqa: F401
from app.database.session import engine

logger = logging.getLogger(__name__)


def initialize_database() -> None:
    """
    Create database tables that do not already exist.

    Existing tables and their data are preserved. This is suitable
    for initial schema creation, not for modifying existing schemas.
    Use database migrations when the schema evolves.
    """

    Base.metadata.create_all(bind=engine)

    logger.info(
        "Database initialized successfully. Registered tables: %s",
        list(Base.metadata.tables.keys()),
    )
