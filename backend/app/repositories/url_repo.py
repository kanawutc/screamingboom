"""URL repository — queries for crawled_urls partitioned table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import PageLink
from app.models.issue import UrlIssue
from app.models.url import CrawledUrl


class UrlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_crawl(
        self,
        crawl_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
        status_code: int | None = None,
        content_type: str | None = None,
        is_indexable: bool | None = None,
        search: str | None = None,
        status_code_min: int | None = None,
        status_code_max: int | None = None,
        has_issue: str | None = None,
    ) -> dict[str, Any]:
        """List URLs for a crawl with cursor pagination and optional filters.

        Args:
            search: URL text search (ILIKE match)
            status_code_min/max: Status code range filter (e.g. 300-399 for redirects)
            has_issue: Filter by issue type (e.g. 'missing_title', 'duplicate_title')
        """
        query = select(CrawledUrl).where(CrawledUrl.crawl_id == crawl_id)

        # Optional filters
        if status_code is not None:
            query = query.where(CrawledUrl.status_code == status_code)
        if status_code_min is not None:
            query = query.where(CrawledUrl.status_code >= status_code_min)
        if status_code_max is not None:
            query = query.where(CrawledUrl.status_code <= status_code_max)
        if content_type is not None:
            safe_ct = content_type.replace("%", "\\%").replace("_", "\\_")
            query = query.where(CrawledUrl.content_type.ilike(f"%{safe_ct}%"))
        if is_indexable is not None:
            query = query.where(CrawledUrl.is_indexable == is_indexable)
        if search is not None and search.strip():
            safe_search = search.strip().replace("%", "\\%").replace("_", "\\_")
            query = query.where(CrawledUrl.url.ilike(f"%{safe_search}%"))

        # Semantic issue filter — join with url_issues to find URLs with specific issues
        if has_issue is not None and has_issue.strip():
            issue_subquery = (
                select(UrlIssue.url_id)
                .where(
                    UrlIssue.crawl_id == crawl_id,
                    UrlIssue.issue_type == has_issue.strip(),
                )
                .distinct()
                .scalar_subquery()
            )
            query = query.where(CrawledUrl.id.in_(issue_subquery))

        # Cursor pagination
        if cursor:
            try:
                cursor_uuid = uuid.UUID(cursor)
            except (ValueError, AttributeError):
                return {"items": [], "next_cursor": None}
            query = query.where(CrawledUrl.id > cursor_uuid)

        query = query.order_by(CrawledUrl.id).limit(limit + 1)

        result = await self._session.execute(query)
        items = list(result.scalars().all())

        has_more = len(items) > limit
        page_items = items[:limit]
        next_cursor = str(page_items[-1].id) if has_more and page_items else None

        return {"items": page_items, "next_cursor": next_cursor}

    async def get_by_id(
        self,
        url_id: uuid.UUID,
        crawl_id: uuid.UUID,
    ) -> CrawledUrl | None:
        """Get a specific URL by its composite key (id + crawl_id)."""
        query = select(CrawledUrl).where(CrawledUrl.id == url_id, CrawledUrl.crawl_id == crawl_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_url_hash(
        self,
        crawl_id: uuid.UUID,
        url_hash: bytes,
    ) -> CrawledUrl | None:
        """Look up a URL by its hash within a crawl (for dedup checking)."""
        query = select(CrawledUrl).where(
            CrawledUrl.crawl_id == crawl_id,
            CrawledUrl.url_hash == url_hash,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def count_by_crawl(
        self,
        crawl_id: uuid.UUID,
        status_code: int | None = None,
    ) -> int:
        """Count URLs for a crawl, optionally filtered by status code."""
        query = select(func.count()).select_from(CrawledUrl).where(CrawledUrl.crawl_id == crawl_id)
        if status_code is not None:
            query = query.where(CrawledUrl.status_code == status_code)
        result = await self._session.execute(query)
        return result.scalar_one()

    async def count_errors_by_crawl(self, crawl_id: uuid.UUID) -> int:
        """Count URLs with error status codes (>= 400) for a crawl."""
        query = (
            select(func.count())
            .select_from(CrawledUrl)
            .where(
                CrawledUrl.crawl_id == crawl_id,
                CrawledUrl.status_code >= 400,
            )
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_inlinks(
        self,
        crawl_id: uuid.UUID,
        url_id: uuid.UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all pages that link TO a specific URL (inlinks).

        Returns links from page_links where target_url matches.
        """
        url_obj = await self.get_by_id(url_id=url_id, crawl_id=crawl_id)
        if url_obj is None:
            return []
        query = (
            select(
                CrawledUrl.url.label("source_url"),
                PageLink.anchor_text,
                PageLink.link_type,
                PageLink.rel_attrs,
                PageLink.link_position,
                PageLink.is_javascript,
            )
            .join(
                CrawledUrl,
                (CrawledUrl.id == PageLink.source_url_id)
                & (CrawledUrl.crawl_id == PageLink.crawl_id),
            )
            .where(
                PageLink.crawl_id == crawl_id,
                PageLink.target_url == url_obj.url,
            )
            .limit(limit)
        )

        result = await self._session.execute(query)
        rows = result.all()

        return [
            {
                "source_url": row.source_url,
                "anchor_text": row.anchor_text,
                "link_type": row.link_type,
                "rel_attrs": row.rel_attrs or [],
                "link_position": row.link_position,
                "is_javascript": row.is_javascript,
            }
            for row in rows
        ]

    async def get_outlinks(
        self,
        crawl_id: uuid.UUID,
        url_id: uuid.UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all links FROM a specific URL (outlinks)."""
        query = (
            select(
                PageLink.target_url,
                PageLink.anchor_text,
                PageLink.link_type,
                PageLink.rel_attrs,
                PageLink.link_position,
                PageLink.is_javascript,
            )
            .where(
                PageLink.crawl_id == crawl_id,
                PageLink.source_url_id == url_id,
            )
            .limit(limit)
        )

        result = await self._session.execute(query)
        rows = result.all()

        return [
            {
                "target_url": row.target_url,
                "anchor_text": row.anchor_text,
                "link_type": row.link_type,
                "rel_attrs": row.rel_attrs or [],
                "link_position": row.link_position,
                "is_javascript": row.is_javascript,
            }
            for row in rows
        ]

    async def stream_for_export(
        self,
        crawl_id: uuid.UUID,
        batch_size: int = 500,
    ):
        """Yield URL batches for streaming CSV export to avoid OOM on large crawls."""
        query = (
            select(CrawledUrl)
            .where(CrawledUrl.crawl_id == crawl_id)
            .order_by(CrawledUrl.crawl_depth, CrawledUrl.url)
            .execution_options(yield_per=batch_size)
        )
        result = await self._session.stream(query)
        async for partition in result.partitions(batch_size):
            yield [row[0] for row in partition]
