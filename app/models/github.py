"""Pydantic schemas and workflow types used by GitHub webhook processing."""

from typing import Annotated, Literal, NotRequired, TypedDict
from pydantic import BaseModel, Field
from app.models.review import Quality, ReviewFinding

# Restrict status values to the states supported by the application.
WebhookStatus = Literal["accepted", "ignored", "duplicate"]

ReviewRunStatus = Literal["completed", "completed_with_skips"]

FileStatus = Literal[
    "added",
    "removed",
    "modified",
    "renamed",
    "copied",
    "unknown",
]

IgnoredReason = Literal[
    "unsupported_event",
    "not_a_branch_push",
    "branch_not_configured",
    "branch_deleted",
]


# Internal workflow types for data retrieved from GitHub.
class GitHubChangedFile(TypedDict):
    """Represent a changed file returned by the GitHub client."""

    path: str
    status: FileStatus
    additions: int
    deletions: int
    changes: int
    patch: str | None
    content: str | None


class ReviewFileResult(TypedDict):
    """Represent the review output for a file before persistence."""

    path: str
    status: FileStatus
    review: str
    quality: Quality
    summary: str
    strengths: list[str]
    areas_to_improve: list[str]
    findings: list[dict[str, object]]
    additional_suggestions: list[str]
    issues_count: int
    warnings_count: int
    suggestions_count: int


class SkippedFileResult(TypedDict):
    """Represent a file skipped during review and the reason."""

    path: str
    reason: Literal[
        "unsupported_file_type",
        "content_unavailable",
        "binary_file",
        "file_exceeds_line_limit",
    ]
    line_count: NotRequired[int]
    line_limit: NotRequired[int]

class ReviewServiceResult(TypedDict):
    """Represent the aggregate result produced by ReviewService."""

    reviews: list[ReviewFileResult]
    skipped_files: list[SkippedFileResult]
    reviewed_file_count: int
    skipped_file_count: int


# Incoming webhook request schemas.
class GitHubRepository(BaseModel):
    """Identify the repository associated with a GitHub event."""

    full_name: Annotated[str, Field(min_length=1, max_length=255)]


class GitHubSender(BaseModel):
    """Represent the GitHub account that triggered the webhook."""

    login: Annotated[str, Field(min_length=1, max_length=39)]


class GitHubPushPayload(BaseModel):
    """Validate the relevant fields in a GitHub push event."""

    repository: GitHubRepository
    ref: Annotated[str, Field(min_length=1, max_length=500)]
    after: Annotated[str, Field(min_length=1, max_length=40)]
    sender: GitHubSender | None = None


# Internal verification schema passed from API dependencies to services.
class WebhookVerification(BaseModel):
    """Carry validated webhook metadata from the API dependency."""

    event_name: Annotated[str, Field(min_length=1, max_length=100)]
    delivery_id: Annotated[str, Field(min_length=1, max_length=255)]
    repository: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    ref: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    branch: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    commit_sha: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    updated_by: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    ignored_reason: IgnoredReason | None = None
    allowed_branches: list[
        Annotated[str, Field(min_length=1, max_length=255)]
    ] = Field(default_factory=list)


# API response schemas.
class ChangedFileSummary(BaseModel):
    """Summarize a changed file retrieved from GitHub."""

    path: Annotated[str, Field(min_length=1, max_length=500)]
    status: FileStatus
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changes: int = Field(ge=0)
    patch_available: bool
    content_available: bool
    content_characters: int = Field(ge=0)


class FileReview(BaseModel):
    """Represent the structured review of one source file."""

    path: Annotated[str, Field(min_length=1, max_length=500)]
    status: FileStatus
    review: str = Field(min_length=1)
    quality: Quality | None = None
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    additional_suggestions: list[str] = Field(default_factory=list)
    issues_count: int = Field(default=0, ge=0)
    warnings_count: int = Field(default=0, ge=0)
    suggestions_count: int = Field(default=0, ge=0)


class SkippedFile(BaseModel):
    """Explain why a changed file was not reviewed."""

    path: Annotated[str, Field(min_length=1, max_length=500)]
    reason: Literal[
        "unsupported_file_type",
        "content_unavailable",
        "binary_file",
        "file_exceeds_line_limit",
    ]
    line_count: int | None = Field(default=None, ge=0)
    line_limit: int | None = Field(default=None, ge=1)


class GitHubWebhookResponse(BaseModel):
    """Return the outcome and review results of a GitHub webhook."""

    status: WebhookStatus
    message: str | None = None
    reason: IgnoredReason | None = None
    event: str | None = None
    ref: str | None = None
    allowed_branches: list[str] | None = None
    delivery_id: str | None = None
    repository: str | None = None
    branch: str | None = None
    commit: str | None = None
    commit_message: str | None = None
    changed_file_count: int | None = Field(default=None, ge=0)
    files: list[ChangedFileSummary] | None = None
    reviewed_file_count: int | None = Field(default=None, ge=0)
    skipped_file_count: int | None = Field(default=None, ge=0)
    reviews: list[FileReview] | None = None
    skipped_files: list[SkippedFile] | None = None
