"""GitHub webhook signature verification."""

import hashlib
import hmac


def verify_github_signature(
    body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify X-Hub-Signature-256 against the original raw request body."""
    if not secret or not signature_header:
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
