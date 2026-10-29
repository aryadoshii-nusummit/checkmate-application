"""Checkmate FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.github_webhook import router as github_webhook_router
from app.config import APP_NAME

app = FastAPI(
    title=APP_NAME,
    description="Webhook-driven code review using GitHub, FastAPI, and Ollama.",
    version="0.2.0",
)

app.include_router(health_router)
app.include_router(github_webhook_router)
