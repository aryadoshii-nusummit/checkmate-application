
"""
Manages the asynchronous SQLite database engine and SQLAlchemy sessions.

The database URL can be overridden through the DATABASE_URL environment
variable. The default database remains checkmate.db in the project root.
"""

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


# Resolve the project root and preserve the existing database location.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "checkmate.db"

# Preserve the existing environment-variable override.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
)

# Convert the existing SQLite URL to its asynchronous driver equivalent.
if DATABASE_URL.startswith("sqlite:///"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace(
        "sqlite:///",
        "sqlite+aiosqlite:///",
        1,
    )
else:
    # Non-SQLite URLs must already specify a compatible async driver.
    ASYNC_DATABASE_URL = DATABASE_URL


# Create one asynchronous engine for the application process.
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
)


# Enable SQLite foreign-key enforcement on every connection.
if ASYNC_DATABASE_URL.startswith("sqlite+aiosqlite://"):

    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        """Enable SQLite foreign-key constraints for each connection."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


# Create one asynchronous session per request.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a request-scoped asynchronous database session.

    The session is automatically closed after the request completes,
    including when an exception occurs.
    """
    async with AsyncSessionLocal() as db:
        yield db
