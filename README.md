# Checkmate — AI-Powered Code Review

Checkmate is a Python/FastAPI application that receives GitHub push events, retrieves the associated commit and changed files, and uses a locally hosted Ollama model to generate code-review feedback.

The current development setup uses **Qwen 2.5 Coder 3B** through Ollama. The application is organized as a modular monolith: API endpoints, application services, configuration, constants, and reusable utilities live in separate packages within one FastAPI application.

> **Implementation note:** This README describes the current GitHub + FastAPI + Ollama development workflow. Features described as future work are not represented as completed functionality.

## What Checkmate currently does

- Exposes a FastAPI health endpoint (`GET /health`).
- Receives GitHub push-style webhook requests at `POST /webhooks/github`.
- Verifies webhook authenticity using an HMAC-SHA256 signature and the configured webhook secret.
- Filters events by configured branch names.
- Retrieves commit information and changed-file data through the GitHub REST API.
- Selects supported source files for review using centralized file-extension configuration.
- Sends code to a locally running Ollama model and collects AI-generated review feedback.
- Returns the processing/review response from the webhook endpoint.

The application does not currently require a database. The `database/` and `middleware/` packages are structural placeholders for future development.

## Technology stack

| Technology | Role |
|---|---|
| Python | Application language |
| FastAPI | HTTP API and webhook receiver |
| Uvicorn | Local ASGI server |
| GitHub REST API | Commit and changed-file retrieval |
| HTTPX | Asynchronous HTTP communication |
| Ollama | Local model runtime |
| Qwen 2.5 Coder 3B | Configured code-review model |
| Pytest | Automated tests |
| python-dotenv | Loads local environment configuration |

## Project structure

```text
checkmate_application/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── github_webhook.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── github_service.py
│   │   ├── review_service.py
│   │   └── ollama_service.py
│   ├── database/
│   │   └── __init__.py
│   ├── constants/
│   │   ├── __init__.py
│   │   └── review.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── webhook_signature.py
│   └── middleware/
│       └── __init__.py
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── PROJECT_STATUS.md
```

### Application modules

| Module | Responsibility |
|---|---|
| `app/main.py` | Creates the FastAPI application and registers its routers. |
| `app/api/health.py` | Implements the health-check endpoint. |
| `app/api/github_webhook.py` | Receives webhook requests, validates/filters events, and delegates review processing. |
| `app/services/github_service.py` | Communicates with the GitHub REST API to retrieve commit and changed-file information. Its HTTPX client follows redirects. |
| `app/services/review_service.py` | Coordinates changed-file processing and the review workflow. |
| `app/services/ollama_service.py` | Sends review requests to the locally hosted Ollama model and handles its response. |
| `app/config/settings.py` | Loads and exposes application settings from environment configuration. |
| `app/constants/review.py` | Centralizes the supported file extensions used to select reviewable files. |
| `app/utils/webhook_signature.py` | Contains reusable GitHub webhook signature-verification logic. |
| `app/database/` | Reserved for future persistence functionality; no database is currently required. |
| `app/middleware/` | Reserved for future cross-cutting HTTP middleware. |

The `__init__.py` files make these directories importable Python packages. They do not necessarily contain runtime logic.

## Request and review flow

```text
Developer pushes a commit to GitHub
                |
                v
        GitHub push webhook
                |
                v
   FastAPI: POST /webhooks/github
                |
                v
     Verify webhook signature
                |
                v
       Check allowed branch
                |
                v
       GitHub service retrieves
       commit and changed files
                |
                v
       Review service selects
       supported files and coordinates review
                |
                v
       Ollama service sends code
       to Qwen 2.5 Coder 3B
                |
                v
       AI-generated review response
                |
                v
       Webhook response
```

The API layer handles HTTP requests and responses. The service layer contains the application operations. The utility layer provides reusable signature verification, while configuration and constants are kept separate from business logic.

## Prerequisites

- Windows with PowerShell (the commands below use PowerShell syntax).
- Python installed.
- Git installed.
- Ollama installed and running locally.
- The configured Ollama model pulled locally.
- GitHub access to the repository and commit being tested.

For the current local model setup:

```powershell
ollama pull qwen2.5-coder:3b
ollama list
```

The local Ollama endpoint is typically `http://localhost:11434`.

## Local setup

Run these commands from the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell prevents virtual-environment activation, allow it for the current terminal session and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Environment configuration

Set the required values in the local `.env` file. Do not commit `.env` or share its secret values.

The configuration used by the current development/test setup includes:

| Variable | Purpose |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | Shared secret used to verify webhook signatures. |
| `CHECKMATE_ALLOWED_BRANCHES` | Comma-separated branch allow-list. |
| `CHECKMATE_TEST_REPOSITORY` | Repository used by the commit-webhook test. |
| `CHECKMATE_TEST_BRANCH` | Branch used by the commit-webhook test. |
| `CHECKMATE_TEST_COMMIT` | Commit SHA used by the commit-webhook test. |
| `OLLAMA_BASE_URL` | Ollama API base URL; local setup uses `http://localhost:11434`. |
| `OLLAMA_MODEL` | Model name; current setup uses `qwen2.5-coder:3b`. |
| `OLLAMA_TIMEOUT_SECONDS` | Intended timeout configuration for Ollama requests. |

Use `.env.example` as the authoritative template for the exact variable names and any additional settings required by the checked-out branch. Generate a strong webhook secret for local use, and configure the same value in the GitHub webhook settings when using real GitHub deliveries.

A GitHub token may be needed for private repositories or API access beyond unauthenticated public access. Use only the minimum required permissions and keep tokens out of source control.

## Run the application

Start Ollama in the background, then start FastAPI from the repository root:

```powershell
uvicorn app.main:app --reload --port 8000
```

Useful local endpoints:

- Health check: `http://127.0.0.1:8000/health`
- Interactive API documentation: `http://127.0.0.1:8000/docs`
- GitHub webhook endpoint: `http://127.0.0.1:8000/webhooks/github`

Keep the server terminal running while executing the test scripts in a second PowerShell terminal.

## Tests and local verification

Run the automated test suite:

```powershell
python -m pytest -q
```

Check that the application imports successfully:

```powershell
python -c "from app.main import app; print('Checkmate application imports successfully')"
```

Run the standalone Ollama smoke test:

```powershell
python -m scripts.test_ollama
```

Send a signed test webhook to check webhook receipt, signature verification, and branch filtering:

```powershell
python -m scripts.send_test_webhook
```

The supplied test branch is intentionally unconfigured, so an `ignored` response with `reason: branch_not_configured` is an expected result for that test.

For a commit-based integration test, keep FastAPI running and configure `CHECKMATE_TEST_REPOSITORY`, `CHECKMATE_TEST_BRANCH`, and `CHECKMATE_TEST_COMMIT` in `.env`. Then run:

```powershell
python -m scripts.send_github_commit_webhook
```

This script sends a signed simulated push event to the local webhook endpoint using the configured test repository and commit. It does not require a public HTTPS tunnel. A successful run should return the review response for the configured commit. Review duration depends on the files and local model performance.

## Refactoring summary

The branch `refactor/manager-project-structure` reorganizes the application into the agreed package layout. The main file moves were:

| Previous path | Current path |
|---|---|
| `app/config.py` | `app/config/settings.py` |
| `app/integrations/github_client.py` | `app/services/github_service.py` |
| `app/review/orchestrator.py` | `app/services/review_service.py` |
| `app/review/ollama_client.py` | `app/services/ollama_service.py` |
| `app/security/webhook_signature.py` | `app/utils/webhook_signature.py` |

Imports were updated to use the new paths, including the signature test import. The refactor also introduced `app/constants/review.py` with the supported file-extension list and added the `database/` and `middleware/` placeholders.

The GitHub HTTP client was configured with `follow_redirects=True` after an API request returned a permanent redirect for the test repository endpoint.

## Current status and limitations

The development workflow has been exercised through application import checks, the health endpoint, the test suite, standalone Ollama testing, webhook signature/branch-filter testing, and a commit-based webhook review. The recorded automated test run completed with **5 passing tests**.

Known considerations:

- Local Ollama response time can vary. A full webhook review previously encountered an HTTPX read timeout, although a subsequent run was reported to return review results. Timeout behavior and long-running review handling should be validated further.
- The `database/` and `middleware/` directories are placeholders, not implemented subsystems.
- The current integration test uses a configured test repository and commit; update those values when testing a different commit.
- AI feedback should be treated as review assistance and checked by a developer.

## Future improvements

Potential next steps, subject to project requirements and manager review:

- Improve timeout handling and processing of long-running reviews.
- Add broader automated tests for GitHub API errors and Ollama failures.
- Improve structured review-result validation and reporting.
- Add persistence if review history or delivery tracking becomes necessary.
- Implement middleware when concrete logging, tracing, or request-handling requirements are defined.
- Extend review capabilities only after confirming the required scope and acceptance criteria.
