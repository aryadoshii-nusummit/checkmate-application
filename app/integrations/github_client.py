"""GitHub REST API client for fetching committed code."""

import base64
from urllib.parse import quote

import httpx

from app.config import GITHUB_API_URL, GITHUB_TOKEN


class GitHubAPIError(Exception):
    """Raised when a GitHub API operation fails."""


class GitHubClient:
    def __init__(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Checkmate-Code-Review",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_URL,
            headers=headers,
            timeout=30.0,
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.client.aclose()

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        try:
            response = await self.client.get(path, params=params)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise GitHubAPIError("GitHub returned an unexpected JSON response.")
            return data
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"GitHub API request failed: {exc}") from exc
        except ValueError as exc:
            raise GitHubAPIError("GitHub returned invalid JSON.") from exc

    async def fetch_commit(self, repository: str, commit_sha: str) -> dict:
        """Fetch a commit's metadata and changed-file contents.

        `commit_sha` should be a commit SHA. A branch ref can be used for the
        standalone smoke test, but webhook-driven reviews pass the exact SHA.
        """
        parts = repository.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("Repository must have the format owner/repository.")
        if not isinstance(commit_sha, str) or not commit_sha.strip():
            raise ValueError("A commit SHA or ref is required.")

        owner, repo = parts
        commit_path = f"/repos/{owner}/{repo}/commits/{quote(commit_sha, safe='')}"
        commit = await self._get_json(commit_path)
        resolved_sha = commit.get("sha")
        if not isinstance(resolved_sha, str) or not resolved_sha:
            raise GitHubAPIError("GitHub commit response did not contain a SHA.")

        files: list[dict] = []
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
                content_path = f"/repos/{owner}/{repo}/contents/{encoded_path}"
                try:
                    content_data = await self._get_json(
                        content_path,
                        params={"ref": resolved_sha},
                    )
                    if (
                        content_data.get("type") == "file"
                        and content_data.get("encoding") == "base64"
                    ):
                        raw_content = base64.b64decode(content_data["content"])
                        result["content"] = raw_content.decode(
                            "utf-8", errors="replace"
                        )
                except GitHubAPIError:
                    # GitHub's Contents API can omit/decline large files or
                    # special file types. Preserve the patch and report that
                    # content is unavailable instead of losing the whole commit.
                    result["content"] = None

            files.append(result)

        return {
            "repository": repository,
            "commit": resolved_sha,
            "message": commit.get("commit", {}).get("message", ""),
            "files": files,
        }
