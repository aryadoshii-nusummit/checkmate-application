import os

import httpx
from dotenv import load_dotenv

load_dotenv()


class OllamaClient:
    def __init__(self):
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434",
        ).rstrip("/")

        self.model = os.getenv(
            "OLLAMA_MODEL",
            "qwen2.5-coder:3b",
        )

        self.timeout = float(
            os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")
        )

    async def review_code(
        self,
        file_path: str,
        code: str,
    ) -> str:
        prompt = f"""
You are a careful senior software engineer performing a code review.

Review the following changed file.

File path: {file_path}

Look for:
1. Bugs and incorrect logic
2. Security vulnerabilities
3. Error-handling problems
4. Performance issues
5. Maintainability concerns

Only report issues supported by the code. Do not invent problems.
If you find no issues, say so clearly.
For each finding, explain the problem, its severity, and a suggested fix.

Return a readable Markdown report.

Code to review:
```text
{code}
```
"""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
        }

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )

            response.raise_for_status()
            result = response.json()

        review = result.get("message", {}).get("content")

        if not review:
            raise RuntimeError(
                "Ollama returned an empty review."
            )

        return review.strip()
