"""
GitHub webhook API endpoints.

This module exposes the HTTP endpoint used by GitHub to notify Checkmate
when a repository receives a push event.

Responsibilities of this API layer:
1. Receive incoming GitHub webhook requests.
2. Use FastAPI dependencies to authenticate and validate webhook data.
3. Obtain the application service responsible for processing the webhook.
4. Delegate the actual workflow to the service layer.
5. Return a structured response or an appropriate HTTP error.

Important:
GitHub API communication, commit retrieval, file processing, and AI-based
code reviews are intentionally handled by service modules rather than
inside this API endpoint. This keeps the API layer thin and maintainable.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

# Dependency responsible for authenticating and validating GitHub webhooks.
# FastAPI executes this dependency before calling the endpoint function.
from app.dependencies.github import verify_github_webhook

# Dependency that provides the application service responsible for
# coordinating GitHub commit retrieval and AI code review.
from app.dependencies.services import get_webhook_service

# Pydantic models define the validated webhook information received
# from the verification dependency and the response returned to GitHub.
from app.models.github import (
    GitHubWebhookResponse,
    WebhookVerification,
)

# The service handles the actual webhook processing workflow.
# WebhookProcessingError represents expected application-level failures
# that need to be translated into appropriate HTTP responses.
from app.services.webhook_service import (
    WebhookProcessingError,
    WebhookService,
)


# Use the module-level logger to record errors and operational information.
# This allows webhook processing issues to be traced without adding
# logging implementation details to the business logic.
logger = logging.getLogger(__name__)


# Group GitHub-related endpoints under the /webhooks URL prefix.
# The "github" tag also groups this endpoint in the FastAPI documentation.
router = APIRouter(
    prefix="/webhooks",
    tags=["github"],
)


@router.post(
    "/github",
    response_model=GitHubWebhookResponse,
)
async def receive_github_webhook(
    verification: WebhookVerification = Depends(verify_github_webhook),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> GitHubWebhookResponse:
    """
    Receive a GitHub webhook and delegate its processing to the service layer.

    FastAPI resolves both dependencies before executing this function:

    - verify_github_webhook:
      Verifies the webhook signature, validates the event and payload,
      and checks whether the pushed branch is configured for review.

    - get_webhook_service:
      Provides the service responsible for coordinating the review workflow.

    The endpoint does not directly communicate with GitHub or Ollama.
    It delegates those operations to WebhookService and returns its
    structured Pydantic response.

    Args:
        verification:
            Validated webhook information produced by the verification
            dependency.

        webhook_service:
            Application service that coordinates commit retrieval,
            changed-file processing, and AI code review.

    Returns:
        GitHubWebhookResponse:
            Structured response describing the webhook processing result.

    Raises:
        HTTPException:
            Returns an appropriate HTTP error when the service reports
            an expected webhook-processing failure.
    """

    try:
        # Delegate the complete webhook workflow to the application service.
        # The service handles ignored events, GitHub API communication,
        # changed-file summaries, AI reviews, and response preparation.
        return await webhook_service.process_webhook(verification)

    except WebhookProcessingError as exc:
        # Convert a known application-level error into an HTTP response.
        # Keeping this translation at the API boundary prevents the service
        # layer from depending directly on FastAPI's HTTPException.
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
