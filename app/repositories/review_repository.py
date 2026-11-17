
"""Persistence operations for completed Checkmate code reviews."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import FileReview, ReviewRun

logger = logging.getLogger(__name__)


class DuplicateDeliveryError(Exception):
    """Raised when a GitHub delivery has already been persisted."""


class ReviewRepository:
    """Manage review-run persistence and retrieval."""

    def __init__(self, db: Session) -> None:
        """Initialize the repository with an injected database session."""

        self.db = db

    def get_by_delivery_id(
        self,
        delivery_id: str,
    ) -> ReviewRun | None:
        """Retrieve an existing review run using its GitHub delivery ID."""

        statement = select(ReviewRun).where(
            ReviewRun.delivery_id == delivery_id
        )

        return self.db.scalar(statement)

    def save_review_run(
        self,
        *,
        delivery_id: str,
        repository: str,
        branch: str,
        commit_sha: str,
        updated_by: str | None,
        commit_author: str | None,
        status: str,
        reviews: list[dict[str, Any]],
    ) -> ReviewRun:
        """
        Persist a review run and all its file reviews atomically.

        The parent record and its file-review records are committed as one
        transaction. If any operation fails, the transaction is rolled back.
        """

        existing = self.get_by_delivery_id(delivery_id)

        if existing is not None:
            raise DuplicateDeliveryError(
                f"Delivery '{delivery_id}' has already been processed."
            )

        total_issues = sum(
            review.get("issues_count", 0)
            for review in reviews
        )
        total_warnings = sum(
            review.get("warnings_count", 0)
            for review in reviews
        )
        total_suggestions = sum(
            review.get("suggestions_count", 0)
            for review in reviews
        )

        review_run = ReviewRun(
            delivery_id=delivery_id,
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            updated_by=updated_by,
            commit_author=commit_author,
            status=status,
            total_issues=total_issues,
            total_warnings=total_warnings,
            total_suggestions=total_suggestions,
        )

        try:
            self.db.add(review_run)
            self.db.flush()

            file_reviews = [
                FileReview(
                    review_run_id=review_run.id,
                    file_name=review["path"],
                    file_status=review["status"],
                    issues_count=review.get("issues_count", 0),
                    warnings_count=review.get("warnings_count", 0),
                    suggestions_count=review.get("suggestions_count", 0),
                    review_report=review["review"],
                    findings=review.get("findings", []),
                    summary=review.get("summary"),
                    overall_quality=review.get("quality"),
                    strengths=review.get("strengths", []),
                    areas_to_improve=review.get("areas_to_improve", []),
                    additional_suggestions=review.get("additional_suggestions", []),
                )
                for review in reviews
            ]

            self.db.add_all(file_reviews)
            self.db.commit()
            self.db.refresh(review_run)

            logger.info(
                "Persisted review run: delivery=%s repository=%s "
                "files=%d status=%s",
                delivery_id,
                repository,
                len(file_reviews),
                status,
            )

            return review_run

        except IntegrityError as exc:
            self.db.rollback()

            # A concurrent webhook may have inserted this delivery after
            # the initial existence check.
            existing = self.get_by_delivery_id(delivery_id)

            if existing is not None:
                raise DuplicateDeliveryError(
                    f"Delivery '{delivery_id}' has already been processed."
                ) from exc

            logger.exception(
                "Database integrity error while saving delivery %s",
                delivery_id,
            )
            raise

        except Exception:
            self.db.rollback()
            logger.exception(
                "Failed to persist review run for delivery %s",
                delivery_id,
            )
            raise
