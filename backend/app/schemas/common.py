"""Common response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    services: dict[str, str]


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str | None = None
