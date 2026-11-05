"""Application service for processing verified GitHub webhooks."""

import logging

from app.models.github import (
    ChangedFileSummary,
    FileReview,
    GitHubWebhookResponse,
    SkippedFile,
    WebhookVerification,
)
from app.services.github_service import GitHubAPIError, GitHubClient
from app.services.review_service import review_commit_files

logger = logging.getLogger(__name__)


class WebhookProcessingError(Exception):
    """Error raised when the webhook review workflow cannot be completed."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class WebhookService:
    """Coordinate GitHub commit retrieval and AI code review."""

    async def process_webhook(
        self,
        verification: WebhookVerification,
    ) -> GitHubWebhookResponse:
        """Process a verified webhook and return its structured response."""

        # A valid webhook may be ignored if it does not require a review.
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

        # These fields are guaranteed by the verification dependency.
        # Keep a defensive check in case this service is called elsewhere.
        if not repository or not branch or not commit_sha:
            raise WebhookProcessingError(
                500,
                "Verified webhook is missing required commit information.",
            )

        logger.info(
            "Processing push: delivery=%s repository=%s branch=%s commit=%s",
            verification.delivery_id,
            repository,
            branch,
            commit_sha,
        )

        # Retrieve commit details and changed-file contents from GitHub.
        try:
            async with GitHubClient() as github:
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

        # Prepare safe metadata about changed files for the API response.
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

        # Delegate file filtering and AI review to the review service.
        try:
            review_result = await review_commit_files(
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

        logger.info(
            "AI review completed for %s: reviewed=%d skipped=%d",
            repository,
            review_result["reviewed_file_count"],
            review_result["skipped_file_count"],
        )

        # Return the final, typed API response.
        return GitHubWebhookResponse(
            status="accepted",
            message="GitHub commit retrieved and AI review completed.",
            delivery_id=verification.delivery_id,
            repository=commit_data["repository"],
            branch=branch,
            commit=commit_data["commit"],
            commit_message=commit_data["message"],
            changed_file_count=len(file_summaries),
            files=file_summaries,
            reviewed_file_count=review_result["reviewed_file_count"],
            skipped_file_count=review_result["skipped_file_count"],
            reviews=[
                FileReview(**item)
                for item in review_result["reviews"]
            ],
            skipped_files=[
                SkippedFile(**item)
                for item in review_result["skipped_files"]
            ],
        )