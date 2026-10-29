# Checkmate project handoff

Use this file when continuing work in another terminal or chat.

## Environment
- The code has been tested on macOS with Python 3.14 and a virtual environment.
- The target next environment is the user's office Windows laptop with Ollama installed.
- Use PowerShell commands from README.md on Windows.

## Current progress
1. FastAPI app starts with `uvicorn app.main:app --reload --port 8000`.
2. `GET /health` returns `{"status":"ok","service":"checkmate"}`.
3. `POST /webhooks/github` verifies GitHub HMAC-SHA256 signatures.
4. Non-push events, tag pushes, deleted branches, and disallowed branches are ignored.
5. Allowed branch pushes call `GitHubClient.fetch_commit()` using the webhook's exact `after` commit SHA.
6. GitHub client retrieves commit metadata, changed-file patches where available, and file contents where available.
7. Local test succeeded against `octocat/Hello-World`, commit `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`, finding one modified README file.
8. Five webhook signature unit tests passed in the earlier starter.

## Not implemented yet
- Ollama API client
- Prompt files and review prompt management
- Review orchestrator
- Chunking and cross-chunk analysis
- Deterministic line-length and syntax/build validators
- Finding aggregation and final PASS/FAIL report
- GitHub status/comment reporting

## Next task
1. Run the project on the Windows laptop using README.md.
2. Confirm health check and unit tests.
3. Run the GitHub client test and `send_github_commit_webhook` test.
4. Build `app/review/ollama_client.py` and prompt templates; verify the configured local Ollama model responds before wiring it into the webhook.

## Current design decisions
- Single Python/FastAPI application; no database.
- Only configured branches trigger reviews.
- Review must use the exact commit SHA from the webhook.
- Changed-code review is the configured default; full-file mode is planned.
- AI findings will be combined with deterministic checks.
- A processing failure or incomplete review must never be reported as a normal PASS.
