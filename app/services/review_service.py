"""Coordinate structured AI code reviews for changed GitHub files."""

import logging
import os

from app.config.settings import LINE_LIMIT
from app.constants.review import REVIEWABLE_EXTENSIONS
from app.models.github import (
    GitHubChangedFile,
    ReviewFileResult,
    ReviewServiceResult,
    SkippedFileResult,
)
from app.models.review import ReviewResult
from app.services.ollama_service import OllamaClient

logger = logging.getLogger(__name__)


def _format_review_report(result: ReviewResult) -> str:
    """Convert a validated review result into a readable Markdown report."""

    sections = [
        "## Review Summary",
        result.summary,
        f"**Overall quality:** {result.overall_quality}",
    ]

    if result.strengths:
        sections.extend(["\n## Strengths"])
        sections.extend(f"- {item}" for item in result.strengths)

    if result.areas_to_improve:
        sections.extend(["\n## Areas to Improve"])
        sections.extend(f"- {item}" for item in result.areas_to_improve)

    sections.append("\n## Findings")

    if not result.findings:
        sections.append("No significant issues identified in the supplied code.")
    else:
        for finding in result.findings:
            lines = ", ".join(str(number) for number in finding.line_numbers)

            sections.extend([
                f"\n### {finding.title}",
                (
                    f"**Severity:** {finding.severity} | "
                    f"**Confidence:** {finding.confidence} | "
                    f"**Category:** {finding.category}"
                ),
                f"**Lines:** {lines}",
                f"**Evidence:** {finding.evidence}",
                f"**Problem:** {finding.problem}",
                f"**Impact:** {finding.impact}",
                f"**Recommendation:** {finding.recommendation}",
            ])

    if result.additional_suggestions:
        sections.append("\n## Additional Suggestions")
        sections.extend(
            f"- {suggestion}"
            for suggestion in result.additional_suggestions
        )

    return "\n\n".join(sections)


def _count_findings(result: ReviewResult) -> dict[str, int]:
    """Calculate consistent issue, warning, and suggestion totals."""

    issues = sum(
        finding.severity in {"CRITICAL", "HIGH", "MEDIUM"}
        for finding in result.findings
    )
    warnings = sum(
        finding.severity == "LOW"
        for finding in result.findings
    )
    suggestions = (
        sum(finding.severity == "INFO" for finding in result.findings)
        + len(result.additional_suggestions)
    )

    return {
        "issues_count": issues,
        "warnings_count": warnings,
        "suggestions_count": suggestions,
    }


class ReviewService:
    """Coordinate code reviews using an injected Ollama client."""

    def __init__(self, ollama_client: OllamaClient) -> None:
        """Initialize the review service with its AI client."""
        self.ollama_client = ollama_client

    async def review_commit_files(
        self,
        files: list[GitHubChangedFile],
    ) -> ReviewServiceResult:
        """
        Review eligible files from a GitHub commit using Ollama.

        Each eligible file receives a validated structured review. Files that
        cannot be reviewed are reported explicitly rather than silently ignored.
        """

        client = self.ollama_client
        reviews: list[ReviewFileResult] = []
        skipped_files: list[SkippedFileResult] = []

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

            if len(lines) > LINE_LIMIT:
                skipped_files.append({
                    "path": path,
                    "reason": "file_exceeds_line_limit",
                    "line_count": len(lines),
                    "line_limit": LINE_LIMIT,
                })
                continue

            try:
                result = await client.review_code(
                    file_path=path,
                    code=content,
                )
            except Exception:
                logger.exception("AI review failed for file %s", path)
                raise

            counts = _count_findings(result)

            reviews.append({
                "path": path,
                "status": file.get("status", "modified"),
                "review": _format_review_report(result),
                "quality": result.overall_quality,
                "summary": result.summary,
                "strengths": result.strengths,
                "areas_to_improve": result.areas_to_improve,
                "findings": [
                    finding.model_dump(mode="json")
                    for finding in result.findings
                ],
                "additional_suggestions": result.additional_suggestions,
                **counts,
            })

        logger.info(
            "Commit review processing finished: reviewed=%d skipped=%d",
            len(reviews),
            len(skipped_files),
        )

        return {
            "reviewed_file_count": len(reviews),
            "skipped_file_count": len(skipped_files),
            "reviews": reviews,
            "skipped_files": skipped_files,
        }
