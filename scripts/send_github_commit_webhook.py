"""Send a signed local push event for a real GitHub commit."""

# Used to calculate the SHA-256 hash and webhook signature.
import hashlib
import hmac

# Used to convert Python dictionaries to JSON and parse JSON responses.
import json

# Used to read environment variables, including settings from .env.
import os

# Used to exit the script with an error message or exit code.
import sys

# Used to handle HTTP errors and connection errors.
import urllib.error
import urllib.request

# Generates a unique ID for each simulated webhook delivery.
import uuid

# Loads environment variables from the project's .env file.
from dotenv import load_dotenv

load_dotenv()

# Read the webhook secret used by Checkmate to verify the signature.
secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()

# Read the GitHub repository to test, in owner/repository format.
repository = os.getenv("CHECKMATE_TEST_REPOSITORY", "").strip()

# Read the branch name; use "main" if it is not configured.
branch = os.getenv("CHECKMATE_TEST_BRANCH", "main").strip()

# Read the exact commit SHA that Checkmate should review.
commit_sha = os.getenv("CHECKMATE_TEST_COMMIT", "").strip()

# Stop early if any required configuration value is missing.
if not all([secret, repository, branch, commit_sha]):
    raise SystemExit(
        "Configure these settings in .env:\n"
        "GITHUB_WEBHOOK_SECRET\n"
        "CHECKMATE_TEST_REPOSITORY\n"
        "CHECKMATE_TEST_BRANCH\n"
        "CHECKMATE_TEST_COMMIT"
    )

# A full Git commit SHA contains 40 hexadecimal characters.
# Reject invalid values before sending the webhook.
if len(commit_sha) != 40 or any(
    character not in "0123456789abcdefABCDEF"
    for character in commit_sha
):
    raise SystemExit(
        "CHECKMATE_TEST_COMMIT must be the full 40-character commit SHA."
    )

# Ensure the repository has an owner and repository name.
if "/" not in repository:
    raise SystemExit(
        "CHECKMATE_TEST_REPOSITORY must use owner/repository format."
    )

# Build a simplified GitHub push-event payload.
# "ref" identifies the branch, and "after" identifies the target commit.
# "before" is a placeholder SHA for this simulated event.
# The repository object contains the full repository name.
payload = {
    "ref": f"refs/heads/{branch}",
    "before": "a" * 40,
    "after": commit_sha,
    "repository": {"full_name": repository},
}

# Convert the payload to compact JSON, then encode it as UTF-8 bytes.
# These exact bytes are used both for signing and for the HTTP request.
body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

# Create a GitHub-compatible HMAC-SHA256 signature.
# The webhook secret is the key, and the raw JSON body is the message.
# The "sha256=" prefix is the format expected in the signature header.
signature = "sha256=" + hmac.new(
    secret.encode("utf-8"),
    body,
    hashlib.sha256,
).hexdigest()

# Generate a unique delivery ID for this simulated webhook request.
delivery_id = str(uuid.uuid4())

# Prepare an HTTP POST request to the locally running FastAPI server.
request = urllib.request.Request(
    "http://127.0.0.1:8000/webhooks/github",
    data=body,  # Send the signed JSON payload as the request body.
    headers={
        "Content-Type": "application/json",  # The body is JSON.
        "X-GitHub-Event": "push",  # Tell Checkmate this is a push event.
        "X-GitHub-Delivery": delivery_id,  # Identify this delivery.
        "X-Hub-Signature-256": signature,  # Allow signature verification.
    },
    method="POST",
)

# Display the details of the simulated event before sending it.
print("Sending simulated GitHub push event...")
print(f"Repository: {repository}")
print(f"Branch:     {branch}")
print(f"Commit:     {commit_sha}")
print(f"Delivery:   {delivery_id}")
print()

try:
    # Send the request to FastAPI.
    # Allow up to 300 seconds for the full review response.
    with urllib.request.urlopen(request, timeout=300) as response:
        # Read the response bytes and convert them to a string.
        response_body = response.read().decode("utf-8")

        # Display the HTTP status code returned by FastAPI.
        print("HTTP status:", response.status)

except urllib.error.HTTPError as exc:
    # HTTPError means the server returned an HTTP error status,
    # such as 400, 401, 403, 500, or 502.
    # Read the server's response body to display its error details.
    response_body = exc.read().decode("utf-8")
    print("HTTP status:", exc.code)
    print(response_body)

    # Exit with a failure code instead of parsing the error as a review.
    sys.exit(1)

except urllib.error.URLError as exc:
    # URLError usually means the script could not reach the local server
    # or encountered another URL/network-level problem.
    raise SystemExit(
        f"Could not reach FastAPI at localhost:8000: {exc}"
    )


try:
    # Parse FastAPI's JSON response into a Python dictionary.
    result = json.loads(response_body)

    # Print a formatted heading for the review report.
    print("\n" + "=" * 72)
    print("                  CHECKMATE CODE REVIEW RESULTS")
    print("=" * 72)

    # Display general commit and review status information.
    # .get() supplies a fallback if a field is missing.
    print(f"Status:       {result.get('status', 'unknown')}")
    print(f"Repository:   {result.get('repository', 'unknown')}")
    print(f"Branch:       {result.get('branch', 'unknown')}")
    print(f"Commit:       {result.get('commit', 'unknown')}")
    print(f"Commit title: {result.get('commit_message', 'unknown')}")

    # Print counts summarizing how Checkmate handled changed files.
    print("\n" + "-" * 72)
    print("REVIEW SUMMARY")
    print("-" * 72)
    print(f"Files changed:  {result.get('changed_file_count', 0)}")
    print(f"Files reviewed: {result.get('reviewed_file_count', 0)}")
    print(f"Files skipped:  {result.get('skipped_file_count', 0)}")

    # Retrieve the list of changed files from the response.
    # Use an empty list if the field is missing.
    files = result.get("files", [])

    if files:
        # Display details for each changed file.
        print("\n" + "-" * 72)
        print("CHANGED FILES")
        print("-" * 72)

        for file_info in files:
            # Show the file path and its change status.
            print(f"  {file_info.get('path', 'Unknown file')}")
            print(f"    Status: {file_info.get('status', 'unknown')}")

            # Show additions and deletions reported for the file.
            print(
                f"    Changes: +{file_info.get('additions', 0)} "
                f"/ -{file_info.get('deletions', 0)}"
            )

    # Retrieve the AI review results from the response.
    reviews = result.get("reviews", [])

    # Print each file's AI-generated review separately.
    for item in reviews:
        print("\n" + "=" * 72)
        print(f"AI REVIEW: {item.get('path', 'Unknown file')}")
        print("=" * 72)

        # Remove extra whitespace around the review text.
        review = item.get("review", "")
        print(review.strip() if review else "No review text returned.")

    # Retrieve files that Checkmate chose not to review.
    skipped = result.get("skipped_files", [])

    if skipped:
        print("\n" + "-" * 72)
        print("SKIPPED FILES")
        print("-" * 72)

        for item in skipped:
            # Dictionary entries may contain a path and skip reason.
            if isinstance(item, dict):
                print(
                    f"  {item.get('path', 'Unknown file')}: "
                    f"{item.get('reason', 'No reason provided')}"
                )
            else:
                # Also support skipped entries represented as plain text.
                print(f"  {item}")

    # Print a closing line after all results have been displayed.
    print("\n" + "=" * 72)
    print("                 END OF CHECKMATE REVIEW")
    print("=" * 72)

except json.JSONDecodeError:
    # If the server response is not valid JSON, print it as plain text.
    print(response_body)
