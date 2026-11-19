"""Constants used by the Checkmate code review process."""

# List the file extensions that Checkmate can send for AI code review.
# Keeping this list in one place makes it easier to support additional
# programming languages and configuration formats in the future.
#
# Extensions are stored in lowercase because review_service.py normalizes
# file extensions before checking them against this set.
REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".kt", ".go", ".rs", ".rb",
    ".php", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml",
    ".sql", ".sh", ".ps1",
}
