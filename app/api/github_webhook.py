
"""GitHub push webhook receiver connected to GitHub and Ollama code review."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import ALLOWED_BRANCHES, GITHUB_WEBHOOK_SECRET
from app.integrations.github_client import GitHubAPIError, GitHubClient
from app.review.orchestrator import review_commit_files
from app.security.webhook_signature import verify_github_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["github"])


@router.post("/github")
async def receive_github_webhook(request: Request) -> dict[str, Any]:
    # Verify the signature against the exact raw request bytes.
    body = await request.body()

    if not GITHUB_WEBHOOK_SECRET:
        logger.error("GITHUB_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=500,
            detail="Webhook secret is not configured.",
        )

    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(
        body, signature, GITHUB_WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid GitHub webhook signature.",
        )

    event_name = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    if event_name != "push":
        return {
            "status": "ignored",
            "reason": "unsupported_event",
            "event": event_name,
            "delivery_id": delivery_id,
        }

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Request body must be valid JSON.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Webhook JSON must be an object.",
        )

    repository = payload.get("repository")

    if not isinstance(repository, dict):
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid repository information.",
        )

    repository_name = repository.get("full_name")

    if not isinstance(repository_name, str) or not repository_name:
        raise HTTPException(
            status_code=400,
            detail="Missing repository.full_name.",
        )

    branch_ref = payload.get("ref")

    if not isinstance(branch_ref, str) or not branch_ref:
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid ref.",
        )

    # This version supports branch pushes, not tags.
    if not branch_ref.startswith("refs/heads/"):
        return {
            "status": "ignored",
            "reason": "not_a_branch_push",
            "ref": branch_ref,
            "delivery_id": delivery_id,
        }

    branch = branch_ref.removeprefix("refs/heads/")

    if branch not in ALLOWED_BRANCHES:
        return {
            "status": "ignored",
            "reason": "branch_not_configured",
            "branch": branch,
            "allowed_branches": sorted(ALLOWED_BRANCHES),
            "delivery_id": delivery_id,
        }

    commit_sha = payload.get("after")

    if not isinstance(commit_sha, str) or not commit_sha:
        raise HTTPException(
            status_code=400,
            detail="Missing target commit SHA in after field.",
        )

    # GitHub uses forty zeroes when a branch is deleted.
    if len(commit_sha) == 40 and set(commit_sha) == {"0"}:
        return {
            "status": "ignored",
            "reason": "branch_deleted",
            "branch": branch,
            "delivery_id": delivery_id,
        }

    if len(commit_sha) != 40 or any(
        character not in "0123456789abcdefABCDEF"
        for character in commit_sha
    ):
        raise HTTPException(
            status_code=400,
            detail="The after field must contain a valid 40-character SHA.",
        )

    logger.info(
        "Processing push: delivery=%s repository=%s branch=%s commit=%s",
        delivery_id,
        repository_name,
        branch,
        commit_sha,
    )

    # Step 1: Retrieve the commit and changed-file contents from GitHub.
    try:
        async with GitHubClient() as github:
            commit_data = await github.fetch_commit(
                repository_name,
                commit_sha,
            )
    except ValueError as exc:
        logger.warning("Invalid GitHub retrieval input: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Invalid repository or commit information.",
        ) from exc
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

    logger.info(
        "Retrieved commit %s from %s: %d changed files",
        commit_data["commit"],
        repository_name,
        len(file_summaries),
    )

    # Step 2: Send eligible changed-file contents to local Ollama.
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

    logger.info(
        "AI review completed for %s: reviewed=%d skipped=%d",
        repository_name,
        review_result["reviewed_file_count"],
        review_result["skipped_file_count"],
    )

    # Return review findings and file metadata, not the source code.
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
