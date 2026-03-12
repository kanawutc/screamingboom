"""Crawl comparison endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession
from app.repositories.url_repo import UrlRepository
from app.schemas.comparison import (
    CrawlComparisonResponse,
    CrawlComparisonSummary,
    CrawlComparisonUrl,
)

router = APIRouter(tags=["comparison"])


@router.get("/crawls/compare", response_model=CrawlComparisonResponse)
async def compare_crawls(
    db: DbSession,
    crawl_a: uuid.UUID = Query(..., description="First crawl ID (baseline)"),
    crawl_b: uuid.UUID = Query(..., description="Second crawl ID (comparison)"),
    change_type: str | None = Query(None, description="Filter: added, removed, changed, unchanged"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> CrawlComparisonResponse:
    if crawl_a == crawl_b:
        raise HTTPException(status_code=400, detail="Cannot compare a crawl with itself")

    if change_type and change_type not in ("added", "removed", "changed", "unchanged"):
        raise HTTPException(
            status_code=400,
            detail="change_type must be one of: added, removed, changed, unchanged",
        )

    repo = UrlRepository(db)
    result = await repo.compare_crawls(
        crawl_a_id=crawl_a,
        crawl_b_id=crawl_b,
        change_type=change_type,
        limit=limit,
        offset=offset,
    )

    return CrawlComparisonResponse(
        crawl_a_id=crawl_a,
        crawl_b_id=crawl_b,
        summary=CrawlComparisonSummary(**result["summary"]),
        urls=[CrawlComparisonUrl(**u) for u in result["urls"]],
        total_count=result["total_count"],
    )
