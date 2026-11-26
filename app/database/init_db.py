"""
Initializes the database schema asynchronously.

All registered SQLAlchemy models are created during application startup.
"""

import logging

from app.database.base import Base
from app.database.models import FileReview, ReviewRun
from app.database.session import engine


logger = logging.getLogger(__name__)


async def initialize_database() -> None:
    """
    Create registered database tables if they do not already exist.

    run_sync bridges SQLAlchemy's synchronous metadata operation into
    the asynchronous engine connection.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    logger.info(
        "Database initialized successfully. Registered tables: %s",
        list(Base.metadata.tables.keys()),
    )
