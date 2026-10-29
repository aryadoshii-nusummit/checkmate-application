"""Unit tests for GitHub webhook signature verification."""

import hashlib
import hmac
import unittest

from app.security.webhook_signature import verify_github_signature


class WebhookSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "test-secret"
        self.body = b'{"ref":"refs/heads/main"}'
        digest = hmac.new(
            self.secret.encode(), self.body, hashlib.sha256
        ).hexdigest()
        self.signature = f"sha256={digest}"

    def test_valid_signature_is_accepted(self) -> None:
        self.assertTrue(
            verify_github_signature(self.body, self.signature, self.secret)
        )

    def test_wrong_signature_is_rejected(self) -> None:
        self.assertFalse(
            verify_github_signature(self.body, "sha256=wrong", self.secret)
        )

    def test_missing_signature_is_rejected(self) -> None:
        self.assertFalse(verify_github_signature(self.body, None, self.secret))

    def test_missing_secret_is_rejected(self) -> None:
        self.assertFalse(verify_github_signature(self.body, self.signature, ""))

    def test_body_change_invalidates_signature(self) -> None:
        self.assertFalse(
            verify_github_signature(self.body + b" ", self.signature, self.secret)
        )


if __name__ == "__main__":
    unittest.main()
