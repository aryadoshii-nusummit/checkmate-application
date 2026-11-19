
"""Application service for processing verified GitHub webhooks."""

import logging
from typing import Callable


from app.database.models import ReviewRun
from app.models.github import (
    ChangedFileSummary,
    FileReview,
    GitHubWebhookResponse,
    ReviewRunStatus,
    SkippedFile,
    WebhookVerification,
)
from app.repositories import DuplicateDeliveryError, ReviewRepository
from app.services.github_service import GitHubAPIError, GitHubClient
from app.services.review_service import ReviewService

logger = logging.getLogger(__name__)

GitHubClientFactory = Callable[[], GitHubClient]


class WebhookProcessingError(Exception):
    """Error raised when the webhook review workflow cannot be completed."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class WebhookService:
    """Coordinate GitHub retrieval, AI review, and result persistence."""

    def __init__(
        self,
        review_repository: ReviewRepository,
        github_client_factory: GitHubClientFactory,
        review_service: ReviewService,
    ) -> None:
        """Initialize the service with its injected dependencies."""

        self.review_repository = review_repository
        self.github_client_factory = github_client_factory
        self.review_service = review_service

    @staticmethod
    def _build_duplicate_response(
        review_run: ReviewRun,
    ) -> GitHubWebhookResponse:
        """Build an acknowledgement for an already persisted delivery."""

        stored_reviews = [
            FileReview(
                path=item.file_name,
                status=item.file_status,
                review=item.review_report,
                findings=item.findings,
                issues_count=item.issues_count,
                warnings_count=item.warnings_count,
                suggestions_count=item.suggestions_count,
                quality=item.overall_quality,
                summary=item.summary,
                strengths=item.strengths,
                areas_to_improve=item.areas_to_improve,
                additional_suggestions=item.additional_suggestions,
            )
            for item in review_run.file_reviews
        ]

        return GitHubWebhookResponse(
            status="duplicate",
            message="This GitHub delivery has already been processed.",
            delivery_id=review_run.delivery_id,
            repository=review_run.repository,
            branch=review_run.branch,
            commit=review_run.commit_sha,
            reviewed_file_count=len(stored_reviews),
            reviews=stored_reviews,
        )

    async def process_webhook(
        self,
        verification: WebhookVerification,
    ) -> GitHubWebhookResponse:
        """Process a verified webhook and persist its completed review."""

        if verification.ignored_reason:
            logger.info(
                "Ignoring GitHub webhook: delivery=%s reason=%s",
                verification.delivery_id,
                verification.ignored_reason,
            )
            return GitHubWebhookResponse(
                status="ignored",
                reason=verification.ignored_reason,
                event=verification.event_name,
                delivery_id=verification.delivery_id,
                repository=verification.repository,
                ref=verification.ref,
                branch=verification.branch,
                allowed_branches=(
                    verification.allowed_branches
                    if verification.allowed_branches
                    else None
                ),
            )

        repository = verification.repository
        branch = verification.branch
        commit_sha = verification.commit_sha

        if not repository or not branch or not commit_sha:
            raise WebhookProcessingError(
                500,
                "Verified webhook is missing required commit information.",
            )

        # Check idempotency before making external API or AI calls.
        try:
            existing_run = self.review_repository.get_by_delivery_id(
                verification.delivery_id
            )
        except Exception as exc:
            logger.exception(
                "Could not check existing delivery %s",
                verification.delivery_id,
            )
            raise WebhookProcessingError(
                500,
                "Could not check whether this GitHub delivery was processed.",
            ) from exc

        if existing_run is not None:
            logger.info(
                "Duplicate GitHub delivery received: %s",
                verification.delivery_id,
            )
            return self._build_duplicate_response(existing_run)

        logger.info(
            "Processing push: delivery=%s repository=%s branch=%s commit=%s",
            verification.delivery_id,
            repository,
            branch,
            commit_sha,
        )

        try:
            async with self.github_client_factory() as github:
                commit_data = await github.fetch_commit(
                    repository,
                    commit_sha,
                )
        except ValueError as exc:
            logger.warning("Invalid GitHub retrieval input: %s", exc)
            raise WebhookProcessingError(
                400,
                "Invalid repository or commit information.",
            ) from exc
        except GitHubAPIError as exc:
            logger.exception(
                "GitHub retrieval failed for %s at %s",
                repository,
                commit_sha,
            )
            raise WebhookProcessingError(
                502,
                (
                    "Could not retrieve the commit from GitHub. "
                    "Check repository access and GitHub API availability."
                ),
            ) from exc

        file_summaries = [
            ChangedFileSummary(
                path=item["path"],
                status=item["status"],
                additions=item["additions"],
                deletions=item["deletions"],
                changes=item["changes"],
                patch_available=bool(item.get("patch")),
                content_available=item.get("content") is not None,
                content_characters=len(item.get("content") or ""),
            )
            for item in commit_data["files"]
        ]

        logger.info(
            "Retrieved commit %s from %s: %d changed files",
            commit_data["commit"],
            repository,
            len(file_summaries),
        )

        try:
            review_result = await self.review_service.review_commit_files(
                commit_data["files"]
            )
        except Exception as exc:
            logger.exception(
                "AI review failed for %s at %s",
                repository,
                commit_sha,
            )
            raise WebhookProcessingError(
                502,
                (
                    "The commit was retrieved, but the AI code review failed. "
                    "Check that Ollama is running and the configured model "
                    "is available."
                ),
            ) from exc

        status: ReviewRunStatus = (
            "completed_with_skips"
            if review_result["skipped_file_count"] > 0
            else "completed"
        )

        try:
            self.review_repository.save_review_run(
                delivery_id=verification.delivery_id,
                repository=commit_data["repository"],
                branch=branch,
                commit_sha=commit_data["commit"],
                updated_by=verification.updated_by,
                commit_author=commit_data.get("commit_author"),
                status=status,
                reviews=review_result["reviews"],
            )
        except DuplicateDeliveryError:
            # Another request may have completed the same delivery
            # between the initial lookup and the database insert.
            existing_run = self.review_repository.get_by_delivery_id(
                verification.delivery_id
            )
            if existing_run is not None:
                return self._build_duplicate_response(existing_run)
            raise WebhookProcessingError(
                500,
                "The review delivery conflicted with another database operation.",
            )
        except Exception as exc:
            logger.exception(
                "Could not persist review results for delivery %s",
                verification.delivery_id,
            )
            raise WebhookProcessingError(
                500,
                "The review completed, but its results could not be saved.",
            ) from exc

        logger.info(
            "Review persisted: delivery=%s reviewed=%d skipped=%d status=%s",
            verification.delivery_id,
            review_result["reviewed_file_count"],
            review_result["skipped_file_count"],
            status,
        )

        return GitHubWebhookResponse(
            status="accepted",
            message="GitHub commit reviewed and results saved successfully.",
            delivery_id=verification.delivery_id,
            repository=commit_data["repository"],
            branch=branch,
            commit=commit_data["commit"],
            commit_message=commit_data["message"],
            changed_file_count=len(file_summaries),
            files=file_summaries,
            reviewed_file_count=review_result["reviewed_file_count"],
            skipped_file_count=review_result["skipped_file_count"],
            reviews=[FileReview(**item) for item in review_result["reviews"]],
            skipped_files=[
                SkippedFile(**item)
                for item in review_result["skipped_files"]
            ],
        )
