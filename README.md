# Checkmate ♟️
### AI-Powered GitHub Code Review System

Checkmate is a local AI-powered code review application that automatically reviews code changes when a GitHub push event is received. It uses **FastAPI** to receive webhooks, the **GitHub REST API** to retrieve commit information and changed files, and **Ollama** to run a local large language model for code review.

The goal of Checkmate is to help developers identify potential bugs, security vulnerabilities, performance issues, and maintainability concerns early in the development workflow.

> **Project status:** Working prototype. The core webhook-to-AI-review workflow has been tested locally. This is an educational and development project, not a replacement for professional code review or dedicated security analysis.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [Technology Stack](#3-technology-stack)
4. [How Checkmate Works](#4-how-checkmate-works)
5. [Project Structure](#5-project-structure)
6. [Prerequisites](#6-prerequisites)
7. [Installation and Setup](#7-installation-and-setup)
8. [Configuration](#8-configuration)
9. [Running the Application](#9-running-the-application)
10. [Testing the Workflow](#10-testing-the-workflow)
11. [API Endpoints](#11-api-endpoints)
12. [Security Considerations](#12-security-considerations)
13. [Current Limitations](#13-current-limitations)
14. [Future Improvements](#14-future-improvements)
15. [Architecture and Folder Structure Alignment](#15-architecture-and-folder-structure-alignment)

---

## 1. Project Overview

Code reviews are an important part of software development, but manual reviews can take time and may overlook certain issues. Checkmate explores how a locally running AI model can assist with this process by reviewing changes associated with GitHub commits.

When a configured GitHub push event reaches Checkmate, the application validates the webhook signature, checks whether the event should be processed, retrieves the relevant commit and changed-file information, and sends eligible code to the local AI model.

The model's response is collected and returned as a structured HTTP response for inspection.

### Project objectives

- Automate the initial review of GitHub code changes.
- Identify potential bugs and security weaknesses.
- Use a locally running AI model instead of requiring a hosted LLM API for code review.
- Separate webhook handling, GitHub communication, review orchestration, and AI interaction.
- Provide a foundation for future improvements to review quality, reporting, and project architecture.

---

## 2. Key Features

### GitHub webhook integration

- Provides a FastAPI endpoint to receive GitHub webhook requests.
- Validates the webhook signature using HMAC-SHA256.
- Filters events according to the application's configured repository, branch, and other processing conditions.
- Retrieves commit information and changed-file details through the GitHub REST API.

### AI-assisted code review

- Uses Ollama to run a code-capable language model locally.
- Sends eligible source-code changes to the model for review.
- Collects the model's findings for inspection.
- Supports recording files that were skipped by the review process.

### Modular application design

The current implementation separates the application into modules responsible for API handling, configuration, GitHub integration, review orchestration, AI communication, and webhook security.

### Local testing support

The `scripts/` directory contains utilities for exercising the webhook workflow and testing individual integrations without needing to trigger every scenario through GitHub.

---

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Primary programming language |
| FastAPI | Web application and HTTP endpoints |
| Uvicorn | ASGI server used to run FastAPI |
| GitHub REST API | Retrieves commit information and changed files |
| Ollama | Runs the AI model locally |
| Qwen2.5-Coder 3B | Local code-review model used during development |
| HTTPX | Makes asynchronous HTTP requests |
| python-dotenv | Loads environment variables from `.env` |
| pytest | Can be used for automated Python tests |

The model and its output are used as review assistance. Model findings require human verification.

---

## 4. How Checkmate Works

The following flow describes the intended processing path for a supported GitHub push event.

```text
Developer pushes code to GitHub
              |
              v
      GitHub push webhook
              |
              v
    FastAPI webhook endpoint
              |
              v
    Verify webhook signature
              |
              v
   Validate event and filters
              |
              v
   Fetch commit from GitHub API
              |
              v
  Identify eligible changed files
              |
              v
     Review orchestrator
              |
              v
      Local Ollama model
              |
              v
     Collect review results
              |
              v
       Return JSON response
```

### Step-by-step execution

1. **Receive the event:** GitHub sends a push webhook to the application's webhook endpoint.
2. **Verify authenticity:** The webhook handler checks the `X-Hub-Signature-256` header against the request body using the configured webhook secret.
3. **Apply filters:** The application checks whether the event and repository, branch, and commit satisfy its processing conditions.
4. **Retrieve commit details:** The GitHub client fetches the commit and relevant changed-file content.
5. **Select files:** The review orchestrator determines which files are eligible for review and which should be skipped.
6. **Generate a review:** The Ollama client sends the eligible code and review prompt to the locally running model.
7. **Collect results:** The orchestrator gathers the review responses and skip information.
8. **Return a response:** The webhook endpoint returns the processing results as JSON.

**Important:** The local webhook simulation script is a test client. It constructs a sample push payload and signs it with the configured secret before sending it to the local FastAPI server. It is not part of GitHub's production webhook delivery mechanism.

---

## 5. Project Structure

The following is the current project structure. It reflects the implementation as it exists today, rather than the proposed future folder layout.

```text
checkmate_application/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── github_webhook.py
│   │   └── health.py
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── github_client.py
│   │
│   ├── review/
│   │   ├── orchestrator.py
│   │   └── ollama_client.py
│   │
│   └── security/
│       ├── __init__.py
│       └── webhook_signature.py
│
├── scripts/
│   ├── __init__.py
│   ├── send_github_commit_webhook.py
│   ├── send_test_webhook.py
│   ├── test_github_client.py
│   └── test_ollama.py
│
├── tests/
│   ├── test_signature.py
│   └── test_case_02_payment_api.py
│
├── .env.example
├── .gitignore
├── PROJECT_STATUS.md
├── README.md
└── requirements.txt
```

### Responsibilities of the main files and folders

#### `app/main.py` — Application entry point

Creates the FastAPI application and registers the API routers.

#### `app/api/` — API routes

- `github_webhook.py`: Receives GitHub webhook events and coordinates the request-processing flow.
- `health.py`: Exposes a health endpoint for checking whether the application is running.

#### `app/integrations/` — External integrations

- `github_client.py`: Communicates with the GitHub REST API to retrieve commit information and changed-file content.

#### `app/review/` — Review logic

- `orchestrator.py`: Coordinates file selection, review execution, and collection of review results.
- `ollama_client.py`: Communicates with the local Ollama API and extracts the model's review response.

#### `app/security/` — Security utilities

- `webhook_signature.py`: Verifies the webhook signature using HMAC-SHA256.

#### `app/config.py` — Application configuration

Loads the application's environment-based configuration, including the settings required by the integrations and webhook processing.

#### `scripts/` — Development and integration test utilities

- `send_github_commit_webhook.py`: Sends a signed, simulated push event to the local application.
- `send_test_webhook.py`: Exercises webhook filtering with a test event.
- `test_github_client.py`: Tests the GitHub client independently.
- `test_ollama.py`: Tests the Ollama client independently.

#### `tests/` — Test cases and fixtures

- `test_signature.py`: Contains automated tests for webhook signature verification.
- `test_case_02_payment_api.py`: Contains an intentionally vulnerable payment API fixture for demonstrating AI-assisted code review. It is not a production payment implementation.

#### `.env.example`

Provides a template for the environment variables required to configure a local instance.

#### `.env`

Stores local environment-specific settings and secrets. This file should remain local and must not be committed to Git.

#### `requirements.txt`

Lists the Python dependencies needed by the application.

---

## 6. Prerequisites

Before running Checkmate, ensure the following are available:

- Python installed on your system.
- Git installed and configured.
- A local Ollama installation.
- A code-capable Ollama model downloaded.
- Access to the GitHub repository whose commits you want to review.
- A configured `.env` file with the values required by the application.

The current development setup uses the `qwen2.5-coder:3b` model.

---

## 7. Installation and Setup

### Step 1: Clone the repository

```bash
git clone https://github.com/aryadoshii-nusummit/checkmate-application.git
cd checkmate-application
```

### Step 2: Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script activation, you can use the environment's Python executable directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Step 3: Install dependencies

If the virtual environment is activated:

```bash
python -m pip install -r requirements.txt
```

### Step 4: Configure environment variables

Create a local `.env` file by copying the example:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and supply the required values for your environment. Refer to `.env.example` and `app/config.py` for the actual setting names and expected formats.

Do not copy real secrets into `.env.example` or commit `.env` to GitHub.

### Step 5: Install and start Ollama

Install Ollama from its official website:

https://ollama.com/

Download the model used for development:

```bash
ollama pull qwen2.5-coder:3b
```

Ollama normally exposes its local API at:

```text
http://localhost:11434
```

Ensure Ollama is running and the model is available before triggering a code review.

---

## 8. Configuration

Checkmate uses environment variables to separate machine-specific settings and secrets from application code.

The `.env.example` file is the reference template for local configuration.

Typical configuration categories include:

- GitHub repository, branch, and commit settings for test scenarios.
- GitHub API authentication settings, if required by the current client configuration.
- The GitHub webhook secret used to verify incoming signatures.
- Ollama's local API endpoint and model selection.
- HTTP timeout settings for longer AI review requests.

Use the exact variable names documented in `.env.example` and loaded by `app/config.py`. Do not assume that every optional setting is enabled in every configuration.

### Security reminder

Never publish GitHub tokens, webhook secrets, or other credentials. Keep them in `.env` or a suitable secret-management system and ensure they are excluded by `.gitignore`.

---

## 9. Running the Application

Open a terminal in the project directory and activate the virtual environment.

Start the FastAPI server:

```bash
python -m uvicorn app.main:app --reload
```

The local application will normally be available at:

```text
http://127.0.0.1:8000
```

The `--reload` option is intended for development. It automatically restarts the server when source files change.

### Interactive API documentation

FastAPI typically exposes interactive documentation at:

```text
http://127.0.0.1:8000/docs
```

Use the documented endpoints to inspect the application's available API routes.

Keep the server running while you execute the webhook simulation scripts in a second terminal.

---

## 10. Testing the Workflow

Checkmate includes utilities for testing individual integrations and the end-to-end local webhook flow.

### Test the GitHub client

```bash
python -m scripts.test_github_client
```

This utility exercises GitHub commit retrieval independently of the webhook simulation.

### Test the Ollama client

```bash
python -m scripts.test_ollama
```

This utility checks communication with the local Ollama model.

### Test webhook filtering

```bash
python -m scripts.send_test_webhook
```

This utility sends a test webhook designed to exercise the configured branch or event filters.

### Run the end-to-end local webhook simulation

With the FastAPI server running in a separate terminal:

```bash
python -m scripts.send_github_commit_webhook
```

This script builds and signs a simulated GitHub push payload, sends it to the local webhook endpoint, and prints the resulting response.

The script depends on the appropriate test repository, branch, commit, webhook secret, and other required configuration being present in `.env`.

### Run the automated signature tests

```bash
python -m pytest tests/test_signature.py -v
```

If pytest is not installed in the environment, install it before running this command.

### Test the review fixture

`tests/test_case_02_payment_api.py` is a deliberately insecure sample used to demonstrate what Checkmate may flag during a code review. It is a review target, not a test that should be deployed as a real payment service.

---

## 11. API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | `GET` | Health check, as registered by the health router |
| `/webhooks/github` | `POST` | Receives GitHub webhook events |

The health route's exact response format is defined in `app/api/health.py`.

The webhook endpoint expects a GitHub-compatible webhook request, including the relevant signature header. Its response reports the outcome of processing the event, including review information or filtering results as implemented by the application.

Check `/docs` while the application is running for the registered paths and their current request and response schemas.

---

## 12. Security Considerations

Security is an important focus of Checkmate, but the application is still a prototype.

### Webhook signature verification

The application verifies `X-Hub-Signature-256` against the raw request body using the configured shared secret and HMAC-SHA256.

Signature verification helps detect requests that do not have a valid signature for the configured secret. It should be complemented by appropriate webhook configuration, delivery checks, and operational controls.

### Secrets and configuration

- Do not commit `.env`.
- Do not place live credentials in source files or example configuration.
- Use appropriately scoped credentials when authentication is needed.
- Rotate any credential that has been exposed.

### AI-generated findings

An AI review is not proof that a vulnerability exists or that code is safe.

The model may:

- Report an issue that is not present in the code.
- Miss a genuine vulnerability.
- Misunderstand surrounding application context.
- Produce inconsistent recommendations.

Treat its output as a list of suggestions for human verification. Findings should be checked against the actual source code and application requirements.

### Vulnerable test fixture

The payment API fixture is intentionally insecure for review demonstrations. It must not be used as a real payment implementation or deployed as a production service.

### Development server

Uvicorn's `--reload` option is for local development, not production deployment. A production setup would require additional deployment, access-control, logging, monitoring, and security considerations.

---

## 13. Current Limitations

The current implementation is a working prototype and has the following limitations:

- Review quality depends on the local model and the quality of the prompt.
- Model responses can contain false positives or false negatives.
- Large files or complex changes may require more processing time and careful timeout configuration.
- The current flow is designed around webhook-triggered review and does not yet provide a full review dashboard.
- A database-backed review history is not currently part of the documented project structure.
- The application does not replace a complete security testing pipeline, static analysis, or human review.
- The current code structure may be reorganized to match the agreed project architecture.

---

## 14. Future Improvements

Potential future enhancements include:

- Posting review summaries directly to GitHub pull requests or commit discussions.
- Producing more structured findings with severity, file, line number, and remediation suggestions.
- Adding safeguards against unsupported or hallucinated findings.
- Introducing a persistent database for review history and execution status.
- Supporting configurable file exclusions and review policies.
- Adding stronger automated integration and end-to-end tests.
- Improving timeout handling, retries, and error reporting.
- Adding structured logging and observability.
- Supporting deployment beyond a local development environment.

These are planned improvements, not claims about currently implemented functionality.

---

## 15. Architecture and Folder Structure Alignment

**Status: To be discussed and implemented following manager feedback.**

The current implementation uses an `app/` package containing API routes, integrations, review logic, security utilities, and configuration.

The proposed organizational direction is to align the project with the following responsibility-based structure:

```text
checkmate_application/
│
├── main/          # Application entry point
├── api/           # HTTP endpoints and route handlers
├── services/      # Application logic and external integrations
├── database/      # Database access and persistence, when introduced
├── constants/     # Shared static values and constants
├── config/        # Application configuration
│
├── scripts/       # Development and integration test utilities
├── tests/         # Automated tests and review fixtures
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

This is a **proposed target structure**, not the current directory layout.

The exact responsibilities and placement of modules will be reviewed with the manager before making the changes. In particular:

- Existing API route handlers will be mapped to the API layer.
- Review orchestration and integration logic will be mapped to the services layer.
- Configuration and shared constants will be separated where appropriate.
- A database layer will be introduced if and when persistence is required.
- The application entry point and imports will be updated as needed during an approved migration.

The reorganization will preserve existing application behavior as far as possible, with appropriate import updates and regression tests to ensure the webhook-to-review workflow continues to work.

---

## 16. Project Summary

Checkmate demonstrates an end-to-end approach to AI-assisted code review using GitHub webhooks, FastAPI, the GitHub REST API, and a locally hosted Ollama model.

Its current focus is to establish the core workflow, keep responsibilities separated, and provide a foundation for further improvements.

The next architectural step is to review the proposed folder structure with the manager and then implement the agreed changes carefully, without disrupting the existing functionality.

**Repository:** https://github.com/aryadoshii-nusummit/checkmate-application
