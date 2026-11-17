"""
Application entry point for the Checkmate code review system.

Initializes application resources during startup and registers
the API routers used by the application.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.github_webhook import router as github_webhook_router
from app.config.settings import APP_NAME
from app.database.init_db import initialize_database


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown operations.

    Database tables are initialized before the application starts
    accepting requests.
    """

    logger.info("Starting Checkmate application...")

    initialize_database()

    logger.info("Checkmate database is ready.")

    yield

    logger.info("Shutting down Checkmate application...")


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
