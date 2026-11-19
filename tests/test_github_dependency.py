"""Tests for GitHub webhook authentication and payload verification."""

import asyncio
import json

import pytest
from starlette.requests import Request

import app.dependencies.github as github_dependency


def make_request(payload: dict) -> Request:
    """Build a Starlette request containing a GitHub push payload."""
    body = json.dumps(payload).encode("utf-8")

    async def receive():
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/github",
        "headers": [
            (b"x-hub-signature-256", b"sha256=test-signature"),
            (b"x-github-event", b"push"),
            (b"x-github-delivery", b"test-sender-delivery"),
        ],
    }

    return Request(scope, receive)


@pytest.fixture
def valid_push_payload():
    """Provide a valid push event with sender information."""
    return {
        "repository": {
            "full_name": "owner/test-repo",
        },
        "ref": "refs/heads/main",
        "after": "a" * 40,
        "sender": {
            "login": "test-developer",
        },
    }


def test_extracts_github_sender_login(
    monkeypatch,
    valid_push_payload,
):
    """The authenticated push payload's sender becomes updated_by."""
    monkeypatch.setattr(
        github_dependency,
        "GITHUB_WEBHOOK_SECRET",
        "test-secret",
    )
    monkeypatch.setattr(
        github_dependency,
        "ALLOWED_BRANCHES",
        {"main"},
    )
    monkeypatch.setattr(
        github_dependency,
        "verify_github_signature",
        lambda *args, **kwargs: True,
    )

    request = make_request(valid_push_payload)

    verification = asyncio.run(
        github_dependency.verify_github_webhook(request)
    )

    assert verification.event_name == "push"
    assert verification.repository == "owner/test-repo"
    assert verification.branch == "main"
    assert verification.updated_by == "test-developer"


def test_missing_sender_returns_none(monkeypatch, valid_push_payload):
    """A push payload without sender information remains valid."""
    monkeypatch.setattr(
        github_dependency,
        "GITHUB_WEBHOOK_SECRET",
        "test-secret",
    )
    monkeypatch.setattr(
        github_dependency,
        "ALLOWED_BRANCHES",
        {"main"},
    )
    monkeypatch.setattr(
        github_dependency,
        "verify_github_signature",
        lambda *args, **kwargs: True,
    )

    valid_push_payload.pop("sender")
    request = make_request(valid_push_payload)

    verification = asyncio.run(
        github_dependency.verify_github_webhook(request)
    )

    assert verification.updated_by is None
