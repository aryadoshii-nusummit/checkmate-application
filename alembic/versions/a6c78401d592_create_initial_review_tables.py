"""create initial review tables

Revision ID: a6c78401d592
Revises:
Create Date: 2026-11-26 17:35:45.337732
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "a6c78401d592"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial review database tables."""

    op.create_table(
        "review_runs",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "delivery_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "repository",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "branch",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "commit_sha",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "commit_author",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "total_issues",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "total_warnings",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "total_suggestions",
            sa.Integer(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "total_issues >= 0",
            name="ck_review_runs_total_issues_nonnegative",
        ),
        sa.CheckConstraint(
            "total_suggestions >= 0",
            name="ck_review_runs_total_suggestions_nonnegative",
        ),
        sa.CheckConstraint(
            "total_warnings >= 0",
            name="ck_review_runs_total_warnings_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id"),
    )

    op.create_table(
        "file_reviews",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "review_run_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "file_name",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "file_status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "issues_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "warnings_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "suggestions_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "overall_quality",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "strengths",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "areas_to_improve",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "additional_suggestions",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "review_report",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "findings",
            sa.JSON(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "issues_count >= 0",
            name="ck_file_reviews_issues_nonnegative",
        ),
        sa.CheckConstraint(
            "suggestions_count >= 0",
            name="ck_file_reviews_suggestions_nonnegative",
        ),
        sa.CheckConstraint(
            "warnings_count >= 0",
            name="ck_file_reviews_warnings_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["review_run_id"],
            ["review_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_file_reviews_review_run_id"),
        "file_reviews",
        ["review_run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the initial review database tables."""

    op.drop_index(
        op.f("ix_file_reviews_review_run_id"),
        table_name="file_reviews",
    )

    op.drop_table("file_reviews")
    op.drop_table("review_runs")
