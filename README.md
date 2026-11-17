# ♟️ Checkmate — AI-Powered Code Review

**Automated code reviews powered by GitHub, FastAPI, and local AI.**

Checkmate is an automated code-review system that receives GitHub push events, retrieves changed files, and uses a locally hosted Ollama model to analyze code.

It identifies potential issues, highlights strengths, evaluates code quality, and provides actionable recommendations. Review results are stored in a SQLite database for persistence.

## Features

- **GitHub Integration:** Receives push webhooks and retrieves commit details and changed files.
- **Webhook Security:** Validates HMAC-SHA256 signatures and configured branch restrictions.
- **AI Code Review:** Uses Ollama with Qwen 2.5 Coder 3B for local code analysis.
- **Structured Feedback:** Provides summaries, quality assessments, strengths, findings, and recommendations.
- **File Handling:** Selects supported source files and skips files that cannot be reviewed.
- **Database Persistence:** Stores review history and file-level results using SQLite and SQLAlchemy.
- **Duplicate Detection:** Prevents repeated processing of previously handled webhook deliveries.
- **Automated Tests:** Covers webhook verification, service processing, and database persistence.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Application language |
| FastAPI | API and webhook handling |
| Pydantic | Data validation and models |
| SQLAlchemy | Database ORM |
| SQLite | Review history storage |
| GitHub REST API | Commit and file retrieval |
| HTTPX | HTTP communication |
| Ollama | Local AI runtime |
| Qwen 2.5 Coder 3B | Code-review model |
| Pytest | Automated testing |

## Project Structure

```text
checkmate_application/
│
├── app/
│   ├── api/             # API endpoints
│   ├── config/          # Application settings
│   ├── constants/       # Review constants
│   ├── database/        # SQLAlchemy models and sessions
│   ├── dependencies/    # FastAPI dependencies
│   ├── models/          # Pydantic models
│   ├── repositories/    # Database operations
│   ├── services/        # GitHub, AI and review services
│   ├── utils/           # Reusable utilities
│   └── main.py          # FastAPI application
│
├── scripts/             # Local testing scripts
├── tests/               # Automated tests
│
├── .env.example
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.14 or a compatible supported version
- Git
- Ollama installed and running
- GitHub repository access

Pull the configured AI model:

```powershell
ollama pull qwen2.5-coder:3b
```

## Setup

Clone the repository and switch to the development branch:

```powershell
git clone https://github.com/aryadoshii-nusummit/checkmate-application.git

cd checkmate-application

git checkout refactor/dependency-injection-and-api-models
```

Create and activate a virtual environment:

```powershell
py -m venv .venv

.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip

pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Configure the required values in `.env`, including:

- `GITHUB_WEBHOOK_SECRET`
- `CHECKMATE_ALLOWED_BRANCHES`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`

Use `.env.example` as the reference for the complete configuration. Never commit secrets or credentials.

## Run the Application

Make sure Ollama is running, then start FastAPI:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Available endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/webhooks/github` | GitHub webhook receiver |

Interactive API documentation:

http://127.0.0.1:8000/docs

## Testing

Run the automated test suite:

```powershell
python -m pytest tests/ -v
```

**Latest verified result: 18 tests passed.**

To test the complete local webhook workflow, keep the application running and execute:

```powershell
python scripts/send_github_commit_webhook.py
```

## Database

Checkmate uses SQLite with SQLAlchemy ORM.

The database is automatically initialized when the application starts and is stored locally as:

```text
checkmate.db
```

It contains two primary tables:

- `review_runs` — stores commit and review-run information.
- `file_reviews` — stores individual file reviews and structured AI feedback.

The database can be inspected using [DB Browser for SQLite](https://sqlitebrowser.org/).

## Current Status

The development branch includes:

- GitHub webhook integration and verification.
- Dependency-injected application services.
- Structured AI code reviews using local Ollama.
- SQLite persistence for review history.
- Duplicate webhook detection.
- Automated tests covering core workflows.

**Branch:** `refactor/dependency-injection-and-api-models`

**Latest commit:** `c774a16` — `feat: add database persistence for code reviews`

## Future Improvements

- Review history retrieval APIs.
- Improved AI review accuracy and recommendation quality.
- Database migrations using Alembic.
- Enhanced logging and production-readiness improvements.

---

*Checkmate aims to make code reviews more consistent and actionable—helping developers identify problems, recognize good practices, and continuously improve code quality.*