"""CrawledUrl schemas for API request/response."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CrawledUrlResponse(BaseModel):
    """Standard crawled URL response for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    crawl_id: uuid.UUID
    url: str
    status_code: int | None = None
    content_type: str | None = None
    title: str | None = None
    title_length: int | None = None
    title_pixel_width: int | None = None
    meta_description: str | None = None
    meta_desc_length: int | None = None
    h1: list[str] | None = None
    h2: list[str] | None = None
    canonical_url: str | None = None
    robots_meta: list[str] | None = None
    is_indexable: bool
    indexability_reason: str | None = None
    word_count: int | None = None
    crawl_depth: int
    response_time_ms: int | None = None
    redirect_url: str | None = None
    link_score: int | None = None
    text_ratio: float | None = None
    readability_score: float | None = None
    avg_words_per_sentence: float | None = None
    crawled_at: datetime


class CrawledUrlDetail(CrawledUrlResponse):
    """Extended response with redirect chain and structured SEO data."""

    redirect_chain: list | None = None
    seo_data: dict = Field(default_factory=dict)


class ExternalLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_url: str
    source_url: str
    source_url_id: uuid.UUID
    anchor_text: str | None = None
    rel_attrs: list[str] | None = None
    link_position: str | None = None
    is_javascript: bool = False
