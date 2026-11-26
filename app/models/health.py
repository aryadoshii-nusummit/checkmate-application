"""Pydantic model for the health-check API response."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str