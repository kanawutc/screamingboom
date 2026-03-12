"""Pydantic schemas for API request/response validation."""

from app.schemas.common import ErrorResponse, HealthResponse
from app.schemas.crawl import (
    CrawlConfig,
    CrawlCreate,
    CrawlMode,
    CrawlResponse,
    CrawlStatus,
    CrawlSummary,
)
from app.schemas.pagination import CursorPage, PaginationParams
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.url import CrawledUrlDetail, CrawledUrlResponse

__all__ = [
    # Common
    "HealthResponse",
    "ErrorResponse",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    # Crawl
    "CrawlConfig",
    "CrawlCreate",
    "CrawlMode",
    "CrawlResponse",
    "CrawlStatus",
    "CrawlSummary",
    # URL
    "CrawledUrlResponse",
    "CrawledUrlDetail",
    # Pagination
    "PaginationParams",
    "CursorPage",
]
