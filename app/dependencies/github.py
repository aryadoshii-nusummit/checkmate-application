"""Dependencies used to authenticate and validate GitHub webhooks."""

import json
import logging

from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config.settings import ALLOWED_BRANCHES, GITHUB_WEBHOOK_SECRET
from app.models.github import GitHubPushPayload, WebhookVerification
from app.utils.webhook_signature import verify_github_signature


logger = logging.getLogger(__name__)


async def verify_github_webhook(
    request: Request,
) -> WebhookVerification:
    """Authenticate a GitHub webhook and validate its push information.

    FastAPI executes this dependency before calling the route function.

    The dependency:
    1. Reads the original request body.
    2. Verifies GitHub's HMAC-SHA256 signature.
    3. Identifies the GitHub event.
    4. Validates the required push-payload fields.
    5. Checks whether the push targets an allowed branch.
    6. Validates the target commit SHA.

    A valid event that should not trigger a review is returned with
    an `ignored_reason`. Invalid or unauthenticated requests raise
    HTTPException and never reach the route's review workflow.
    """

    # ---------------------------------------------------------
    # 1. Read the original request body.
    # ---------------------------------------------------------
    # GitHub calculates its signature using the exact bytes sent.
    # Do not parse and re-serialize the JSON before signature verification.
    body = await request.body()

    # ---------------------------------------------------------
    # 2. Check that the webhook secret is configured.
    # ---------------------------------------------------------
    if not GITHUB_WEBHOOK_SECRET:
        logger.error("GITHUB_WEBHOOK_SECRET is not configured")

        raise HTTPException(
            status_code=500,
            detail="Webhook secret is not configured.",
        )

    # ---------------------------------------------------------
    # 3. Authenticate the request using GitHub's signature.
    # ---------------------------------------------------------
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(
        body,
        signature,
        GITHUB_WEBHOOK_SECRET,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid GitHub webhook signature.",
        )

    # The request is authenticated. We can now use its event headers.
    event_name = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    # ---------------------------------------------------------
    # 4. Ignore events that Checkmate does not process.
    # ---------------------------------------------------------
    # This preserves the existing behavior: non-push events are
    # acknowledged without attempting to parse a push payload.
    if event_name != "push":
        return WebhookVerification(
            event_name=event_name,
            delivery_id=delivery_id,
            ignored_reason="unsupported_event",
        )

    # ---------------------------------------------------------
    # 5. Parse the authenticated JSON payload.
    # ---------------------------------------------------------
    try:
        raw_payload = json.loads(body)

    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Request body must be valid JSON.",
        ) from exc

    # The top-level GitHub push payload must be a JSON object.
    if not isinstance(raw_payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Webhook JSON must be an object.",
        )

    # Pydantic checks that repository.full_name, ref, and after
    # exist and have the expected data types.
    try:
        payload = GitHubPushPayload.model_validate(raw_payload)

    except ValidationError as exc:
        logger.warning("Invalid GitHub push payload: %s", exc)

        raise HTTPException(
            status_code=400,
            detail="Webhook payload is missing required or valid push information.",
        ) from exc

    repository_name = payload.repository.full_name
    branch_ref = payload.ref
    commit_sha = payload.after

    # ---------------------------------------------------------
    # 6. Ignore tag pushes.
    # ---------------------------------------------------------
    # Checkmate reviews branch updates, not tag creation events.
    if not branch_ref.startswith("refs/heads/"):
        return WebhookVerification(
            event_name=event_name,
            delivery_id=delivery_id,
            repository=repository_name,
            ref=branch_ref,
            ignored_reason="not_a_branch_push",
        )

    # Remove the Git reference prefix to get the actual branch name.
    # Example: refs/heads/main becomes main.
    branch = branch_ref.removeprefix("refs/heads/")

    # ---------------------------------------------------------
    # 7. Verify that the branch is allowed.
    # ---------------------------------------------------------
    # ALLOWED_BRANCHES is loaded from application configuration.
    # A valid push to an unconfigured branch is ignored, not rejected.
    if branch not in ALLOWED_BRANCHES:
        return WebhookVerification(
            event_name=event_name,
            delivery_id=delivery_id,
            repository=repository_name,
            ref=branch_ref,
            branch=branch,
            ignored_reason="branch_not_configured",
            allowed_branches=sorted(ALLOWED_BRANCHES),
        )

    # ---------------------------------------------------------
    # 8. Handle branch deletion events.
    # ---------------------------------------------------------
    # GitHub uses forty zeroes in the "after" field when a branch
    # is deleted. There is no commit to retrieve or review.
    if len(commit_sha) == 40 and set(commit_sha) == {"0"}:
        return WebhookVerification(
            event_name=event_name,
            delivery_id=delivery_id,
            repository=repository_name,
            ref=branch_ref,
            branch=branch,
            ignored_reason="branch_deleted",
        )

    # ---------------------------------------------------------
    # 9. Validate the commit SHA.
    # ---------------------------------------------------------
    # A standard Git commit SHA is exactly forty hexadecimal characters.
    if len(commit_sha) != 40 or any(
        character not in "0123456789abcdefABCDEF"
        for character in commit_sha
    ):
        raise HTTPException(
            status_code=400,
            detail="The after field must contain a valid 40-character SHA.",
        )

    # Return validated information to the route.
    # The route does not need to repeat any of these checks.
    return WebhookVerification(
        event_name=event_name,
        delivery_id=delivery_id,
        repository=repository_name,
        ref=branch_ref,
        branch=branch,
        commit_sha=commit_sha,
    )