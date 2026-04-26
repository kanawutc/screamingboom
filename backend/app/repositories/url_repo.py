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
            if content_type == "other":
                # "Other" means NOT html, javascript, css, or image
                query = query.where(
                    ~CrawledUrl.content_type.ilike("%text/html%"),
                    ~CrawledUrl.content_type.ilike("%javascript%"),
                    ~CrawledUrl.content_type.ilike("%css%"),
                    ~CrawledUrl.content_type.ilike("%image/%"),
                    CrawledUrl.content_type.isnot(None),
                )
            else:
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

    async def list_pagination_urls(
        self,
        crawl_id: uuid.UUID,
        filter_type: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List URLs with pagination attributes (rel=next/prev).

        Filter types:
        - contains: has any pagination attribute
        - first_page: has rel_next but no rel_prev
        - paginated_2_plus: has rel_prev
        - url_not_in_anchor: issue filter
        - non_200: issue filter
        - unlinked: issue filter
        - non_indexable: issue filter
        - multiple: issue filter
        - loop: issue filter
        - sequence_error: issue filter
        """
        # Issue-based filters map to specific issue types
        _issue_filters = {
            "url_not_in_anchor": "pagination_url_not_in_anchor",
            "non_200": "non_200_pagination_url",
            "unlinked": "unlinked_pagination_url",
            "non_indexable": "non_indexable_paginated",
            "multiple": "multiple_pagination_urls",
            "loop": "pagination_loop",
            "sequence_error": "pagination_sequence_error",
        }

        query = select(CrawledUrl).where(
            CrawledUrl.crawl_id == crawl_id,
            text("seo_data ? 'pagination'"),
        )

        if filter_type == "first_page":
            query = query.where(
                text("seo_data->'pagination'->>'rel_next' IS NOT NULL"),
                text("(seo_data->'pagination'->>'rel_prev' IS NULL)"),
            )
        elif filter_type == "paginated_2_plus":
            query = query.where(
                text("seo_data->'pagination'->>'rel_prev' IS NOT NULL"),
            )
        elif filter_type in _issue_filters:
            issue_type = _issue_filters[filter_type]
            issue_subquery = (
                select(UrlIssue.url_id)
                .where(
                    UrlIssue.crawl_id == crawl_id,
                    UrlIssue.issue_type == issue_type,
                )
                .distinct()
                .scalar_subquery()
            )
            query = query.where(CrawledUrl.id.in_(issue_subquery))

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

    # ------------------------------------------------------------------
    # Links Analysis (F2.10)
    # ------------------------------------------------------------------

    async def get_inlink_counts(
        self,
        crawl_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get pages ranked by inlink count."""
        sql = text("""
            SELECT cu.id, cu.url, cu.title, cu.crawl_depth, cu.status_code,
                   COUNT(pl.id) AS inlink_count
            FROM crawled_urls cu
            LEFT JOIN page_links pl
              ON pl.crawl_id = cu.crawl_id
              AND pl.target_url_hash = cu.url_hash
              AND pl.link_type = 'internal'
            WHERE cu.crawl_id = :crawl_id
            GROUP BY cu.id, cu.url, cu.title, cu.crawl_depth, cu.status_code, cu.crawl_id
            ORDER BY inlink_count DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit, "offset": offset}
        )
        return [
            {
                "id": str(r.id),
                "url": r.url,
                "title": r.title,
                "crawl_depth": r.crawl_depth,
                "status_code": r.status_code,
                "inlink_count": r.inlink_count,
            }
            for r in result.all()
        ]

    async def get_orphan_pages(
        self,
        crawl_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get pages with zero internal inlinks (excluding start URL)."""
        sql = text("""
            SELECT cu.id, cu.url, cu.title, cu.crawl_depth, cu.status_code
            FROM crawled_urls cu
            WHERE cu.crawl_id = :crawl_id
              AND cu.crawl_depth > 0
              AND NOT EXISTS (
                SELECT 1 FROM page_links pl
                WHERE pl.crawl_id = cu.crawl_id
                  AND pl.target_url_hash = cu.url_hash
                  AND pl.link_type = 'internal'
              )
            ORDER BY cu.url
            LIMIT :limit OFFSET :offset
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit, "offset": offset}
        )
        return [
            {
                "id": str(r.id),
                "url": r.url,
                "title": r.title,
                "crawl_depth": r.crawl_depth,
                "status_code": r.status_code,
            }
            for r in result.all()
        ]

    async def get_depth_distribution(
        self,
        crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get URL count per crawl depth level."""
        sql = text("""
            SELECT crawl_depth, COUNT(*) AS url_count
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
            GROUP BY crawl_depth
            ORDER BY crawl_depth
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        return [
            {"crawl_depth": r.crawl_depth, "url_count": r.url_count}
            for r in result.all()
        ]

    async def get_anchor_text_stats(
        self,
        crawl_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get top anchor texts by frequency for internal links."""
        sql = text("""
            SELECT anchor_text, COUNT(*) AS frequency
            FROM page_links
            WHERE crawl_id = :crawl_id
              AND link_type = 'internal'
              AND anchor_text IS NOT NULL
              AND anchor_text != ''
            GROUP BY anchor_text
            ORDER BY frequency DESC
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {"anchor_text": r.anchor_text, "frequency": r.frequency}
            for r in result.all()
        ]

    # ------------------------------------------------------------------
    # Duplicate Content Detection (F2.12)
    # ------------------------------------------------------------------

    async def get_exact_duplicate_groups(
        self,
        crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Group URLs by identical content_hash (exact duplicates)."""
        sql = text("""
            SELECT content_hash, array_agg(url) AS urls,
                   array_agg(id::text) AS url_ids,
                   array_agg(title) AS titles,
                   COUNT(*) AS count
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND content_hash IS NOT NULL
              AND status_code = 200
            GROUP BY content_hash
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 50
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        return [
            {
                "urls": r.urls,
                "url_ids": r.url_ids,
                "titles": r.titles,
                "count": r.count,
            }
            for r in result.all()
        ]

    async def get_near_duplicate_groups(
        self,
        crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Find near-duplicate pages using SimHash from seo_data."""
        from app.analysis.simhash import find_clusters

        sql = text("""
            SELECT id, url, title, (seo_data->>'simhash')::bigint AS simhash
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND seo_data->>'simhash' IS NOT NULL
              AND status_code = 200
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        rows = result.all()

        url_map = {str(r.id): {"url": r.url, "title": r.title} for r in rows}
        hashes = [(str(r.id), r.simhash) for r in rows if r.simhash]

        clusters = find_clusters(hashes, threshold=3)

        groups = []
        for cluster_ids in clusters:
            group_urls = []
            for uid in cluster_ids:
                info = url_map.get(uid, {})
                group_urls.append({
                    "id": uid,
                    "url": info.get("url", ""),
                    "title": info.get("title", ""),
                })
            groups.append({
                "urls": group_urls,
                "count": len(group_urls),
            })
        groups.sort(key=lambda g: g["count"], reverse=True)
        return groups[:50]

    # ------------------------------------------------------------------
    # Content Analysis (F2.11)
    # ------------------------------------------------------------------

    async def get_content_analysis(
        self,
        crawl_id: uuid.UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get content analysis metrics sorted by readability score."""
        sql = text("""
            SELECT id, url, title, word_count,
                   (seo_data->>'text_ratio')::float AS text_ratio,
                   (seo_data->>'readability_score')::float AS readability_score,
                   (seo_data->>'avg_words_per_sentence')::float AS avg_words_per_sentence
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND content_type LIKE 'text/html%'
              AND status_code = 200
            ORDER BY word_count DESC
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {
                "id": str(r.id),
                "url": r.url,
                "title": r.title,
                "word_count": r.word_count,
                "text_ratio": r.text_ratio,
                "readability_score": r.readability_score,
                "avg_words_per_sentence": r.avg_words_per_sentence,
            }
            for r in result.all()
        ]

    # ------------------------------------------------------------------
    # Link Score (F3.6)
    # ------------------------------------------------------------------

    async def get_link_scores(
        self,
        crawl_id: uuid.UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get URLs ranked by Link Score (descending)."""
        sql = text("""
            SELECT id, url, title, crawl_depth, status_code, word_count,
                   (seo_data->>'link_score')::int AS link_score
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND seo_data->>'link_score' IS NOT NULL
            ORDER BY (seo_data->>'link_score')::int DESC
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {
                "id": str(r.id),
                "url": r.url,
                "title": r.title,
                "crawl_depth": r.crawl_depth,
                "status_code": r.status_code,
                "word_count": r.word_count,
                "link_score": r.link_score,
            }
            for r in result.all()
        ]

    async def get_cookies_audit(
        self,
        crawl_id: uuid.UUID,
        limit: int = 200,
    ) -> list[dict]:
        """Get pages that set cookies with their cookie details."""
        sql = text("""
            SELECT id, url, seo_data->'cookies' AS cookies
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND seo_data->'cookies' IS NOT NULL
              AND jsonb_array_length(seo_data->'cookies') > 0
            ORDER BY jsonb_array_length(seo_data->'cookies') DESC
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {
                "url_id": str(r.id),
                "url": r.url,
                "cookies": r.cookies,
            }
            for r in result.all()
        ]

    async def get_security_overview(
        self,
        crawl_id: uuid.UUID,
    ) -> dict:
        """Get security overview: HTTPS adoption, header coverage."""
        protocol_sql = text("""
            SELECT
                COUNT(*) FILTER (WHERE url LIKE 'https://%%') AS https_count,
                COUNT(*) FILTER (WHERE url LIKE 'http://%%') AS http_count,
                COUNT(*) AS total
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND status_code BETWEEN 200 AND 299
        """)
        protocol_result = await self._session.execute(
            protocol_sql, {"crawl_id": str(crawl_id)}
        )
        proto = protocol_result.one()

        header_sql = text("""
            SELECT issue_type, COUNT(*) AS cnt
            FROM url_issues
            WHERE crawl_id = :crawl_id
              AND issue_type IN (
                'missing_hsts', 'missing_csp',
                'missing_x_content_type_options', 'missing_x_frame_options',
                'http_url', 'mixed_content'
              )
            GROUP BY issue_type
        """)
        header_result = await self._session.execute(
            header_sql, {"crawl_id": str(crawl_id)}
        )
        header_counts = {r.issue_type: r.cnt for r in header_result.all()}

        return {
            "https_count": proto.https_count,
            "http_count": proto.http_count,
            "total_pages": proto.total,
            "issue_counts": header_counts,
        }

    async def get_redirect_chains(
        self,
        crawl_id: uuid.UUID,
        limit: int = 200,
    ) -> list[dict]:
        """Get pages with redirect chains."""
        sql = text("""
            SELECT id, url, status_code, redirect_url, redirect_chain
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND redirect_url IS NOT NULL
            ORDER BY
                jsonb_array_length(COALESCE(redirect_chain, '[]'::jsonb)) DESC,
                url
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {
                "url_id": str(r.id),
                "url": r.url,
                "status_code": r.status_code,
                "redirect_url": r.redirect_url,
                "chain": r.redirect_chain or [],
                "chain_length": len(r.redirect_chain) if r.redirect_chain else 1,
            }
            for r in result.all()
        ]

    async def get_health_score(
        self,
        crawl_id: uuid.UUID,
    ) -> dict:
        """Calculate SEO health score (0-100) based on crawl metrics."""
        sql = text("""
            SELECT
                COUNT(*) AS total_urls,
                COUNT(*) FILTER (WHERE status_code BETWEEN 200 AND 299) AS ok_urls,
                COUNT(*) FILTER (WHERE status_code BETWEEN 300 AND 399) AS redirect_urls,
                COUNT(*) FILTER (WHERE status_code >= 400) AS error_urls,
                COUNT(*) FILTER (WHERE is_indexable = true) AS indexable_urls,
                AVG(response_time_ms) FILTER (WHERE response_time_ms IS NOT NULL) AS avg_response_ms,
                COUNT(*) FILTER (WHERE response_time_ms > 1000) AS slow_urls
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        row = result.one()

        issues_sql = text("""
            SELECT
                COUNT(*) FILTER (WHERE severity = 'critical') AS critical,
                COUNT(*) FILTER (WHERE severity = 'warning') AS warnings,
                COUNT(*) AS total_issues
            FROM url_issues
            WHERE crawl_id = :crawl_id
        """)
        issues_result = await self._session.execute(issues_sql, {"crawl_id": str(crawl_id)})
        issues = issues_result.one()

        total = row.total_urls or 1

        # Score components (each 0-100, weighted)
        # 1. Status code health (30%): % of 200 OK pages
        status_score = float(row.ok_urls / total) * 100

        # 2. Indexability (20%): % of indexable pages out of OK pages
        ok = row.ok_urls or 1
        index_score = float(row.indexable_urls / ok) * 100

        # 3. Issue density (30%): fewer critical/warning issues = better
        critical_penalty = min(issues.critical * 5, 50)
        warning_penalty = min(issues.warnings * 1, 30)
        issue_score = float(max(100 - critical_penalty - warning_penalty, 0))

        # 4. Performance (20%): fast = good
        avg_ms = float(row.avg_response_ms or 500)
        if avg_ms < 300:
            perf_score = 100
        elif avg_ms < 1000:
            perf_score = 100 - ((avg_ms - 300) / 700) * 50
        elif avg_ms < 3000:
            perf_score = 50 - ((avg_ms - 1000) / 2000) * 40
        else:
            perf_score = 10

        # Weighted average
        health = (
            status_score * 0.30
            + index_score * 0.20
            + issue_score * 0.30
            + perf_score * 0.20
        )
        health = round(min(max(health, 0), 100), 1)

        return {
            "score": health,
            "grade": "A" if health >= 90 else "B" if health >= 75 else "C" if health >= 60 else "D" if health >= 40 else "F",
            "components": {
                "status_codes": round(status_score, 1),
                "indexability": round(index_score, 1),
                "issues": round(issue_score, 1),
                "performance": round(perf_score, 1),
            },
            "metrics": {
                "total_urls": total,
                "ok_urls": row.ok_urls,
                "error_urls": row.error_urls,
                "redirect_urls": row.redirect_urls,
                "indexable_urls": row.indexable_urls,
                "critical_issues": issues.critical,
                "warning_issues": issues.warnings,
                "avg_response_ms": round(avg_ms, 1),
            },
        }

    async def get_performance_stats(
        self,
        crawl_id: uuid.UUID,
        limit: int = 100,
    ) -> dict:
        """Get performance analysis: response time stats, slow pages."""
        stats_sql = text("""
            SELECT
                COUNT(*) AS total,
                AVG(response_time_ms) AS avg_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) AS p50_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) AS p95_ms,
                MIN(response_time_ms) AS min_ms,
                MAX(response_time_ms) AS max_ms,
                COUNT(*) FILTER (WHERE response_time_ms > 1000) AS slow_count,
                COUNT(*) FILTER (WHERE response_time_ms > 3000) AS very_slow_count
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND response_time_ms IS NOT NULL
              AND status_code BETWEEN 200 AND 299
        """)
        stats_result = await self._session.execute(
            stats_sql, {"crawl_id": str(crawl_id)}
        )
        row = stats_result.one()

        # Distribution buckets
        dist_sql = text("""
            SELECT
                CASE
                    WHEN response_time_ms < 200 THEN '<200ms'
                    WHEN response_time_ms < 500 THEN '200-500ms'
                    WHEN response_time_ms < 1000 THEN '500ms-1s'
                    WHEN response_time_ms < 3000 THEN '1-3s'
                    ELSE '>3s'
                END AS bucket,
                COUNT(*) AS cnt
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND response_time_ms IS NOT NULL
              AND status_code BETWEEN 200 AND 299
            GROUP BY bucket
            ORDER BY MIN(response_time_ms)
        """)
        dist_result = await self._session.execute(
            dist_sql, {"crawl_id": str(crawl_id)}
        )
        distribution = [{"bucket": r.bucket, "count": r.cnt} for r in dist_result.all()]

        # Slowest pages
        slow_sql = text("""
            SELECT id, url, response_time_ms, status_code, content_type
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND response_time_ms IS NOT NULL
            ORDER BY response_time_ms DESC
            LIMIT :limit
        """)
        slow_result = await self._session.execute(
            slow_sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        slowest = [
            {
                "url_id": str(r.id),
                "url": r.url,
                "response_time_ms": r.response_time_ms,
                "status_code": r.status_code,
                "content_type": r.content_type,
            }
            for r in slow_result.all()
        ]

        return {
            "stats": {
                "total": row.total,
                "avg_ms": round(row.avg_ms, 1) if row.avg_ms else None,
                "p50_ms": round(row.p50_ms, 1) if row.p50_ms else None,
                "p95_ms": round(row.p95_ms, 1) if row.p95_ms else None,
                "min_ms": row.min_ms,
                "max_ms": row.max_ms,
                "slow_count": row.slow_count,
                "very_slow_count": row.very_slow_count,
            },
            "distribution": distribution,
            "slowest_pages": slowest,
        }

    async def get_site_structure(
        self,
        crawl_id: uuid.UUID,
        limit: int = 500,
    ) -> list[dict]:
        """Get URL paths for site structure tree."""
        sql = text("""
            SELECT id, url, status_code, crawl_depth, content_type
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
            ORDER BY url
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {
                "id": str(r.id),
                "url": r.url,
                "status_code": r.status_code,
                "crawl_depth": r.crawl_depth,
                "content_type": r.content_type,
            }
            for r in result.all()
        ]

    async def get_hreflang_data(
        self,
        crawl_id: uuid.UUID,
        limit: int = 200,
    ) -> list[dict]:
        """Get pages with hreflang tags."""
        sql = text("""
            SELECT id, url, seo_data->'hreflang' AS hreflang
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND seo_data->'hreflang' IS NOT NULL
              AND jsonb_array_length(seo_data->'hreflang') > 0
            ORDER BY url
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        return [
            {
                "url_id": str(r.id),
                "url": r.url,
                "hreflang": r.hreflang,
            }
            for r in result.all()
        ]
