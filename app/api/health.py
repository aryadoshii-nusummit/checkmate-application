"""Health-check endpoint for monitoring the Checkmate application."""

from fastapi import APIRouter


# Create a separate router for health-related endpoints.
# The health tag groups this endpoint in the FastAPI documentation.
router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """
    Check whether the Checkmate API is running.

    Returns:
        dict[str, str]: A simple response indicating the service status.
    """

    # Return a basic status response so monitoring tools and developers
    # can verify that the application is responding to requests.
    return {
        "status": "ok",
        "service": "checkmate",
    }