"""
Manages the SQLite database engine and SQLAlchemy sessions.

The database file is stored in the project root by default.
DATABASE_URL can override the default connection string.

get_db() provides a request-scoped database session through FastAPI
dependency injection. Each session is closed after the request ends.
"""

import os
from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Resolve the project root independently of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Store the SQLite database in the project root.
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "checkmate.db"

# Allow the database connection to be configured through the environment.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
)

# SQLite requires this option when connections may be used across threads,
# as can happen in a FastAPI application.
connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

# Create the SQLAlchemy engine.
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable SQLite foreign-key enforcement for every connection.
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        """Enable foreign-key constraints on each SQLite connection."""

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Create a reusable factory for database sessions.
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    Provide a database session through FastAPI dependency injection.

    The session is always closed after the request finishes, including
    when an exception occurs.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
