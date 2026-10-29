"""Test webhook signature and branch filtering without calling GitHub.

The test branch is deliberately excluded from the usual allowed-branch list,
so FastAPI should return status=ignored and reason=branch_not_configured.
"""

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
import uuid

from dotenv import load_dotenv

load_dotenv()
secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
if not secret:
    raise SystemExit("GITHUB_WEBHOOK_SECRET is missing. Create your .env first.")

payload = {
    "ref": "refs/heads/__checkmate_unconfigured_test_branch__",
    "before": "a" * 40,
    "after": "b" * 40,
    "repository": {"full_name": "example/checkmate-demo"},
}
body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
signature = "sha256=" + hmac.new(
    secret.encode("utf-8"), body, hashlib.sha256
).hexdigest()
request = urllib.request.Request(
    "http://127.0.0.1:8000/webhooks/github",
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": str(uuid.uuid4()),
        "X-Hub-Signature-256": signature,
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print("HTTP status:", response.status)
        print(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    print("HTTP status:", exc.code)
    print(exc.read().decode("utf-8"))
    raise SystemExit(1)
except urllib.error.URLError as exc:
    raise SystemExit(f"Could not connect to Checkmate: {exc}")
