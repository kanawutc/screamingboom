"""Pagination schemas for cursor-based pagination."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for cursor-based pagination."""

    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class CursorPage(BaseModel, Generic[T]):
    """Generic cursor-paginated response."""

    items: list[T]
    next_cursor: str | None = None
    total_count: int | None = None
