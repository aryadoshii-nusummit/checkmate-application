
"""Unit tests for Checkmate's webhook orchestration service.

These tests verify webhook processing without making external GitHub
or Ollama requests. External dependencies are mocked at the service boundary.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.github import WebhookVerification
from app.repositories import ReviewRepository
from app.services.ollama_service import OllamaClient
from app.services.review_service import ReviewService
import app.services.webhook_service as webhook_service_module
from app.services.webhook_service import (
    WebhookProcessingError,
    WebhookService,
)


def run_async(coroutine):
    """Run an asynchronous service operation in a synchronous pytest test."""
    return asyncio.run(coroutine)


def make_verification(**overrides):
    """Create a valid webhook verification fixture."""
    data = {
        "event_name": "push",
        "delivery_id": "test-delivery-001",
        "repository": "owner/test-repo",
        "ref": "refs/heads/main",
        "branch": "main",
        "commit_sha": "abc123",
        "ignored_reason": None,
        "allowed_branches": ["main"],
    }
    data.update(overrides)
    return WebhookVerification(**data)


def make_commit_response():
    """Create a minimal GitHub commit response for service testing."""
    return {
        "repository": "owner/test-repo",
        "commit": "abc123",
        "message": "Add sample feature",
        "files": [
            {
                "path": "app.py",
                "status": "modified",
                "additions": 5,
                "deletions": 2,
                "changes": 7,
                "patch": "@@ -1 +1 @@",
                "content": "print('Checkmate')",
            }
        ],
    }


def make_github_context(commit_response):
    """Create a mocked asynchronous GitHub client context manager."""
    github_client = AsyncMock()
    github_client.fetch_commit = AsyncMock(
        return_value=commit_response
    )

    github_context = AsyncMock()
    github_context.__aenter__.return_value = github_client

    return github_context, github_client


def make_webhook_service(db_session):
    """Build the webhook service with injected test dependencies."""
    return WebhookService(
        review_repository=ReviewRepository(db_session),
        github_client_factory=webhook_service_module.GitHubClient,
        review_service=ReviewService(OllamaClient()),
    )


def test_ignored_webhook_returns_ignored_response(db_session):
    """Ignored webhook events should return without external processing."""
    verification = make_verification(
        ignored_reason="branch_not_configured"
    )

    response = run_async(
        make_webhook_service(db_session).process_webhook(verification)
    )

    assert response.status == "ignored"
    assert response.reason == "branch_not_configured"
    assert response.delivery_id == "test-delivery-001"


def test_missing_verified_commit_information_returns_server_error(db_session):
    """Missing repository, branch, or commit information should be rejected."""
    verification = make_verification(branch=None)

    with pytest.raises(WebhookProcessingError) as exc_info:
        run_async(
            make_webhook_service(db_session).process_webhook(verification)
        )

    assert exc_info.value.status_code == 500
    assert "missing required commit information" in exc_info.value.detail


def test_successful_webhook_processing(db_session):
    """A valid push should fetch the commit and invoke the review service."""
    verification = make_verification()
    commit_response = make_commit_response()

    github_context, github_client = make_github_context(
        commit_response
    )

    review_result = {
        "reviewed_file_count": 0,
        "skipped_file_count": 0,
        "reviews": [],
        "skipped_files": [],
    }

    with (
        patch(
            "app.services.webhook_service.GitHubClient",
            return_value=github_context,
        ),
        patch(
            "app.services.review_service.ReviewService.review_commit_files",
            new_callable=AsyncMock,
            return_value=review_result,
        ) as review_mock,
    ):
        response = run_async(
            make_webhook_service(db_session).process_webhook(verification)
        )

    github_client.fetch_commit.assert_awaited_once_with(
        "owner/test-repo",
        "abc123",
    )

    review_mock.assert_awaited_once_with(
        commit_response["files"]
    )

    assert response.status != "ignored"
    assert response.repository == "owner/test-repo"
    assert response.commit == "abc123"
    assert response.commit_message == "Add sample feature"
    assert response.changed_file_count == 1
    assert response.reviewed_file_count == 0
    assert response.skipped_file_count == 0


def test_review_failure_returns_bad_gateway(db_session):
    """Review failures should be translated into a service-level error."""
    verification = make_verification()
    github_context, _ = make_github_context(
        make_commit_response()
    )

    with (
        patch(
            "app.services.webhook_service.GitHubClient",
            return_value=github_context,
        ),
        patch(
            "app.services.review_service.ReviewService.review_commit_files",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Simulated review failure"),
        ),
    ):
        with pytest.raises(WebhookProcessingError) as exc_info:
            run_async(
                make_webhook_service(db_session).process_webhook(verification)
            )

    assert exc_info.value.status_code == 502
    assert "AI code review failed" in exc_info.value.detail


@pytest.fixture
def db_session():
    """Provide an isolated in-memory database for webhook service tests."""

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database.base import Base
    from app.database.models import FileReview, ReviewRun

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    session = testing_session()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()

def test_duplicate_delivery_returns_saved_review_without_reprocessing(db_session):
    """Repeated deliveries should return stored results without external calls."""
    verification = make_verification()
    commit_response = make_commit_response()

    github_context, github_client = make_github_context(commit_response)

    review_result = {
        "reviewed_file_count": 1,
        "skipped_file_count": 0,
        "reviews": [
            {
                "path": "app/example.py",
                "status": "modified",
                "review": "## Review\\n\\nOne issue identified.",
                "findings": [{
                            "title": "Example issue",
                            "severity": "HIGH",
                            "confidence": "HIGH",
                            "category": "security",
                            "line_numbers": [10],
                            "evidence": "Example vulnerable code",
                            "problem": "The code contains a security issue.",
                            "impact": "The issue could affect application security.",
                            "recommendation": "Correct the vulnerable implementation.",
                        }
                ],
                "issues_count": 1,
                "warnings_count": 0,
                "suggestions_count": 0,
            }
        ],
        "skipped_files": [],
    }

    # Process the first delivery and persist its review.
    with (
        patch(
            "app.services.webhook_service.GitHubClient",
            return_value=github_context,
        ),
        patch(
            "app.services.review_service.ReviewService.review_commit_files",
            new_callable=AsyncMock,
            return_value=review_result,
        ) as first_review_mock,
    ):
        first_response = run_async(
            make_webhook_service(db_session).process_webhook(verification)
        )

    assert first_response.status == "accepted"
    github_client.fetch_commit.assert_awaited_once_with(
        "owner/test-repo",
        "abc123",
    )
    first_review_mock.assert_awaited_once_with(commit_response["files"])

    # Process the same delivery again. Neither external dependency should run.
    with (
        patch(
            "app.services.webhook_service.GitHubClient"
        ) as github_mock,
        patch(
            "app.services.review_service.ReviewService.review_commit_files",
            new_callable=AsyncMock,
        ) as review_mock,
    ):
        duplicate_response = run_async(
            make_webhook_service(db_session).process_webhook(verification)
        )

    assert duplicate_response.status == "duplicate"
    assert duplicate_response.delivery_id == verification.delivery_id
    assert duplicate_response.repository == "owner/test-repo"
    assert duplicate_response.commit == "abc123"
    assert duplicate_response.reviewed_file_count == 1
    assert duplicate_response.reviews[0].path == "app/example.py"

    github_mock.assert_not_called()
    review_mock.assert_not_awaited()
