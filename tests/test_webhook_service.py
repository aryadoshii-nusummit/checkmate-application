
"""Unit tests for Checkmate's webhook orchestration service.

These tests verify webhook processing without making external GitHub
or Ollama requests. External dependencies are mocked at the service boundary.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.github import WebhookVerification
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


def test_ignored_webhook_returns_ignored_response():
    """Ignored webhook events should return without external processing."""
    verification = make_verification(
        ignored_reason="Branch is not configured"
    )

    response = run_async(
        WebhookService().process_webhook(verification)
    )

    assert response.status == "ignored"
    assert response.reason == "Branch is not configured"
    assert response.delivery_id == "test-delivery-001"


def test_missing_verified_commit_information_returns_server_error():
    """Missing repository, branch, or commit information should be rejected."""
    verification = make_verification(branch=None)

    with pytest.raises(WebhookProcessingError) as exc_info:
        run_async(
            WebhookService().process_webhook(verification)
        )

    assert exc_info.value.status_code == 500
    assert "missing required commit information" in exc_info.value.detail


def test_successful_webhook_processing():
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
            "app.services.webhook_service.review_commit_files",
            new_callable=AsyncMock,
            return_value=review_result,
        ) as review_mock,
    ):
        response = run_async(
            WebhookService().process_webhook(verification)
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


def test_review_failure_returns_bad_gateway():
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
            "app.services.webhook_service.review_commit_files",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Simulated review failure"),
        ),
    ):
        with pytest.raises(WebhookProcessingError) as exc_info:
            run_async(
                WebhookService().process_webhook(verification)
            )

    assert exc_info.value.status_code == 502
    assert "AI code review failed" in exc_info.value.detail
