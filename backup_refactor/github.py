"""Pydantic models used by the GitHub webhook API.

These models define the structure of incoming GitHub push data and
outgoing Checkmate webhook responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class GitHubRepository(BaseModel):
    """Repository information included in a GitHub push payload."""

    # GitHub identifies a repository using the owner/repository format.
    # min_length=1 prevents an empty repository name from being accepted.
    full_name: str = Field(min_length=1)


class GitHubPushPayload(BaseModel):
    """The GitHub push-payload fields required by Checkmate."""

    # Only the fields needed by Checkmate are declared here.
    # GitHub sends additional fields, which Pydantic ignores by default.
    # min_length=1 ensures these required values are not empty strings.
    repository: GitHubRepository
    ref: str = Field(min_length=1)
    after: str = Field(min_length=1)


class WebhookVerification(BaseModel):
    """Result produced after authenticating and checking a webhook.

    This is an internal dependency result, not the public API response.
    It carries the information the route needs without repeating
    signature, branch, or commit validation.
    """

    event_name: str
    delivery_id: str
    repository: str | None = None
    ref: str | None = None
    branch: str | None = None
    commit_sha: str | None = None

    # A value here means the webhook is valid but should not trigger a review.
    ignored_reason: str | None = None

    # Included when the branch is not configured, to explain why it was ignored.
    allowed_branches: list[str] = Field(default_factory=list)


class ChangedFileSummary(BaseModel):
    """Safe metadata about a changed file returned by the webhook."""

    path: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch_available: bool
    content_available: bool
    content_characters: int


class FileReview(BaseModel):
    """AI review report for one changed file."""

    path: str
    status: str
    review: str


class SkippedFile(BaseModel):
    """Information about a file that the review service did not process."""

    path: str
    reason: str

    # These fields are populated when a file exceeds the configured line limit.
    line_count: int | None = None
    line_limit: int | None = None


class GitHubWebhookResponse(BaseModel):
    """Public response returned by the GitHub webhook endpoint.

    Optional fields allow this model to represent both ignored events
    and successfully completed reviews without changing existing responses.
    """

    status: str
    message: str | None = None
    reason: str | None = None
    event: str | None = None
    ref: str | None = None
    allowed_branches: list[str] | None = None
    delivery_id: str | None = None

    repository: str | None = None
    branch: str | None = None
    commit: str | None = None
    commit_message: str | None = None

    changed_file_count: int | None = None
    files: list[ChangedFileSummary] | None = None

    reviewed_file_count: int | None = None
    skipped_file_count: int | None = None
    reviews: list[dict[str, Any]] | None = None
    skipped_files: list[dict[str, Any]] | None = None