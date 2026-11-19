"""Dependencies for providing application services."""


from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories import ReviewRepository
from app.services.github_service import GitHubClient
from app.services.ollama_service import OllamaClient
from app.services.review_service import ReviewService
from app.services.webhook_service import (
    GitHubClientFactory,
    WebhookService,
)


def get_review_repository(
    db: Session = Depends(get_db),
) -> ReviewRepository:
    """Provide a repository using the request-scoped database session."""

    return ReviewRepository(db)


def get_github_client_factory() -> GitHubClientFactory:
    """Provide a factory for creating GitHub API clients."""

    return GitHubClient


def get_ollama_client() -> OllamaClient:
    """Provide an Ollama client configured from application settings."""

    return OllamaClient()


def get_review_service(
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> ReviewService:
    """Provide a review service with its injected Ollama client."""

    return ReviewService(ollama_client=ollama_client)


def get_webhook_service(
    review_repository: ReviewRepository = Depends(get_review_repository),
    github_client_factory: GitHubClientFactory = Depends(
        get_github_client_factory
    ),
    review_service: ReviewService = Depends(get_review_service),
) -> WebhookService:
    """Provide a webhook service with its required dependencies."""

    return WebhookService(
        review_repository=review_repository,
        github_client_factory=github_client_factory,
        review_service=review_service,
    )
