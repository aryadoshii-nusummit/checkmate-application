
"""GitHub REST API client for fetching committed code."""

import base64
from urllib.parse import quote

import httpx

from app.config.settings import GITHUB_API_URL, GITHUB_TOKEN


class GitHubAPIError(Exception):
    """Raised when a GitHub API operation fails."""


class GitHubClient:
    def __init__(self) -> None:
        # Set the headers required for GitHub REST API requests.
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Checkmate-Code-Review",
        }

        # Add authentication when a GitHub token is configured.
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        # Create an asynchronous HTTP client.
        # follow_redirects=True handles GitHub repository rename redirects.
        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_URL,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.client.aclose()

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        """Send a GET request and return the JSON response."""
        try:
            response = await self.client.get(path, params=params)
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict):
                raise GitHubAPIError(
                    "GitHub returned an unexpected JSON response."
                )

            return data

        except httpx.HTTPError as exc:
            raise GitHubAPIError(
                f"GitHub API request failed: {exc}"
            ) from exc

        except ValueError as exc:
            raise GitHubAPIError(
                "GitHub returned invalid JSON."
            ) from exc

    async def fetch_commit(self, repository: str, commit_sha: str) -> dict:
        """Fetch a commit's metadata and changed-file contents.

        `commit_sha` should be a commit SHA. A branch ref can be used for the
        standalone smoke test, but webhook-driven reviews pass the exact SHA.
        """
        parts = repository.split("/")

        if len(parts) != 2 or not all(parts):
            raise ValueError(
                "Repository must have the format owner/repository."
            )

        if not isinstance(commit_sha, str) or not commit_sha.strip():
            raise ValueError("A commit SHA or ref is required.")

        owner, repo = parts

        # Fetch commit metadata and information about changed files.
        commit_path = (
            f"/repos/{owner}/{repo}/commits/"
            f"{quote(commit_sha, safe='')}"
        )

        commit = await self._get_json(commit_path)

        resolved_sha = commit.get("sha")

        if not isinstance(resolved_sha, str) or not resolved_sha:
            raise GitHubAPIError(
                "GitHub commit response did not contain a SHA."
            )

        files: list[dict] = []

        # Process each file changed in the commit.
        for item in commit.get("files", []):
            path = item.get("filename")
            status = item.get("status", "unknown")

            if not isinstance(path, str) or not path:
                continue

            result = {
                "path": path,
                "status": status,
                "additions": item.get("additions", 0),
                "deletions": item.get("deletions", 0),
                "changes": item.get("changes", 0),
                "patch": item.get("patch"),
                "content": None,
            }

            # Deleted files have no current content at the target commit.
            if status != "removed":
                encoded_path = quote(path, safe="/")

                content_path = (
                    f"/repos/{owner}/{repo}/contents/{encoded_path}"
                )

                try:
                    # Fetch the file contents at the exact commit SHA.
                    content_data = await self._get_json(
                        content_path,
                        params={"ref": resolved_sha},
                    )

                    # GitHub returns file contents as Base64-encoded data.
                    if (
                        content_data.get("type") == "file"
                        and content_data.get("encoding") == "base64"
                    ):
                        raw_content = base64.b64decode(
                            content_data["content"]
                        )

                        result["content"] = raw_content.decode(
                            "utf-8",
                            errors="replace",
                        )

                except GitHubAPIError:
                    # Large or unsupported files may not be available through
                    # the Contents API. Keep the patch so review can continue.
                    result["content"] = None

            files.append(result)

        # Return the commit information in Checkmate's expected format.
        return {
            "repository": repository,
            "commit": resolved_sha,
            "message": commit.get("commit", {}).get("message", ""),
            "files": files,
        }
