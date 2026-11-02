"""Application entry point for the Checkmate code review system."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.github_webhook import router as github_webhook_router
from app.config.settings import APP_NAME


# Initialize the FastAPI application using the configured application name.
# The metadata is displayed in the automatically generated API documentation.
app = FastAPI(
    title=APP_NAME,
    description="Webhook-driven code review using GitHub, FastAPI, and Ollama.",
    version="0.2.0",
)


# Register the health router to provide an endpoint for checking
# whether the Checkmate application is running.
app.include_router(health_router)

# Register the GitHub webhook router to receive push events.
# Incoming events are validated and passed through the code review workflow.
app.include_router(github_webhook_router)