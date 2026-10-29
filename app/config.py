"""Central application configuration loaded from environment / .env."""

import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("CHECKMATE_APP_NAME", "Checkmate Code Review System")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

ALLOWED_BRANCHES = {
    branch.strip()
    for branch in os.getenv("CHECKMATE_ALLOWED_BRANCHES", "main,develop").split(",")
    if branch.strip()
}

REVIEW_SCOPE = os.getenv("CHECKMATE_REVIEW_SCOPE", "changed").strip().lower()
REVIEW_TYPE = os.getenv("CHECKMATE_REVIEW_TYPE", "detail").strip().lower()
LINE_LIMIT = int(os.getenv("CHECKMATE_LINE_LIMIT", "120"))

if REVIEW_SCOPE not in {"changed", "full_file"}:
    raise ValueError("CHECKMATE_REVIEW_SCOPE must be 'changed' or 'full_file'.")
if REVIEW_TYPE not in {"high_level", "detail"}:
    raise ValueError("CHECKMATE_REVIEW_TYPE must be 'high_level' or 'detail'.")
if LINE_LIMIT < 1:
    raise ValueError("CHECKMATE_LINE_LIMIT must be greater than zero.")
if OLLAMA_TIMEOUT_SECONDS <= 0:
    raise ValueError("OLLAMA_TIMEOUT_SECONDS must be greater than zero.")
