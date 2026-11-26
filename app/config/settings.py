"""Central application configuration loaded from environment variables and .env."""

import os

from dotenv import load_dotenv


# Load environment variables from the project's .env file.
# This allows developers to configure the application locally without
# hardcoding credentials, service URLs, or environment-specific values.
load_dotenv()


# ---------------------------------------------------------------------
# General application configuration
# ---------------------------------------------------------------------

# Define the application name displayed in FastAPI documentation.
# A default value is used when CHECKMATE_APP_NAME is not configured.
APP_NAME = os.getenv(
    "CHECKMATE_APP_NAME",
    "Checkmate Code Review System",
)


# ---------------------------------------------------------------------
# GitHub integration configuration
# ---------------------------------------------------------------------

# Shared secret used to verify the authenticity of incoming GitHub webhooks.
# This value must match the secret configured in the GitHub repository webhook.
GITHUB_WEBHOOK_SECRET = os.getenv(
    "GITHUB_WEBHOOK_SECRET",
    "",
).strip()

# Base URL of the GitHub REST API.
# Removing a trailing slash prevents duplicate slashes when building API URLs.
GITHUB_API_URL = os.getenv(
    "GITHUB_API_URL",
    "https://api.github.com",
).rstrip("/")

# Personal access token used to authenticate requests to the GitHub API.
# The token is stripped of surrounding whitespace before use.
GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
).strip()


# ---------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------

# Base URL of the local Ollama server that generates AI code reviews.
# The default address assumes Ollama is running on the same machine.
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

# Name of the language model used to analyze source code.
# This default model is used when OLLAMA_MODEL is not specified in .env.
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5-coder:3b",
).strip()

# Maximum number of seconds to wait for Ollama to complete a review.
# AI-generated responses may take longer than ordinary API requests.
OLLAMA_TIMEOUT_SECONDS = float(
    os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")
)


# ---------------------------------------------------------------------
# Code review configuration
# ---------------------------------------------------------------------

# Define which repository branches are eligible for automated reviews.
# Multiple branch names can be supplied as a comma-separated .env value.
# The set removes duplicate entries and makes branch membership checks efficient.
ALLOWED_BRANCHES = {
    branch.strip()
    for branch in os.getenv(
        "CHECKMATE_ALLOWED_BRANCHES",
        "main,develop",
    ).split(",")
    if branch.strip()
}

# Determine which portion of a file should be reviewed.
# "changed" focuses on modified code, while "full_file" requests
# analysis of the complete file.
REVIEW_SCOPE = os.getenv(
    "CHECKMATE_REVIEW_SCOPE",
    "changed",
).strip().lower()

# Select the level of detail expected in the generated review.
# "high_level" provides a broader overview, while "detail" requests
# more specific findings and explanations.
REVIEW_TYPE = os.getenv(
    "CHECKMATE_REVIEW_TYPE",
    "detail",
).strip().lower()

# Maximum number of lines allowed in a file before it is skipped.
# This helps control the amount of source code sent to the language model.
LINE_LIMIT = int(
    os.getenv("CHECKMATE_LINE_LIMIT", "120")
)


# ---------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------

# Ensure the configured review scope is one of the supported options.
# Invalid values stop application startup rather than allowing unexpected behavior.
if REVIEW_SCOPE not in {"changed", "full_file"}:
    raise ValueError(
        "CHECKMATE_REVIEW_SCOPE must be 'changed' or 'full_file'."
    )

# Ensure the configured review type is supported by the application.
if REVIEW_TYPE not in {"high_level", "detail"}:
    raise ValueError(
        "CHECKMATE_REVIEW_TYPE must be 'high_level' or 'detail'."
    )

# A line limit below one would make the file filtering configuration unusable.
if LINE_LIMIT < 1:
    raise ValueError(
        "CHECKMATE_LINE_LIMIT must be greater than zero."
    )

# A zero or negative timeout would prevent Ollama requests from
# having a meaningful amount of time to complete.
if OLLAMA_TIMEOUT_SECONDS <= 0:
    raise ValueError(
        "OLLAMA_TIMEOUT_SECONDS must be greater than zero."
    )
