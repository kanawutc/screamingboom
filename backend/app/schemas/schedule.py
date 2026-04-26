"""Crawl schedule schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleCrawlConfig(BaseModel):
    """Crawl configuration stored with a schedule."""

    start_url: str | None = None
    max_urls: int = Field(default=10000, ge=1, le=100_000_000)
    max_depth: int = Field(default=10, ge=1, le=100)
    max_threads: int = Field(default=5, ge=1, le=50)
    rate_limit_rps: float = Field(default=2.0, gt=0, le=100)
    user_agent: str = "SEOSpider/1.0"
    respect_robots: bool = True
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


class ScheduleCreate(BaseModel):
    """Schema for creating a crawl schedule."""

    name: str = Field(min_length=1, max_length=255)
    cron_expression: str = Field(
        min_length=1,
        max_length=100,
        description="Cron expression (e.g. '0 2 * * 1' for Monday 2am)",
    )
    crawl_config: ScheduleCrawlConfig = Field(default_factory=ScheduleCrawlConfig)
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    """Schema for updating a crawl schedule."""

    name: str | None = None
    cron_expression: str | None = None
    crawl_config: ScheduleCrawlConfig | None = None
    is_active: bool | None = None


class ScheduleResponse(BaseModel):
    """Response schema for a crawl schedule."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    cron_expression: str
    crawl_config: dict
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_crawl_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
