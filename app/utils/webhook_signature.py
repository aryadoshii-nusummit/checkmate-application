"""Utilities for verifying GitHub webhook request signatures."""

import hashlib
import hmac


def verify_github_signature(
    body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """
    Verify the GitHub webhook signature using HMAC-SHA256.

    GitHub signs webhook request bodies using a shared secret configured
    in the repository's webhook settings. Checkmate uses the same secret
    to calculate the expected signature and compare it with the signature
    received in the X-Hub-Signature-256 request header.

    Args:
        body: Original raw HTTP request body received from GitHub.
        signature_header: Signature supplied in the
            X-Hub-Signature-256 header.
        secret: Shared webhook secret configured in Checkmate.

    Returns:
        bool: True if the signature is valid; otherwise, False.
    """

    # Reject the request if either the shared secret or signature header
    # is missing. Without both values, the request cannot be authenticated.
    if not secret or not signature_header:
        return False

    # Calculate the expected HMAC-SHA256 signature using the shared secret.
    # The secret is encoded as UTF-8, while the original request body is
    # passed as bytes to ensure the signature matches GitHub's calculation.
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    # Compare the expected signature with GitHub's supplied signature.
    # compare_digest performs a timing-safe comparison, reducing the risk
    # of timing attacks compared with ordinary string equality.
    return hmac.compare_digest(expected, signature_header)
