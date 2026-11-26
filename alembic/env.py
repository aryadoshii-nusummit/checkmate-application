"""Alembic migration environment for asynchronous SQLAlchemy."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection

from app.database.base import Base
from app.database import models  # noqa: F401
from app.database.session import ASYNC_DATABASE_URL, engine


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the application's actual ORM metadata for autogeneration.
target_metadata = Base.metadata

# Use the same database URL as the application.
config.set_main_option(
    "sqlalchemy.url",
    ASYNC_DATABASE_URL.replace("%", "%%"),
)


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    context.configure(
        url=ASYNC_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure and execute migrations using a synchronous bridge."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using the application's shared async engine."""

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
