"""Crawl schemas for API request/response."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.custom_rules import CustomExtractorCreate, CustomSearchCreate


class CrawlStatus(StrEnum):
    """Possible crawl statuses."""

    idle = "idle"
    configuring = "configuring"
    queued = "queued"
    crawling = "crawling"
    paused = "paused"
    completing = "completing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CrawlMode(StrEnum):
    """Crawl modes."""

    spider = "spider"
    list = "list"


class CrawlConfig(BaseModel):
    """Configuration for a crawl session."""

    max_urls: int = Field(default=10000, ge=0, le=100_000_000)  # 0 = unlimited
    max_depth: int = Field(default=10, ge=1, le=100)
    max_threads: int = Field(default=5, ge=1, le=50)
    rate_limit_rps: float = Field(default=2.0, gt=0, le=100.0)
    user_agent: str = Field(default="SEOSpider/1.0", max_length=500)
    respect_robots: bool = True
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    url_rewrites: list[dict] = Field(default_factory=list)
    strip_query_params: list[str] = Field(default_factory=list)
    render_js: bool = False
    auth_type: str | None = Field(default=None, description="Authentication type: 'basic', 'bearer', or None")
    auth_username: str | None = Field(default=None, max_length=255)
    auth_password: str | None = Field(default=None, max_length=255)
    auth_token: str | None = Field(default=None, max_length=2000, description="Bearer token")
    custom_headers: dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")


class CrawlCreate(BaseModel):
    """Schema for creating/starting a new crawl.

    Spider mode: requires start_url.
    List mode: requires urls (list of URLs to crawl).
    """

    start_url: str = Field(default="", min_length=0)
    urls: list[str] | None = None
    mode: CrawlMode = CrawlMode.spider
    config: CrawlConfig = Field(default_factory=CrawlConfig)
    project_id: uuid.UUID | None = None
    custom_extractors: list[CustomExtractorCreate] = Field(default_factory=list)
    custom_searches: list[CustomSearchCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "CrawlCreate":
        """Enforce mode-dependent required fields."""
        if self.mode == CrawlMode.spider and not self.start_url.strip():
            raise ValueError("start_url is required for spider mode")
        if self.mode == CrawlMode.list:
            if not self.urls or len(self.urls) == 0:
                raise ValueError("urls list is required for list mode")
        return self


class CrawlResponse(BaseModel):
    """Full crawl response for detail views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: CrawlStatus
    mode: CrawlMode
    config: dict
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_urls: int
    crawled_urls_count: int
    error_count: int
    created_at: datetime


class CrawlContinue(BaseModel):
    """Schema for continuing an existing crawl from uncrawled links."""

    additional_urls: int = Field(default=0, ge=0, le=100_000_000)  # 0 = unlimited


class CrawlSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: CrawlStatus
    mode: CrawlMode
    config: dict
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_urls: int
    crawled_urls_count: int
    error_count: int = 0
    created_at: datetime
