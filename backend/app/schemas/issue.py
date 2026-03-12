"""Pydantic schemas for SEO issues API responses."""

from __future__ import annotations

from pydantic import BaseModel


class IssueResponse(BaseModel):
    """Single issue record returned from the issues list endpoint."""

    id: str
    crawl_id: str
    url_id: str
    url: str  # Joined from crawled_urls
    issue_type: str
    severity: str
    category: str
    description: str  # From issue registry
    details: dict

    model_config = {"from_attributes": True}


class IssueSummary(BaseModel):
    """Aggregated issue counts by severity and category."""

    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
