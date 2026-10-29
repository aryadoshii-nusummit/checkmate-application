"""Smoke-test GitHub commit retrieval against a public repository."""

import asyncio
import os

from app.config import GITHUB_API_URL, GITHUB_TOKEN  # load project config/.env
from app.integrations.github_client import GitHubClient


async def main() -> None:
    repository = os.getenv(
        "GITHUB_TEST_REPOSITORY",
        os.getenv("CHECKMATE_TEST_REPOSITORY", "octocat/Hello-World"),
    ).strip()
    commit_or_ref = os.getenv(
        "GITHUB_TEST_COMMIT",
        os.getenv("CHECKMATE_TEST_COMMIT", "master"),
    ).strip()

    print("GitHub API:", GITHUB_API_URL)
    print("Authenticated:", bool(GITHUB_TOKEN))
    print("Repository:", repository)
    print("Commit/ref:", commit_or_ref)

    async with GitHubClient() as github:
        result = await github.fetch_commit(repository, commit_or_ref)

    print("Resolved commit:", result["commit"])
    print("Message:", result["message"])
    print("Changed files:", len(result["files"]))

    for file_info in result["files"]:
        print(
            f"\n{file_info['status']}: {file_info['path']} "
            f"(+{file_info['additions']}/-{file_info['deletions']})"
        )
        if file_info.get("content") is not None:
            print("Source content retrieved successfully.")
        elif file_info["status"] != "removed":
            print("Source content unavailable; patch may still be present.")


if __name__ == "__main__":
    asyncio.run(main())
