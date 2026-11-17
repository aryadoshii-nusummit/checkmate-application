"""
SQLAlchemy models for storing Checkmate code-review history.

ReviewRun represents one GitHub webhook-triggered review.
FileReview represents the review result for an individual changed file.

A review run can contain multiple file reviews. The relationship
preserves the commit-level context while allowing per-file reporting.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ReviewRun(Base):
    """
    Stores metadata and aggregate results for one code-review run.

    The GitHub delivery ID is unique so that the same webhook delivery
    cannot accidentally create multiple review records.
    """

    __tablename__ = "review_runs"

    __table_args__ = (
        CheckConstraint(
            "total_issues >= 0",
            name="ck_review_runs_total_issues_nonnegative",
        ),
        CheckConstraint(
            "total_warnings >= 0",
            name="ck_review_runs_total_warnings_nonnegative",
        ),
        CheckConstraint(
            "total_suggestions >= 0",
            name="ck_review_runs_total_suggestions_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    delivery_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    repository: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    commit_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    commit_author: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="completed",
        nullable=False,
    )

    total_issues: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_warnings: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_suggestions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # One review run can contain results for multiple changed files.
    file_reviews: Mapped[list["FileReview"]] = relationship(
        back_populates="review_run",
        cascade="all, delete-orphan",
    )


class FileReview(Base):
    """
    Stores the AI review result and finding counts for one file.

    The review report retains the human-readable Markdown output.
    Structured findings are stored separately for reliable reporting.
    """

    __tablename__ = "file_reviews"

    __table_args__ = (
        CheckConstraint(
            "issues_count >= 0",
            name="ck_file_reviews_issues_nonnegative",
        ),
        CheckConstraint(
            "warnings_count >= 0",
            name="ck_file_reviews_warnings_nonnegative",
        ),
        CheckConstraint(
            "suggestions_count >= 0",
            name="ck_file_reviews_suggestions_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    review_run_id: Mapped[int] = mapped_column(
        ForeignKey("review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    file_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    issues_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    warnings_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    suggestions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Preserve the structured AI review so it can be retrieved without
    # reconstructing information from the Markdown report.
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    overall_quality: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    strengths: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    areas_to_improve: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    additional_suggestions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    review_report: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    findings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # Each file review belongs to exactly one review run.
    review_run: Mapped["ReviewRun"] = relationship(
        back_populates="file_reviews",
    )
