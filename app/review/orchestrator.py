
"""Coordinate AI reviews for changed files in a GitHub commit."""

import logging
import os
from typing import Any

from app.review.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# Avoid sending binary files and generated dependency files to the model.
REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".kt", ".go", ".rs", ".rb",
    ".php", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml",
    ".sql", ".sh", ".ps1",
}


async def review_commit_files(
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Review eligible changed files and collect their reports."""

    client = OllamaClient()
    reviews = []
    skipped_files = []

    line_limit = int(os.getenv("CHECKMATE_LINE_LIMIT", "120"))

    for file in files:
        path = file.get("path", "")
        content = file.get("content")

        extension = os.path.splitext(path)[1].lower()

        if extension not in REVIEWABLE_EXTENSIONS:
            skipped_files.append({
                "path": path,
                "reason": "unsupported_file_type",
            })
            continue

        if not isinstance(content, str) or not content.strip():
            skipped_files.append({
                "path": path,
                "reason": "content_unavailable",
            })
            continue

        if "\x00" in content:
            skipped_files.append({
                "path": path,
                "reason": "binary_file",
            })
            continue

        lines = content.splitlines()

        if len(lines) > line_limit:
            skipped_files.append({
                "path": path,
                "reason": "file_exceeds_line_limit",
                "line_count": len(lines),
                "line_limit": line_limit,
            })
            continue

        try:
            report = await client.review_code(
                file_path=path,
                code=content,
            )
        except Exception:
            logger.exception("AI review failed for file %s", path)
            raise

        reviews.append({
            "path": path,
            "status": file.get("status", "modified"),
            "review": report,
        })

    return {
        "reviewed_file_count": len(reviews),
        "skipped_file_count": len(skipped_files),
        "reviews": reviews,
        "skipped_files": skipped_files,
    }
