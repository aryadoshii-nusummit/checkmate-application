"""Health-check endpoint for monitoring the Checkmate application."""

from fastapi import APIRouter

from app.models.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check whether the Checkmate API is running."""

    return HealthResponse(
        status="ok",
        service="checkmate",
    )