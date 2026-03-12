"""URL API routes — crawled URL queries, inlinks/outlinks, CSV export."""

from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.repositories.url_repo import UrlRepository
from app.schemas.pagination import CursorPage
from app.schemas.url import CrawledUrlDetail, CrawledUrlResponse

router = APIRouter(tags=["urls"])


@router.get(
    "/crawls/{crawl_id}/urls",
    response_model=CursorPage[CrawledUrlResponse],
)
async def list_crawled_urls(
    crawl_id: uuid.UUID,
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    status_code: int | None = Query(None, description="Filter by HTTP status code"),
    content_type: str | None = Query(None, description="Filter by content type (partial match)"),
    is_indexable: bool | None = Query(None, description="Filter by indexability"),
    search: str | None = Query(None, description="Search URL text (ILIKE)"),
    status_code_min: int | None = Query(None, description="Min status code (inclusive)"),
    status_code_max: int | None = Query(None, description="Max status code (inclusive)"),
    has_issue: str | None = Query(None, description="Filter by issue type"),
) -> CursorPage[CrawledUrlResponse]:
    repo = UrlRepository(db)
    result = await repo.list_by_crawl(
        crawl_id=crawl_id,
        cursor=cursor,
        limit=limit,
        status_code=status_code,
        content_type=content_type,
        is_indexable=is_indexable,
        search=search,
        status_code_min=status_code_min,
        status_code_max=status_code_max,
        has_issue=has_issue,
    )
    return CursorPage(
        items=[CrawledUrlResponse.model_validate(u) for u in result["items"]],
        next_cursor=result["next_cursor"],
    )


@router.get(
    "/crawls/{crawl_id}/urls/{url_id}",
    response_model=CrawledUrlDetail,
)
async def get_crawled_url(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    db: DbSession,
) -> CrawledUrlDetail:
    repo = UrlRepository(db)
    url = await repo.get_by_id(url_id=url_id, crawl_id=crawl_id)
    if url is None:
        raise HTTPException(status_code=404, detail="URL not found")
    return CrawledUrlDetail.model_validate(url)


@router.get("/crawls/{crawl_id}/urls/{url_id}/inlinks")
async def get_url_inlinks(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    repo = UrlRepository(db)
    return await repo.get_inlinks(crawl_id=crawl_id, url_id=url_id, limit=limit)


@router.get("/crawls/{crawl_id}/urls/{url_id}/outlinks")
async def get_url_outlinks(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    repo = UrlRepository(db)
    return await repo.get_outlinks(crawl_id=crawl_id, url_id=url_id, limit=limit)


EXPORT_COLUMNS = [
    "url",
    "status_code",
    "content_type",
    "title",
    "title_length",
    "title_pixel_width",
    "meta_description",
    "meta_desc_length",
    "h1",
    "h2",
    "canonical_url",
    "robots_meta",
    "is_indexable",
    "indexability_reason",
    "word_count",
    "crawl_depth",
    "response_time_ms",
    "redirect_url",
]


@router.get("/crawls/{crawl_id}/export")
async def export_crawl_csv(
    crawl_id: uuid.UUID,
    db: DbSession,
) -> StreamingResponse:
    repo = UrlRepository(db)

    async def _generate_csv():
        # Header row
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        yield buf.getvalue()

        # Stream data in batches
        async for batch in repo.stream_for_export(crawl_id=crawl_id, batch_size=500):
            buf = io.StringIO()
            writer = csv.writer(buf)
            for u in batch:
                row = []
                for col in EXPORT_COLUMNS:
                    val = getattr(u, col, None)
                    if isinstance(val, list):
                        val = " | ".join(str(v) for v in val)
                    row.append(val if val is not None else "")
                writer.writerow(row)
            yield buf.getvalue()

    return StreamingResponse(
        _generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=crawl_{crawl_id}.csv"},
    )
