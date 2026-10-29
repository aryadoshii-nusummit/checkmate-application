# Checkmate — Local Development Starter (Windows)

Checkmate currently contains:

- FastAPI application and `/health` endpoint
- `POST /webhooks/github` endpoint
- HMAC-SHA256 validation of `X-Hub-Signature-256`
- Push-event, branch, payload, and commit-SHA validation
- GitHub REST API client for commit metadata, changed-file patches, and file contents
- Local webhook test scripts and signature unit tests
- Configuration placeholders for Ollama; the Ollama review client is the **next milestone** and is not connected yet

No database is used.

## 1. Extract and open the project

Extract the ZIP and open the `checkmate_starter` folder in VS Code. Open a PowerShell terminal in that folder.

## 2. Create the Python environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks virtual-environment activation, run this in that terminal and retry activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Configure `.env`

Generate a local webhook secret:

```powershell
py -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output to `GITHUB_WEBHOOK_SECRET` in `.env`. Keep `.env` private; it is excluded by `.gitignore`.

The sample `.env` includes `master` for the public integration demonstration. Change `CHECKMATE_ALLOWED_BRANCHES` to your intended branches after the demo, for example `main,develop`.

A GitHub token is optional for this public-repository demonstration. If you configure one, use a token with the minimum required access and never commit it.

## 4. Start FastAPI

```powershell
uvicorn app.main:app --reload --port 8000
```

Keep this terminal open. Visit:

- Health: <http://127.0.0.1:8000/health>
- API docs: <http://127.0.0.1:8000/docs>

## 5. Test the GitHub client directly

Open a second PowerShell terminal in the project root and activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.test_github_client
```

This fetches a known public commit from `octocat/Hello-World`. It requires internet access.

## 6. Test the complete webhook-to-GitHub flow

Keep FastAPI running in the first terminal. In the second terminal, run:

```powershell
python -m scripts.send_github_commit_webhook
```

Expected outcome: HTTP 200, `status` of `accepted`, the real commit SHA, and a summary of changed files. This test generates a correctly signed simulated push event. It does not require a public HTTPS tunnel or an actual GitHub webhook delivery.

To test signature verification and branch filtering without contacting GitHub, run:

```powershell
python -m scripts.send_test_webhook
```

The expected response is `status: ignored` with `reason: branch_not_configured` because the test branch is intentionally not in the allow-list.

## 7. Run unit tests

```powershell
python -m unittest discover -s tests -v
```

## Current implementation status

**Completed:** FastAPI receiver, health endpoint, webhook signature validation, branch filtering, GitHub commit retrieval, changed-file metadata and source-content retrieval, JSON response summary.

**Next:** Implement the Ollama client, review prompts, review orchestrator, structured finding validation, line-length checking, chunking, and final PASS/FAIL report.

Ollama settings (`OLLAMA_BASE_URL` and `OLLAMA_MODEL`) are present in `.env.example` to prepare for the next milestone, but the current webhook does not call Ollama yet.

## Troubleshooting

- `ModuleNotFoundError: No module named 'app'`: run scripts as modules from the project root, e.g. `python -m scripts.test_github_client`.
- `GITHUB_WEBHOOK_SECRET is not configured`: make sure `.env` exists in the project root and the secret is set.
- `branch_not_configured`: add the test branch to `CHECKMATE_ALLOWED_BRANCHES`, or use the provided `.env.example` for the public demo.
- GitHub API failure: verify the repository/commit values, internet connection, API status, and any rate-limit response.
- Ollama is not called by this version yet; that integration comes next.
