"""Common API response models."""

from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] | list[Any] | None = None