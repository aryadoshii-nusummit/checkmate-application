"""Receive GitHub push events and trigger AI-powered code reviews."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config.settings import ALLOWED_BRANCHES, GITHUB_WEBHOOK_SECRET
from app.services.github_service import GitHubAPIError, GitHubClient
from app.services.review_service import review_commit_files
from app.utils.webhook_signature import verify_github_signature

logger = logging.getLogger(__name__)

# Register all GitHub webhook endpoints under the /webhooks prefix.
router = APIRouter(prefix="/webhooks", tags=["github"])


@router.post("/github")
async def receive_github_webhook(request: Request) -> dict[str, Any]:
    # Read the original request body because GitHub calculates its
    # signature using the exact raw bytes sent in the webhook request.
    body = await request.body()

    # A configured secret is required to authenticate incoming webhooks.
    # Reject the request if the application has not been configured securely.
    if not GITHUB_WEBHOOK_SECRET:
        logger.error("GITHUB_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=500,
            detail="Webhook secret is not configured.",
        )

    # Verify that the request was signed using the shared GitHub secret.
    # This prevents unauthenticated clients from triggering code reviews.
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(
        body, signature, GITHUB_WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid GitHub webhook signature.",
        )

    # Extract event details for filtering, logging, and response tracking.
    event_name = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    # Checkmate currently processes push events only.
    # Other GitHub events are acknowledged but do not trigger a review.
    if event_name != "push":
        return {
            "status": "ignored",
            "reason": "unsupported_event",
            "event": event_name,
            "delivery_id": delivery_id,
        }

    # Parse the authenticated request body into a JSON object.
    # Invalid JSON is rejected before any GitHub API calls are made.
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Request body must be valid JSON.",
        ) from exc

    # A GitHub push payload must be a JSON object containing repository
    # and commit information.
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Webhook JSON must be an object.",
        )

    # Extract repository information to identify which project was updated.
    repository = payload.get("repository")

    if not isinstance(repository, dict):
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid repository information.",
        )

    # GitHub provides the repository in owner/repository format.
    repository_name = repository.get("full_name")

    if not isinstance(repository_name, str) or not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Missing repository.full_name.",
        )

    # Read the Git reference to determine whether the event represents
    # a branch push or a tag push.
    branch_ref = payload.get("ref")

    if not isinstance(branch_ref, str) or not branch_ref:
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid ref.",
        )

    # Only branch pushes are reviewed. Tag pushes are ignored because
    # they do not represent an update to a configured review branch.
    if not branch_ref.startswith("refs/heads/"):
        return {
            "status": "ignored",
            "reason": "not_a_branch_push",
            "ref": branch_ref,
            "delivery_id": delivery_id,
        }

    # Convert the full Git reference into its branch name.
    # Example: refs/heads/main becomes main.
    branch = branch_ref.removeprefix("refs/heads/")

    # Restrict reviews to branches defined in the application settings.
    # This prevents every branch push from automatically triggering reviews.
    if branch not in ALLOWED_BRANCHES:
        return {
            "status": "ignored",
            "reason": "branch_not_configured",
            "branch": branch,
            "allowed_branches": sorted(ALLOWED_BRANCHES),
            "delivery_id": delivery_id,
        }

    # The 'after' field contains the commit SHA at the end of the push.
    # This is the commit Checkmate will retrieve and review.
    commit_sha = payload.get("after")

    if not isinstance(commit_sha, str) or not commit_sha:
        raise HTTPException(
            status_code=400,
            detail="Missing target commit SHA in after field.",
        )

    # GitHub uses forty zeroes in the 'after' field when a branch is deleted.
    # Such events do not contain a commit that needs to be reviewed.
    if len(commit_sha) == 40 and set(commit_sha) == {"0"}:
        return {
            "status": "ignored",
            "reason": "branch_deleted",
            "branch": branch,
            "delivery_id": delivery_id,
        }

    # Validate the SHA format before passing it to the GitHub API.
    # A standard Git commit SHA contains exactly forty hexadecimal characters.
    if len(commit_sha) != 40 or any(
        character not in "0123456789abcdefABCDEF"
        for character in commit_sha
    ):
        raise HTTPException(
            status_code=400,
            detail="The after field must contain a valid 40-character SHA.",
        )

    # Record the accepted push details to help trace the review process
    # and troubleshoot failures using the GitHub delivery ID.
    logger.info(
        "Processing push: delivery=%s repository=%s branch=%s commit=%s",
        delivery_id,
        repository_name,
        branch,
        commit_sha,
    )

    # Step 1: Retrieve commit details and changed file contents from GitHub.
    # The GitHub client handles communication with the GitHub REST API.
    try:
        async with GitHubClient() as github:
            commit_data = await github.fetch_commit(
                repository_name,
                commit_sha,
            )

    # Invalid repository or commit inputs are treated as client-side errors.
    except ValueError as exc:
        logger.warning("Invalid GitHub retrieval input: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Invalid repository or commit information.",
        ) from exc

    # GitHub API failures are reported as gateway errors because Checkmate
    # could not retrieve the commit from the external GitHub service.
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

    # Build a safe summary of the changed files for the webhook response.
    # Source code is not included; only file metadata and availability details
    # are returned.
    file_summaries = [
        {
            "path": item["path"],
            "status": item["status"],
            "additions": item["additions"],
            "deletions": item["deletions"],
            "changes": item["changes"],
            "patch_available": bool(item.get("patch")),
            "content_available": item.get("content") is not None,
            "content_characters": len(item.get("content") or ""),
        }
        for item in commit_data["files"]
    ]

    # Log the number of changed files retrieved for this commit.
    logger.info(
        "Retrieved commit %s from %s: %d changed files",
        commit_data["commit"],
        repository_name,
        len(file_summaries),
    )

    # Step 2: Pass the changed files to the review service.
    # The review service filters unsupported files and sends eligible
    # source code to the locally running Ollama model.
    try:
        review_result = await review_commit_files(
            commit_data["files"]
        )

    # If the AI review fails, log the error and return a gateway response.
    # The commit may have been retrieved successfully, but its review
    # could not be completed.
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

    # Record the review totals to make it easier to monitor each run.
    logger.info(
        "AI review completed for %s: reviewed=%d skipped=%d",
        repository_name,
        review_result["reviewed_file_count"],
        review_result["skipped_file_count"],
    )

    # Return commit metadata, file summaries, review reports,
    # and details of files that were skipped by the review service.
    return {
        "status": "accepted",
        "message": "GitHub commit retrieved and AI review completed.",
        "delivery_id": delivery_id,
        "repository": commit_data["repository"],
        "branch": branch,
        "commit": commit_data["commit"],
        "commit_message": commit_data["message"],
        "changed_file_count": len(file_summaries),
        "files": file_summaries,
        "reviewed_file_count": review_result["reviewed_file_count"],
        "skipped_file_count": review_result["skipped_file_count"],
        "reviews": review_result["reviews"],
        "skipped_files": review_result["skipped_files"],
    }
