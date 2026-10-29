
import asyncio

from app.review.ollama_client import OllamaClient


async def main():
    client = OllamaClient()

    sample_code = """
def divide(a, b):
    return a / b

print(divide(10, 0))
"""

    print(f"Testing model: {client.model}")
    print("Waiting for code review...\n")

    review = await client.review_code(
        file_path="example.py",
        code=sample_code,
    )

    print("=== CODE REVIEW ===")
    print(review)


if __name__ == "__main__":
    asyncio.run(main())
