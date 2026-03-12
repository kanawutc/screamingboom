"""Crawl comparison schemas."""

import uuid

from pydantic import BaseModel


class CrawlComparisonUrl(BaseModel):
    url: str
    change_type: str
    a_status_code: int | None = None
    a_title: str | None = None
    a_word_count: int | None = None
    a_response_time_ms: int | None = None
    a_is_indexable: bool | None = None
    b_status_code: int | None = None
    b_title: str | None = None
    b_word_count: int | None = None
    b_response_time_ms: int | None = None
    b_is_indexable: bool | None = None


class CrawlComparisonSummary(BaseModel):
    total_urls_a: int
    total_urls_b: int
    added: int
    removed: int
    changed: int
    unchanged: int


class CrawlComparisonResponse(BaseModel):
    crawl_a_id: uuid.UUID
    crawl_b_id: uuid.UUID
    summary: CrawlComparisonSummary
    urls: list[CrawlComparisonUrl]
    total_count: int
