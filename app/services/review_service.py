"""Coordinate AI code reviews for changed files in a GitHub commit."""

import logging
import os
from typing import Any

from app.config.settings import LINE_LIMIT
from app.constants.review import REVIEWABLE_EXTENSIONS
from app.services.ollama_service import OllamaClient


# Create a module-level logger to record errors during AI code reviews.
logger = logging.getLogger(__name__)


async def review_commit_files(
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Review eligible files from a GitHub commit using Ollama.

    Files are checked for supported extensions, available text content,
    binary data, and the configured line limit before being reviewed.

    Args:
        files: Changed-file information returned by the GitHub service.

    Returns:
        dict[str, Any]: Review reports, reviewed-file count,
        skipped-file count, and details of skipped files.
    """

    # Initialize the Ollama client used to generate code review reports.
    client = OllamaClient()

    # Keep successful reviews and skipped-file details separately
    # so the final response clearly explains what was processed.
    reviews = []
    skipped_files = []

    # Read the maximum allowed file length from central configuration.
    # Files exceeding this limit are skipped to control model input size.
    line_limit = LINE_LIMIT

    # Process each changed file retrieved from the GitHub commit.
    for file in files:
        path = file.get("path", "")
        content = file.get("content")

        # Extract the file extension and normalize it to lowercase.
        # This ensures that extensions such as .PY and .py are treated equally.
        extension = os.path.splitext(path)[1].lower()

        # Skip files whose extensions are not supported by the review process.
        # The supported extensions are maintained centrally in constants/review.py.
        if extension not in REVIEWABLE_EXTENSIONS:
            skipped_files.append({
                "path": path,
                "reason": "unsupported_file_type",
            })
            continue

        # Skip files when GitHub did not provide readable source content.
        # Empty files are also excluded because there is no useful code to review.
        if not isinstance(content, str) or not content.strip():
            skipped_files.append({
                "path": path,
                "reason": "content_unavailable",
            })
            continue

        # Check for null bytes, which commonly indicate binary file content.
        # Binary data should not be passed to a language model as source code.
        if "\x00" in content:
            skipped_files.append({
                "path": path,
                "reason": "binary_file",
            })
            continue

        # Count the file's lines before sending it to Ollama.
        # This protects the review workflow from processing files
        # larger than the configured limit.
        lines = content.splitlines()

        if len(lines) > line_limit:
            skipped_files.append({
                "path": path,
                "reason": "file_exceeds_line_limit",
                "line_count": len(lines),
                "line_limit": line_limit,
            })
            continue

        # Send the eligible file to Ollama for AI-powered code review.
        # The file path provides context, while the content contains
        # the source code that needs to be analyzed.
        try:
            report = await client.review_code(
                file_path=path,
                code=content,
            )

        # Log the failing file and preserve the exception.
        # Re-raising allows the webhook layer to return an appropriate
        # error response instead of silently treating a failed review as skipped.
        except Exception:
            logger.exception("AI review failed for file %s", path)
            raise

        # Store the generated report together with the file path and
        # GitHub change status for identification in the final response.
        reviews.append({
            "path": path,
            "status": file.get("status", "modified"),
            "review": report,
        })

    # Return a structured result so the webhook endpoint can report
    # successful reviews and skipped files separately.
    return {
        "reviewed_file_count": len(reviews),
        "skipped_file_count": len(skipped_files),
        "reviews": reviews,
        "skipped_files": skipped_files,
    }
