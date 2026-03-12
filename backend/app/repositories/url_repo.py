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
                PageLink.target_url_hash == url_obj.url_hash,
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

    async def list_external_links(
        self,
        crawl_id: uuid.UUID,
        cursor: int | None = None,
        limit: int = 50,
        search: str | None = None,
        nofollow: bool | None = None,
    ) -> dict[str, Any]:
        query = (
            select(
                PageLink.id,
                PageLink.target_url,
                CrawledUrl.url.label("source_url"),
                PageLink.source_url_id,
                PageLink.anchor_text,
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
                PageLink.link_type == "external",
            )
        )

        if search and search.strip():
            safe = search.strip().replace("%", "\\%").replace("_", "\\_")
            query = query.where(PageLink.target_url.ilike(f"%{safe}%"))

        if nofollow is True:
            query = query.where(text("'nofollow' = ANY(page_links.rel_attrs)"))
        elif nofollow is False:
            query = query.where(
                text("('nofollow' != ALL(page_links.rel_attrs) OR page_links.rel_attrs IS NULL)")
            )

        if cursor is not None:
            query = query.where(PageLink.id > cursor)

        query = query.order_by(PageLink.id).limit(limit + 1)

        result = await self._session.execute(query)
        rows = list(result.all())

        has_more = len(rows) > limit
        page_items = rows[:limit]
        next_cursor = str(page_items[-1].id) if has_more and page_items else None

        items = [
            {
                "id": r.id,
                "target_url": r.target_url,
                "source_url": r.source_url,
                "source_url_id": r.source_url_id,
                "anchor_text": r.anchor_text,
                "rel_attrs": r.rel_attrs or [],
                "link_position": r.link_position,
                "is_javascript": r.is_javascript,
            }
            for r in page_items
        ]

        return {"items": items, "next_cursor": next_cursor}

    async def stream_for_export(
        self,
        crawl_id: uuid.UUID,
        batch_size: int = 500,
    ):
        query = (
            select(CrawledUrl)
            .where(CrawledUrl.crawl_id == crawl_id)
            .order_by(CrawledUrl.crawl_depth, CrawledUrl.url)
            .execution_options(yield_per=batch_size)
        )
        result = await self._session.stream(query)
        async for partition in result.partitions(batch_size):
            yield [row[0] for row in partition]

    async def list_with_structured_data(
        self,
        crawl_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        query = select(CrawledUrl).where(
            CrawledUrl.crawl_id == crawl_id,
            text("seo_data ? 'json_ld'"),
            text("jsonb_array_length(seo_data->'json_ld') > 0"),
        )
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

    async def list_with_custom_extractions(
        self,
        crawl_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List URLs that have custom extraction results in seo_data."""
        query = select(CrawledUrl).where(
            CrawledUrl.crawl_id == crawl_id,
            text("seo_data ? 'custom_extractions'"),
            text("seo_data->'custom_extractions' != '{}'::jsonb"),
        )
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

    async def stream_for_sitemap(
        self,
        crawl_id: uuid.UUID,
        include_non_indexable: bool = False,
        include_non_200: bool = False,
        batch_size: int = 500,
    ):
        query = select(CrawledUrl).where(CrawledUrl.crawl_id == crawl_id)
        if not include_non_indexable:
            query = query.where(CrawledUrl.is_indexable.is_(True))
        if not include_non_200:
            query = query.where(CrawledUrl.status_code == 200)
        query = (
            query.where(CrawledUrl.content_type.ilike("text/html%"))
            .order_by(CrawledUrl.crawl_depth, CrawledUrl.url)
            .execution_options(yield_per=batch_size)
        )
        result = await self._session.stream(query)
        async for partition in result.partitions(batch_size):
            yield [row[0] for row in partition]

    async def compare_crawls(
        self,
        crawl_a_id: uuid.UUID,
        crawl_b_id: uuid.UUID,
        change_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        cte = """
            WITH a AS (
                SELECT url, status_code, title, word_count, response_time_ms, is_indexable
                FROM crawled_urls
                WHERE crawl_id = :crawl_a
            ),
            b AS (
                SELECT url, status_code, title, word_count, response_time_ms, is_indexable
                FROM crawled_urls
                WHERE crawl_id = :crawl_b
            ),
            comparison AS (
                SELECT
                    COALESCE(a.url, b.url) AS url,
                    CASE
                        WHEN a.url IS NULL THEN 'added'
                        WHEN b.url IS NULL THEN 'removed'
                        WHEN a.status_code IS DISTINCT FROM b.status_code
                          OR a.title IS DISTINCT FROM b.title
                          OR a.word_count IS DISTINCT FROM b.word_count
                          OR a.is_indexable IS DISTINCT FROM b.is_indexable
                        THEN 'changed'
                        ELSE 'unchanged'
                    END AS change_type,
                    a.status_code AS a_status_code,
                    a.title AS a_title,
                    a.word_count AS a_word_count,
                    a.response_time_ms AS a_response_time_ms,
                    a.is_indexable AS a_is_indexable,
                    b.status_code AS b_status_code,
                    b.title AS b_title,
                    b.word_count AS b_word_count,
                    b.response_time_ms AS b_response_time_ms,
                    b.is_indexable AS b_is_indexable
                FROM a
                FULL OUTER JOIN b ON a.url = b.url
            )
        """
        if change_type:
            where_clause = "WHERE change_type = :change_type"
        else:
            where_clause = ""

        sql = text(
            cte
            + f"SELECT * FROM comparison {where_clause} ORDER BY change_type, url LIMIT :limit OFFSET :offset"
        )

        count_sql = text("""
            WITH a AS (
                SELECT url, status_code, title, word_count, is_indexable
                FROM crawled_urls
                WHERE crawl_id = :crawl_a
            ),
            b AS (
                SELECT url, status_code, title, word_count, is_indexable
                FROM crawled_urls
                WHERE crawl_id = :crawl_b
            ),
            comparison AS (
                SELECT
                    CASE
                        WHEN a.url IS NULL THEN 'added'
                        WHEN b.url IS NULL THEN 'removed'
                        WHEN a.status_code IS DISTINCT FROM b.status_code
                          OR a.title IS DISTINCT FROM b.title
                          OR a.word_count IS DISTINCT FROM b.word_count
                          OR a.is_indexable IS DISTINCT FROM b.is_indexable
                        THEN 'changed'
                        ELSE 'unchanged'
                    END AS change_type
                FROM a
                FULL OUTER JOIN b ON a.url = b.url
            )
            SELECT change_type, COUNT(*) AS cnt
            FROM comparison
            GROUP BY change_type
        """)

        params: dict[str, Any] = {
            "crawl_a": str(crawl_a_id),
            "crawl_b": str(crawl_b_id),
            "limit": limit,
            "offset": offset,
        }
        if change_type:
            params["change_type"] = change_type

        count_result = await self._session.execute(
            count_sql, {"crawl_a": str(crawl_a_id), "crawl_b": str(crawl_b_id)}
        )
        count_rows = count_result.all()
        counts = {row.change_type: row.cnt for row in count_rows}

        total_a_result = await self._session.execute(
            text("SELECT COUNT(*) FROM crawled_urls WHERE crawl_id = :cid"),
            {"cid": str(crawl_a_id)},
        )
        total_a = total_a_result.scalar_one()

        total_b_result = await self._session.execute(
            text("SELECT COUNT(*) FROM crawled_urls WHERE crawl_id = :cid"),
            {"cid": str(crawl_b_id)},
        )
        total_b = total_b_result.scalar_one()

        summary = {
            "total_urls_a": total_a,
            "total_urls_b": total_b,
            "added": counts.get("added", 0),
            "removed": counts.get("removed", 0),
            "changed": counts.get("changed", 0),
            "unchanged": counts.get("unchanged", 0),
        }

        rows_result = await self._session.execute(sql, params)
        rows = rows_result.all()

        urls = [
            {
                "url": row.url,
                "change_type": row.change_type,
                "a_status_code": row.a_status_code,
                "a_title": row.a_title,
                "a_word_count": row.a_word_count,
                "a_response_time_ms": row.a_response_time_ms,
                "a_is_indexable": row.a_is_indexable,
                "b_status_code": row.b_status_code,
                "b_title": row.b_title,
                "b_word_count": row.b_word_count,
                "b_response_time_ms": row.b_response_time_ms,
                "b_is_indexable": row.b_is_indexable,
            }
            for row in rows
        ]

        if change_type:
            filtered_total = counts.get(change_type, 0)
        else:
            filtered_total = sum(counts.values())

        return {
            "summary": summary,
            "urls": urls,
            "total_count": filtered_total,
        }
