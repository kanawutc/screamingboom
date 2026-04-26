"""Config profile schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """Crawl config stored in a profile."""

    max_urls: int = Field(default=10000, ge=1, le=100_000_000)
    max_depth: int = Field(default=10, ge=1, le=100)
    max_threads: int = Field(default=5, ge=1, le=50)
    rate_limit_rps: float = Field(default=2.0, gt=0, le=100)
    user_agent: str = "SEOSpider/1.0"
    respect_robots: bool = True
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=500)
    config: ProfileConfig = Field(default_factory=ProfileConfig)
    is_default: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: ProfileConfig | None = None
    is_default: bool | None = None


class ProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str
    config: dict
    is_default: bool
    created_at: datetime
    updated_at: datetime
