"""Pydantic models used by the GitHub webhook API."""

from typing import Any

from pydantic import BaseModel, Field


class GitHubRepository(BaseModel):
    """Identify the repository associated with a GitHub event."""

    full_name: str = Field(min_length=1)


class GitHubSender(BaseModel):
    """Represent the GitHub account that triggered the webhook."""

    login: str = Field(min_length=1)


class GitHubPushPayload(BaseModel):
    """Validate the relevant fields in a GitHub push event."""

    repository: GitHubRepository
    ref: str = Field(min_length=1)
    after: str = Field(min_length=1)
    sender: GitHubSender | None = None


class WebhookVerification(BaseModel):
    """Carry validated webhook metadata from the API dependency."""

    event_name: str
    delivery_id: str
    repository: str | None = None
    ref: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    updated_by: str | None = None
    ignored_reason: str | None = None
    allowed_branches: list[str] = Field(default_factory=list)


class ChangedFileSummary(BaseModel):
    """Summarize a changed file retrieved from GitHub."""

    path: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch_available: bool
    content_available: bool
    content_characters: int


class FileReview(BaseModel):
    """Represent the structured review of one source file."""

    path: str
    status: str
    review: str
    quality: str | None = None
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    additional_suggestions: list[str] = Field(default_factory=list)
    issues_count: int = 0
    warnings_count: int = 0
    suggestions_count: int = 0


class SkippedFile(BaseModel):
    """Explain why a changed file was not reviewed."""

    path: str
    reason: str
    line_count: int | None = None
    line_limit: int | None = None


class GitHubWebhookResponse(BaseModel):
    """Return the outcome and review results of a GitHub webhook."""

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
    reviews: list[FileReview] | None = None
    skipped_files: list[SkippedFile] | None = None
