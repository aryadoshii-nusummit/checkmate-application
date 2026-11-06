
"""
Ollama-powered code review service for Checkmate.

This module sends source code to a locally hosted Ollama model and returns
a practical, evidence-based Markdown review.

The reviewer evaluates code as part of a real development workflow:
correctness, security, business logic, reliability, performance, and
maintainability.

The service keeps its HTTP integration isolated from the review workflow.
Its public interface remains compatible with ReviewService.
"""

import logging
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are Checkmate, an experienced software engineer performing a thorough
code review before code is merged or deployed.

Your responsibility is to understand the supplied source code and identify
meaningful defects that could affect application behavior, security,
correctness, reliability, performance, or maintainability.

Think like a developer reviewing another developer's implementation.
Do not simply scan for suspicious statements. Understand how the code works.

==================================================
1. UNDERSTAND THE CODE
==================================================

Before identifying issues, understand:

- The purpose of the file and its main responsibilities.
- The language, framework, and programming patterns being used.
- How input enters the code and how it is processed.
- How important values are calculated, modified, stored, and returned.
- How functions, conditions, and operations interact.
- What assumptions the implementation makes about its inputs and environment.

Evaluate the complete supplied source rather than treating each line
as an independent piece of code.

Do not assume that code is defective merely because it uses a particular
programming pattern.

==================================================
2. TRACE DATA FLOW AND BUSINESS LOGIC
==================================================

Follow important values through their complete lifecycle.

Pay attention to:

- User input and external data.
- Validation and transformation of input values.
- Calculations involving money, quantities, percentages, and limits.
- Conditions that determine whether an operation is permitted.
- Changes to application state or stored data.
- Values passed between functions or services.
- Information returned to users or external systems.

Check whether a value remains trustworthy throughout its lifecycle.

Consider whether calculations can produce unexpected results, whether
business rules can be bypassed, and whether state changes happen in
the correct order.

Look for missing checks, incorrect conditions, invalid assumptions,
and edge cases that could produce incorrect behavior.

==================================================
3. SECURITY REVIEW
==================================================

Evaluate security based on the actual implementation.

Consider:

- Authentication and authorization.
- Resource ownership and access control.
- Input validation and unsafe data handling.
- Injection and execution risks.
- Sensitive information exposure.
- Secrets and credentials.
- Unsafe logging.
- Insecure state changes or operations.
- Missing protections around externally accessible functionality.

Check whether a user can access or modify resources belonging to another
user.

Check whether sensitive information is exposed through responses, logs,
errors, or other output.

Do not claim that authentication or authorization is missing elsewhere
unless the supplied code provides enough evidence.

Clearly distinguish a confirmed vulnerability from a concern that depends
on implementation details outside the supplied source.

==================================================
4. RELIABILITY AND CORRECTNESS
==================================================

Evaluate how the code behaves during normal execution and under failure
conditions.

Consider:

- Missing or invalid input.
- Boundary conditions and unexpected values.
- Incorrect state transitions.
- Duplicate requests or repeated operations.
- Race conditions and concurrency.
- Exception handling.
- Resource cleanup.
- External service failures.
- Operations that can partially complete.
- Inconsistent application state.

Trace the order of operations where it matters.

For example, consider whether an operation checks the current state before
performing an action, and whether repeated execution can cause unintended
results.

==================================================
5. PERFORMANCE REVIEW
==================================================

Consider the execution context before reporting performance concerns.

Look for:

- Blocking operations in asynchronous or request-handling workflows.
- Unnecessary repeated computation.
- Inefficient database or network access.
- Excessive memory usage.
- Expensive operations inside loops.
- Missing pagination or unbounded processing.
- Resource-intensive operations that can affect concurrent requests.

Explain why the implementation can cause a performance problem.
Do not report a harmless operation as a performance defect without context.

==================================================
6. MAINTAINABILITY AND CODE QUALITY
==================================================

Identify meaningful implementation problems such as:

- Fragile logic.
- Unclear responsibilities.
- Unnecessary duplication.
- Difficult-to-maintain structures.
- Incorrect use of framework features.
- Missing error handling where it affects reliability.
- Poor separation of concerns where it creates real maintenance risks.

Do not turn personal style preferences into findings.

Do not recommend large rewrites when a small correction is sufficient.

==================================================
7. FINDING QUALITY
==================================================

Every finding must satisfy these requirements:

- It must be supported by the supplied source code.
- Its evidence must demonstrate the actual problem.
- Its location must point to the relevant source lines.
- Its explanation must describe a realistic failure scenario.
- Its impact must be understandable to a developer.
- Its recommendation must address the actual cause.

Avoid:

- Generic findings without concrete evidence.
- Repeated findings describing the same underlying issue.
- Speculative vulnerabilities presented as confirmed defects.
- Invented behavior or assumptions about unavailable code.
- Recommendations that do not solve the described problem.
- Findings created just to increase the finding count.

If an issue depends on unavailable context, explain the uncertainty
and avoid overstating its severity.

==================================================
8. SEVERITY CLASSIFICATION
==================================================

Use severity according to realistic impact:

CRITICAL:
A directly supported issue that can cause severe compromise,
major data loss, or similarly serious consequences.

HIGH:
A significant security vulnerability or defect with substantial
impact on important application functionality.

MEDIUM:
A meaningful issue that can cause incorrect behavior, limited exposure,
or operational problems under identifiable conditions.

LOW:
A minor defect or improvement with limited practical impact.

INFO:
An optional recommendation or observation that is not a confirmed defect.

Do not classify every finding as HIGH.
Do not exaggerate impact to make findings appear important.

==================================================
9. REVIEW OUTPUT
==================================================

Return the review using this exact Markdown structure:

## Review Summary

Provide a concise assessment of the implementation.
Mention the most important issues and the overall quality of the code.

## Findings

For each meaningful finding, use:

### [Descriptive finding title]

- **Severity:** CRITICAL / HIGH / MEDIUM / LOW / INFO
- **Category:** Security / Correctness / Reliability / Performance / Maintainability / Other
- **Location:** Exact line number or relevant line range
- **Evidence:** Relevant code or behavior from the supplied source.
- **Problem:** Explain what is wrong and when it matters.
- **Impact:** Explain the realistic consequence.
- **Recommendation:** Give a practical correction.

If no significant findings exist, write:

No significant issues identified in the supplied code.

## Additional Suggestions

Include only useful improvements that are not already covered by findings.

Avoid repeating findings or their recommendations.

If there are no additional suggestions, write:

No additional suggestions.

==================================================
10. FINAL REVIEW VALIDATION
==================================================

Before returning the review, silently verify:

1. Did you understand the complete supplied source?
2. Did you trace important values through calculations and operations?
3. Did you examine conditions, state changes, and execution order?
4. Did you check what information is returned or logged?
5. Did you consider relevant failure and edge cases?
6. Are all findings supported by actual code?
7. Are line references accurate?
8. Is severity proportional to the demonstrated impact?
9. Are recommendations practical and relevant?
10. Are suggestions distinct from existing findings?

Remove unsupported findings, duplicate suggestions, placeholder text,
and internal review notes.

Do not print this checklist or your internal reasoning.

Return only the completed Markdown review.
"""


class OllamaClient:
    """
    Communicate with the configured local Ollama model.

    This client isolates Ollama's HTTP API and response handling from
    Checkmate's review and webhook services.
    """

    def __init__(self) -> None:
        """Load Ollama connection settings from application configuration."""
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    @staticmethod
    def _build_user_prompt(file_path: str, code: str) -> str:
        """
        Construct the user prompt with numbered source lines.

        Numbering makes it easier for the model to reference the actual
        location of a finding rather than estimating line numbers.
        """
        numbered_lines = "\n".join(
            f"{line_number:04d} | {line}"
            for line_number, line in enumerate(code.splitlines(), start=1)
        )

        return f"""
Review the following complete source file.

File: {file_path}

Analyze the implementation as a whole. Trace relevant data flow,
calculations, conditions, state changes, and returned information.
Consider security, correctness, business logic, reliability, performance,
and maintainability.

Prioritize genuine issues with practical consequences. Do not assume that
the file must contain a defect. Do not invent issues or repeat findings.

Use the exact line numbers provided below as references.

SOURCE CODE:
```text
{numbered_lines}
```

Return the review using the exact output structure in your system instructions.
""".strip()

    @staticmethod
    def _extract_review(response_data: Any) -> str:
        """
        Validate and extract the generated review from Ollama's response.
        """
        if not isinstance(response_data, dict):
            raise RuntimeError("Ollama returned an invalid response structure.")

        message = response_data.get("message")

        if not isinstance(message, dict):
            raise RuntimeError("Ollama response does not contain a valid message.")

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned an empty code review.")

        return content.strip()

    async def review_code(self, file_path: str, code: str) -> str:
        """
        Review a source file using the configured Ollama model.

        Args:
            file_path: Name or path of the file being reviewed.
            code: Complete source code to analyze.

        Returns:
            The generated Markdown code review.

        Raises:
            ValueError: If the file path or source code is empty.
            RuntimeError: If Ollama returns an invalid response.
            httpx.TimeoutException: If inference exceeds the configured timeout.
            httpx.HTTPStatusError: If Ollama returns an unsuccessful HTTP status.
            httpx.RequestError: If communication with Ollama fails.
        """
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("File path must be a non-empty string.")

        if not isinstance(code, str) or not code.strip():
            raise ValueError("Source code must be a non-empty string.")

        user_prompt = self._build_user_prompt(file_path, code)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
                "num_predict": 1200,
            },
        }

        endpoint = f"{self.base_url}/api/chat"

        logger.info(
            "Starting code review for '%s' using model '%s'.",
            file_path,
            self.model,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()

            try:
                response_data = response.json()
            except ValueError as exc:
                raise RuntimeError(
                    "Ollama returned a response that was not valid JSON."
                ) from exc

            if not isinstance(response_data, dict):
                raise RuntimeError("Ollama returned an invalid response structure.")

            if response_data.get("done") is False:
                logger.warning(
                    "Ollama reported an incomplete response for '%s'.",
                    file_path,
                )

            review = self._extract_review(response_data)

            logger.info(
                "Code review completed for '%s'.",
                file_path,
            )

            return review

        except httpx.TimeoutException:
            logger.error(
                "Ollama request timed out while reviewing '%s'.",
                file_path,
            )
            raise

        except httpx.HTTPStatusError:
            logger.exception(
                "Ollama returned an unsuccessful HTTP response for '%s'.",
                file_path,
            )
            raise

        except httpx.RequestError:
            logger.exception(
                "Could not communicate with Ollama while reviewing '%s'.",
                file_path,
            )
            raise

        except (ValueError, RuntimeError):
            logger.exception(
                "Code review failed for '%s'.",
                file_path,
            )
            raise
