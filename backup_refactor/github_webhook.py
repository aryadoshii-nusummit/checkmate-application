"""API endpoint for receiving GitHub push webhooks.

The API layer is responsible for:
1. Receiving the incoming HTTP request.
2. Using dependencies to authenticate and validate the webhook.
3. Calling the appropriate application services.
4. Returning a structured API response.

GitHub communication and AI review logic remain in their respective
service modules.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.github import verify_github_webhook
from app.models.github import (
    ChangedFileSummary,
    GitHubWebhookResponse,
    WebhookVerification,
)
from app.services.github_service import GitHubAPIError, GitHubClient
from app.services.review_service import review_commit_files


# Create a logger for tracking webhook processing and troubleshooting errors.
logger = logging.getLogger(__name__)

# All routes in this router will use the /webhooks URL prefix.
router = APIRouter(prefix="/webhooks", tags=["github"])


@router.post(
    "/github",
    response_model=GitHubWebhookResponse,
)
async def receive_github_webhook(
    verification: WebhookVerification = Depends(verify_github_webhook),
) -> GitHubWebhookResponse:
    """Receive a verified GitHub push event and trigger an AI code review.

    FastAPI executes verify_github_webhook before entering this function.

    The dependency has already:
    - Verified the GitHub signature.
    - Checked the event type.
    - Validated the required push-payload fields.
    - Checked the branch configuration.
    - Validated the commit SHA.

    This endpoint therefore focuses on coordinating the services and
    returning the result to GitHub.
    """

    # ---------------------------------------------------------
    # 1. Handle valid events that do not require a code review.
    # ---------------------------------------------------------
    # The dependency returns an ignored_reason when the request is
    # authenticated but does not represent a supported review event.
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

    # ---------------------------------------------------------
    # 2. Retrieve the validated information from the dependency.
    # ---------------------------------------------------------
    # These values have already passed the dependency's validation.
    # The assertions make the non-optional values explicit to type checkers.
    repository_name = verification.repository
    branch = verification.branch
    commit_sha = verification.commit_sha
    delivery_id = verification.delivery_id

    assert repository_name is not None
    assert branch is not None
    assert commit_sha is not None

    logger.info(
        "Processing push: delivery=%s repository=%s branch=%s commit=%s",
        delivery_id,
        repository_name,
        branch,
        commit_sha,
    )

    # ---------------------------------------------------------
    # 3. Retrieve commit details from GitHub.
    # ---------------------------------------------------------
    # GitHubClient handles the external GitHub REST API communication.
    # The route does not contain HTTP request implementation details.
    try:
        async with GitHubClient() as github:
            commit_data = await github.fetch_commit(
                repository_name,
                commit_sha,
            )

    # Invalid inputs passed to the GitHub service are reported as
    # HTTP 400 responses because the requested resource cannot be fetched.
    except ValueError as exc:
        logger.warning("Invalid GitHub retrieval input: %s", exc)

        raise HTTPException(
            status_code=400,
            detail="Invalid repository or commit information.",
        ) from exc

    # A failure from the external GitHub API is reported as a gateway error.
    except GitHubAPIError as exc:
        logger.exception(
            "GitHub retrieval failed for %s at %s",
            repository_name,
            commit_sha,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Could not retrieve the commit from GitHub. Check the "
                "repository, commit SHA, API access, and GitHub API availability."
            ),
        ) from exc

    # ---------------------------------------------------------
    # 4. Create safe summaries of the changed files.
    # ---------------------------------------------------------
    # Return file metadata rather than the actual source code.
    # This keeps the webhook response concise and avoids exposing
    # repository contents unnecessarily.
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
        repository_name,
        len(file_summaries),
    )

    # ---------------------------------------------------------
    # 5. Delegate the AI review to the review service.
    # ---------------------------------------------------------
    # The review service decides which files can be reviewed and
    # coordinates the local Ollama model.
    # No AI review logic is implemented directly in this API route.
    try:
        review_result = await review_commit_files(
            commit_data["files"]
        )

    except Exception as exc:
        logger.exception(
            "AI review failed for %s at %s",
            repository_name,
            commit_sha,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The commit was retrieved, but the AI code review failed. "
                "Check that Ollama is running and the configured model "
                "is available."
            ),
        ) from exc

    # ---------------------------------------------------------
    # 6. Log the review totals.
    # ---------------------------------------------------------
    logger.info(
        "AI review completed for %s: reviewed=%d skipped=%d",
        repository_name,
        review_result["reviewed_file_count"],
        review_result["skipped_file_count"],
    )

    # ---------------------------------------------------------
    # 7. Return the structured API response.
    # ---------------------------------------------------------
    # Pydantic validates the response against GitHubWebhookResponse.
    # The JSON field names remain compatible with the previous endpoint.
    return GitHubWebhookResponse(
        status="accepted",
        message="GitHub commit retrieved and AI review completed.",
        delivery_id=delivery_id,
        repository=commit_data["repository"],
        branch=branch,
        commit=commit_data["commit"],
        commit_message=commit_data["message"],
        changed_file_count=len(file_summaries),
        files=file_summaries,
        reviewed_file_count=review_result["reviewed_file_count"],
        skipped_file_count=review_result["skipped_file_count"],
        reviews=review_result["reviews"],
        skipped_files=review_result["skipped_files"],
    )