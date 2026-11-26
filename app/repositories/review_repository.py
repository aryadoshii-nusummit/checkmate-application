"""Repository for asynchronously persisting and retrieving code reviews."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import FileReview, ReviewRun
from app.models.github import ReviewFileResult, ReviewRunStatus


logger = logging.getLogger(__name__)


class DuplicateDeliveryError(Exception):
    """Raised when a GitHub delivery has already been persisted."""


class ReviewRepository:
    """Manage review-run persistence and retrieval."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the repository with an injected async session."""
        self.db = db

    async def get_by_delivery_id(
        self,
        delivery_id: str,
    ) -> ReviewRun | None:
        """Retrieve an existing review run using its GitHub delivery ID."""

        statement = (
            select(ReviewRun)
            .options(selectinload(ReviewRun.file_reviews))
            .where(ReviewRun.delivery_id == delivery_id)
        )

        return await self.db.scalar(statement)

    async def save_review_run(
        self,
        *,
        delivery_id: str,
        repository: str,
        branch: str,
        commit_sha: str,
        updated_by: str,
        commit_author: str,
        status: ReviewRunStatus,
        reviews: list[ReviewFileResult],
    ) -> ReviewRun:
        """Persist a review run and its file reviews in one transaction."""

        existing = await self.get_by_delivery_id(delivery_id)

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

            # Flush to obtain the generated review_run.id.
            await self.db.flush()

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
                    additional_suggestions=review.get(
                        "additional_suggestions", []
                    ),
                )
                for review in reviews
            ]

            self.db.add_all(file_reviews)

            await self.db.commit()
            await self.db.refresh(review_run)

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
            await self.db.rollback()

            # Another concurrent webhook may have inserted this delivery.
            existing = await self.get_by_delivery_id(delivery_id)

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
            await self.db.rollback()

            logger.exception(
                "Failed to persist review run for delivery %s",
                delivery_id,
            )
            raise
