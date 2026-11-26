
"""
Database initialization compatibility module.

Database schema creation and updates are managed through Alembic.

Run the following command before starting the application:

    python -m alembic upgrade head
"""

import logging

logger = logging.getLogger(__name__)


async def initialize_database() -> None:
    """
    Confirm that database schema management is handled by Alembic.

    This function intentionally does not create or modify database tables.
    """
    logger.info(
        "Database schema management is handled by Alembic. "
        "Run 'python -m alembic upgrade head' before application startup."
    )
