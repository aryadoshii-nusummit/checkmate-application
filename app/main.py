"""Application entry point and lifecycle management for Checkmate."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.github_webhook import router as github_webhook_router
from app.config.settings import APP_NAME
from app.database.session import engine


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application resources during startup and shutdown.

    Database schema changes are managed separately through Alembic.
    Run migrations before starting the application.
    """
    logger.info("Starting Checkmate application...")

    try:
        logger.info("Checkmate application started. Database engine is ready.")

        yield

    finally:
        logger.info("Shutting down Checkmate application...")
        await engine.dispose()
        logger.info("Database engine connections disposed.")


# Initialize the FastAPI application and its lifecycle management.
app = FastAPI(
    title=APP_NAME,
    description="Webhook-driven code review using GitHub, FastAPI, and Ollama.",
    version="0.2.0",
    lifespan=lifespan,
)

# Register the health endpoint.
app.include_router(health_router)

# Register the GitHub webhook endpoint.
app.include_router(github_webhook_router)
