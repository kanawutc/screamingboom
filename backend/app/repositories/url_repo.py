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

    async def get_heading_hierarchy(
        self,
        crawl_id: uuid.UUID,
        limit: int = 200,
    ) -> list[dict]:
        """Get heading hierarchy analysis per page."""
        sql = text("""
            SELECT id, url, h1, h2,
                   seo_data->'heading_sequence' AS heading_sequence
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND content_type LIKE 'text/html%'
              AND status_code BETWEEN 200 AND 299
            ORDER BY url
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        pages = []
        for r in result.all():
            seq = r.heading_sequence if isinstance(r.heading_sequence, list) else []
            # Detect hierarchy issues
            issues = []
            prev_level = 0
            for tag in seq:
                level = int(tag[1]) if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit() else 0
                if level > 0 and prev_level > 0 and level > prev_level + 1:
                    issues.append(f"Skipped from {tag.upper()} after H{prev_level} (jumped {level - prev_level} levels)")
                if level > 0:
                    prev_level = level

            pages.append({
                "url_id": str(r.id),
                "url": r.url,
                "h1": r.h1 or [],
                "h2": r.h2 or [],
                "heading_sequence": seq,
                "heading_count": len(seq),
                "has_hierarchy_issues": len(issues) > 0,
                "issues": issues,
            })
        return pages

    async def get_overview_stats(
        self,
        crawl_id: uuid.UUID,
    ) -> dict:
        """Get comprehensive overview stats for the Overview tab."""
        # Status code distribution
        status_sql = text("""
            SELECT
                CASE
                    WHEN status_code BETWEEN 200 AND 299 THEN '2xx'
                    WHEN status_code BETWEEN 300 AND 399 THEN '3xx'
                    WHEN status_code BETWEEN 400 AND 499 THEN '4xx'
                    WHEN status_code BETWEEN 500 AND 599 THEN '5xx'
                    ELSE 'other'
                END AS group_name,
                COUNT(*) AS cnt
            FROM crawled_urls
            WHERE crawl_id = :crawl_id AND status_code IS NOT NULL
            GROUP BY group_name
            ORDER BY group_name
        """)
        status_result = await self._session.execute(
            status_sql, {"crawl_id": str(crawl_id)}
        )
        status_dist = {r.group_name: r.cnt for r in status_result.all()}

        # Content type distribution
        ct_sql = text("""
            SELECT
                CASE
                    WHEN content_type LIKE 'text/html%' THEN 'HTML'
                    WHEN content_type LIKE '%javascript%' THEN 'JavaScript'
                    WHEN content_type LIKE 'text/css%' THEN 'CSS'
                    WHEN content_type LIKE 'image/%' THEN 'Images'
                    WHEN content_type LIKE '%json%' THEN 'JSON'
                    WHEN content_type LIKE '%xml%' THEN 'XML'
                    WHEN content_type LIKE '%pdf%' THEN 'PDF'
                    WHEN content_type LIKE '%font%' THEN 'Fonts'
                    ELSE 'Other'
                END AS type_name,
                COUNT(*) AS cnt
            FROM crawled_urls
            WHERE crawl_id = :crawl_id AND content_type IS NOT NULL
            GROUP BY type_name
            ORDER BY cnt DESC
        """)
        ct_result = await self._session.execute(
            ct_sql, {"crawl_id": str(crawl_id)}
        )
        content_type_dist = [{"type": r.type_name, "count": r.cnt} for r in ct_result.all()]

        # Indexability
        idx_sql = text("""
            SELECT
                COUNT(*) FILTER (WHERE is_indexable = true) AS indexable,
                COUNT(*) FILTER (WHERE is_indexable = false) AS non_indexable,
                COUNT(*) AS total
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
        """)
        idx_result = await self._session.execute(
            idx_sql, {"crawl_id": str(crawl_id)}
        )
        idx = idx_result.one()

        return {
            "status_code_distribution": status_dist,
            "content_type_distribution": content_type_dist,
            "indexability": {
                "indexable": idx.indexable,
                "non_indexable": idx.non_indexable,
                "total": idx.total,
            },
        }

    async def get_images_audit(
        self,
        crawl_id: uuid.UUID,
        limit: int = 500,
    ) -> dict:
        """Get images audit: pages with images, alt text analysis."""
        sql = text("""
            SELECT id, url, seo_data->'images' AS images
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND seo_data->'images' IS NOT NULL
              AND jsonb_array_length(seo_data->'images') > 0
            ORDER BY jsonb_array_length(seo_data->'images') DESC
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        pages = []
        total_images = 0
        missing_alt = 0
        missing_dimensions = 0
        all_images: list[dict] = []

        for r in result.all():
            imgs = r.images if isinstance(r.images, list) else []
            page_missing_alt = sum(1 for i in imgs if not i.get("alt"))
            page_images = []
            for img in imgs:
                total_images += 1
                has_alt = bool(img.get("alt"))
                has_dims = bool(img.get("width") and img.get("height"))
                if not has_alt:
                    missing_alt += 1
                if not has_dims:
                    missing_dimensions += 1
                entry = {
                    "src": img.get("src", ""),
                    "alt": img.get("alt", ""),
                    "width": img.get("width"),
                    "height": img.get("height"),
                    "has_alt": has_alt,
                    "has_dimensions": has_dims,
                }
                page_images.append(entry)
                all_images.append({**entry, "page_url": r.url})
            pages.append({
                "url_id": str(r.id),
                "url": r.url,
                "image_count": len(imgs),
                "missing_alt_count": page_missing_alt,
                "images": page_images,
            })

        return {
            "summary": {
                "total_images": total_images,
                "pages_with_images": len(pages),
                "missing_alt": missing_alt,
                "missing_dimensions": missing_dimensions,
                "alt_coverage": round((total_images - missing_alt) / total_images * 100, 1) if total_images > 0 else 100,
            },
            "pages": pages,
            "images_missing_alt": [i for i in all_images if not i["has_alt"]][:100],
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

    async def get_crawl_timeline(
        self,
        crawl_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        """Get chronological crawl timeline (most recent first)."""
        base = """
            SELECT id, url, status_code, content_type, response_time_ms,
                   crawl_depth, title, is_indexable, redirect_url, crawled_at
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
        """
        params: dict[str, Any] = {"crawl_id": str(crawl_id), "limit": limit + 1}

        if status_filter == "errors":
            base += " AND (status_code >= 400 OR status_code = 0)"
        elif status_filter == "redirects":
            base += " AND status_code BETWEEN 300 AND 399"
        elif status_filter == "ok":
            base += " AND status_code BETWEEN 200 AND 299"

        if cursor:
            base += " AND crawled_at < :cursor_ts"
            params["cursor_ts"] = cursor

        base += " ORDER BY crawled_at DESC LIMIT :limit"

        result = await self._session.execute(text(base), params)
        rows = list(result.all())

        has_more = len(rows) > limit
        page_items = rows[:limit]
        next_cursor = page_items[-1].crawled_at.isoformat() if has_more and page_items else None

        # Get summary stats
        summary_sql = text("""
            SELECT
                COUNT(*) AS total,
                MIN(crawled_at) AS first_crawled,
                MAX(crawled_at) AS last_crawled,
                COUNT(*) FILTER (WHERE status_code BETWEEN 200 AND 299) AS ok_count,
                COUNT(*) FILTER (WHERE status_code BETWEEN 300 AND 399) AS redirect_count,
                COUNT(*) FILTER (WHERE status_code >= 400 OR status_code = 0) AS error_count,
                AVG(response_time_ms) FILTER (WHERE response_time_ms IS NOT NULL) AS avg_response_ms
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
        """)
        summary_result = await self._session.execute(
            summary_sql, {"crawl_id": str(crawl_id)}
        )
        s = summary_result.one()

        return {
            "items": [
                {
                    "id": str(r.id),
                    "url": r.url,
                    "status_code": r.status_code,
                    "content_type": r.content_type,
                    "response_time_ms": r.response_time_ms,
                    "crawl_depth": r.crawl_depth,
                    "title": r.title,
                    "is_indexable": r.is_indexable,
                    "redirect_url": r.redirect_url,
                    "crawled_at": r.crawled_at.isoformat() if r.crawled_at else None,
                }
                for r in page_items
            ],
            "next_cursor": next_cursor,
            "summary": {
                "total": s.total,
                "first_crawled": s.first_crawled.isoformat() if s.first_crawled else None,
                "last_crawled": s.last_crawled.isoformat() if s.last_crawled else None,
                "ok_count": s.ok_count,
                "redirect_count": s.redirect_count,
                "error_count": s.error_count,
                "avg_response_ms": round(float(s.avg_response_ms), 1) if s.avg_response_ms else None,
            },
        }

    async def get_crawl_speed_chart(
        self,
        crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get URLs crawled per second for speed chart."""
        sql = text("""
            SELECT
                date_trunc('second', crawled_at) AS ts,
                COUNT(*) AS urls_per_second,
                AVG(response_time_ms) AS avg_ms
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
            GROUP BY ts
            ORDER BY ts
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        return [
            {
                "timestamp": r.ts.isoformat(),
                "urls_per_second": r.urls_per_second,
                "avg_ms": round(float(r.avg_ms), 1) if r.avg_ms else None,
            }
            for r in result.all()
        ]

    async def get_quick_wins(
        self,
        crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Generate prioritized SEO quick wins / action items."""
        actions: list[dict[str, Any]] = []

        # 1. Missing titles
        title_sql = text("""
            SELECT COUNT(*) AS cnt FROM url_issues
            WHERE crawl_id = :cid AND issue_type = 'missing_title'
        """)
        r = await self._session.execute(title_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "critical",
                "category": "titles",
                "action": f"Add page titles to {cnt} page{'s' if cnt > 1 else ''}",
                "impact": "high",
                "effort": "low",
                "issue_type": "missing_title",
                "count": cnt,
            })

        # 2. Missing meta descriptions
        meta_sql = text("""
            SELECT COUNT(*) AS cnt FROM url_issues
            WHERE crawl_id = :cid AND issue_type = 'missing_meta_description'
        """)
        r = await self._session.execute(meta_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "critical",
                "category": "meta",
                "action": f"Write meta descriptions for {cnt} page{'s' if cnt > 1 else ''}",
                "impact": "high",
                "effort": "medium",
                "issue_type": "missing_meta_description",
                "count": cnt,
            })

        # 3. Missing H1
        h1_sql = text("""
            SELECT COUNT(*) AS cnt FROM url_issues
            WHERE crawl_id = :cid AND issue_type = 'missing_h1'
        """)
        r = await self._session.execute(h1_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "critical",
                "category": "headings",
                "action": f"Add H1 heading to {cnt} page{'s' if cnt > 1 else ''}",
                "impact": "high",
                "effort": "low",
                "issue_type": "missing_h1",
                "count": cnt,
            })

        # 4. Missing alt text
        img_sql = text("""
            SELECT COUNT(*) AS cnt FROM url_issues
            WHERE crawl_id = :cid AND issue_type = 'missing_alt_text'
        """)
        r = await self._session.execute(img_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "warning",
                "category": "images",
                "action": f"Add alt text to images on {cnt} page{'s' if cnt > 1 else ''}",
                "impact": "medium",
                "effort": "low",
                "issue_type": "missing_alt_text",
                "count": cnt,
            })

        # 5. Slow pages (>1s)
        slow_sql = text("""
            SELECT COUNT(*) AS cnt FROM crawled_urls
            WHERE crawl_id = :cid AND response_time_ms > 1000
              AND status_code BETWEEN 200 AND 299
        """)
        r = await self._session.execute(slow_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "warning",
                "category": "performance",
                "action": f"Optimize {cnt} slow page{'s' if cnt > 1 else ''} (>1s response)",
                "impact": "medium",
                "effort": "high",
                "count": cnt,
            })

        # 6. Long redirect chains
        chain_sql = text("""
            SELECT COUNT(*) AS cnt FROM crawled_urls
            WHERE crawl_id = :cid
              AND redirect_chain IS NOT NULL
              AND jsonb_array_length(redirect_chain) > 2
        """)
        r = await self._session.execute(chain_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "warning",
                "category": "redirects",
                "action": f"Shorten {cnt} redirect chain{'s' if cnt > 1 else ''} (>2 hops)",
                "impact": "medium",
                "effort": "medium",
                "count": cnt,
            })

        # 7. Duplicate titles
        dup_title_sql = text("""
            SELECT COUNT(*) AS cnt FROM url_issues
            WHERE crawl_id = :cid AND issue_type = 'duplicate_title'
        """)
        r = await self._session.execute(dup_title_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "warning",
                "category": "titles",
                "action": f"Make {cnt} duplicate title{'s' if cnt > 1 else ''} unique",
                "impact": "medium",
                "effort": "medium",
                "issue_type": "duplicate_title",
                "count": cnt,
            })

        # 8. Non-indexable pages that should be indexed
        noindex_sql = text("""
            SELECT COUNT(*) AS cnt FROM crawled_urls
            WHERE crawl_id = :cid AND is_indexable = false
              AND status_code BETWEEN 200 AND 299
              AND content_type LIKE 'text/html%%'
        """)
        r = await self._session.execute(noindex_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "info",
                "category": "indexability",
                "action": f"Review {cnt} non-indexable HTML page{'s' if cnt > 1 else ''}",
                "impact": "medium",
                "effort": "low",
                "count": cnt,
            })

        # 9. Missing canonical
        canon_sql = text("""
            SELECT COUNT(*) AS cnt FROM url_issues
            WHERE crawl_id = :cid AND issue_type = 'missing_canonical'
        """)
        r = await self._session.execute(canon_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "info",
                "category": "canonicals",
                "action": f"Add canonical tags to {cnt} page{'s' if cnt > 1 else ''}",
                "impact": "medium",
                "effort": "low",
                "issue_type": "missing_canonical",
                "count": cnt,
            })

        # 10. Thin content (word count < 100)
        thin_sql = text("""
            SELECT COUNT(*) AS cnt FROM crawled_urls
            WHERE crawl_id = :cid AND word_count IS NOT NULL AND word_count < 100
              AND status_code BETWEEN 200 AND 299
              AND content_type LIKE 'text/html%%'
        """)
        r = await self._session.execute(thin_sql, {"cid": str(crawl_id)})
        cnt = r.scalar_one()
        if cnt > 0:
            actions.append({
                "priority": "info",
                "category": "content",
                "action": f"Add content to {cnt} thin page{'s' if cnt > 1 else ''} (<100 words)",
                "impact": "medium",
                "effort": "high",
                "count": cnt,
            })

        # Sort by priority: critical > warning > info, then by count desc
        priority_order = {"critical": 0, "warning": 1, "info": 2}
        actions.sort(key=lambda a: (priority_order.get(a["priority"], 3), -a["count"]))

        return actions

    async def get_top_keywords(
        self,
        crawl_id: uuid.UUID,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Extract top keywords from page titles and H1 headings."""
        import re as _re
        STOP_WORDS = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can", "need",
            "it", "its", "this", "that", "these", "those", "i", "you", "he", "she",
            "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
            "our", "their", "not", "no", "all", "each", "every", "both", "few",
            "more", "most", "some", "any", "other", "such", "than", "too", "very",
            "just", "about", "up", "out", "how", "what", "which", "who", "when",
            "where", "why", "so", "if", "then", "also", "s", "t", "", "|", "-",
        }

        sql = text("""
            SELECT title, h1
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
              AND status_code BETWEEN 200 AND 299
              AND content_type LIKE 'text/html%%'
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        rows = result.all()

        word_freq: dict[str, int] = {}
        for row in rows:
            texts: list[str] = []
            if row.title:
                texts.append(row.title)
            if row.h1 and isinstance(row.h1, list):
                texts.extend(row.h1)
            for text_str in texts:
                words = _re.findall(r'[a-zA-Z0-9\u0E00-\u0E7F]+', text_str.lower())
                for w in words:
                    if w not in STOP_WORDS and len(w) > 1:
                        word_freq[w] = word_freq.get(w, 0) + 1

        # Sort by frequency, take top N
        sorted_words = sorted(word_freq.items(), key=lambda x: -x[1])[:limit]
        max_freq = sorted_words[0][1] if sorted_words else 1

        return {
            "keywords": [
                {
                    "word": w,
                    "count": c,
                    "weight": round(c / max_freq, 3),
                }
                for w, c in sorted_words
            ],
            "total_pages": len(rows),
            "unique_words": len(word_freq),
        }

    async def get_url_segments(
        self,
        crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Auto-detect URL segments by first path directory."""
        sql = text("""
            WITH parsed AS (
                SELECT
                    CASE
                        WHEN position('/' in substring(url from 'https?://[^/]+(/.*)')) > 1
                        THEN '/' || split_part(substring(url from 'https?://[^/]+/([^?#]*)'), '/', 1)
                        ELSE '/'
                    END AS segment,
                    status_code,
                    response_time_ms,
                    is_indexable,
                    word_count
                FROM crawled_urls
                WHERE crawl_id = :crawl_id
            )
            SELECT
                segment,
                COUNT(*) AS url_count,
                COUNT(*) FILTER (WHERE status_code BETWEEN 200 AND 299) AS ok_count,
                COUNT(*) FILTER (WHERE status_code >= 400 OR status_code = 0) AS error_count,
                COUNT(*) FILTER (WHERE status_code BETWEEN 300 AND 399) AS redirect_count,
                COUNT(*) FILTER (WHERE is_indexable = true) AS indexable_count,
                ROUND(AVG(response_time_ms)::numeric, 1) AS avg_response_ms,
                ROUND(AVG(word_count)::numeric, 0) AS avg_word_count
            FROM parsed
            GROUP BY segment
            ORDER BY url_count DESC
        """)
        result = await self._session.execute(sql, {"crawl_id": str(crawl_id)})
        return [
            {
                "segment": r.segment,
                "url_count": r.url_count,
                "ok_count": r.ok_count,
                "error_count": r.error_count,
                "redirect_count": r.redirect_count,
                "indexable_count": r.indexable_count,
                "avg_response_ms": float(r.avg_response_ms) if r.avg_response_ms else None,
                "avg_word_count": int(r.avg_word_count) if r.avg_word_count else None,
                "health_pct": round(r.ok_count / r.url_count * 100, 1) if r.url_count > 0 else 0,
                "index_pct": round(r.indexable_count / r.url_count * 100, 1) if r.url_count > 0 else 0,
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

    async def get_link_graph(
        self, crawl_id: uuid.UUID, max_nodes: int = 200
    ) -> dict[str, Any]:
        """Return nodes and edges for a force-directed link graph."""
        s = self._session

        # Get top pages by inlink count (most connected first)
        nodes_q = text("""
            WITH inlink_counts AS (
                SELECT
                    cu.id,
                    cu.url,
                    cu.status_code,
                    COALESCE(cu.seo_data->>'title', '') AS title,
                    COUNT(DISTINCT pl.source_url_id) AS inlinks,
                    cu.is_indexable
                FROM crawled_urls cu
                LEFT JOIN page_links pl
                    ON pl.crawl_id = cu.crawl_id
                    AND pl.target_url_hash = cu.url_hash
                    AND pl.link_type = 'internal'
                WHERE cu.crawl_id = :crawl_id
                    AND cu.content_type LIKE 'text/html%%'
                GROUP BY cu.id, cu.url, cu.status_code, cu.seo_data, cu.is_indexable
                ORDER BY inlinks DESC
                LIMIT :max_nodes
            )
            SELECT * FROM inlink_counts
        """)
        node_result = await s.execute(nodes_q, {"crawl_id": str(crawl_id), "max_nodes": max_nodes})
        node_rows = node_result.all()

        if not node_rows:
            return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}

        node_ids = {str(r.id) for r in node_rows}
        nodes = []
        for r in node_rows:
            nodes.append({
                "id": str(r.id),
                "url": r.url,
                "title": r.title or "",
                "status_code": r.status_code,
                "inlinks": r.inlinks,
                "is_indexable": r.is_indexable,
            })

        # Get edges between the selected nodes
        edges_q = text("""
            SELECT DISTINCT
                pl.source_url_id::text AS source,
                cu_target.id::text AS target
            FROM page_links pl
            JOIN crawled_urls cu_target
                ON cu_target.crawl_id = pl.crawl_id
                AND cu_target.url_hash = pl.target_url_hash
            WHERE pl.crawl_id = :crawl_id
                AND pl.link_type = 'internal'
                AND pl.source_url_id::text = ANY(:node_ids)
                AND cu_target.id::text = ANY(:node_ids)
                AND pl.source_url_id != cu_target.id
        """)
        edge_result = await s.execute(
            edges_q,
            {"crawl_id": str(crawl_id), "node_ids": list(node_ids)},
        )
        edges = [{"source": r.source, "target": r.target} for r in edge_result.all()]

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        }

    async def get_orphan_pages(
        self, crawl_id: uuid.UUID, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Find HTML pages with zero inlinks (orphan pages)."""
        sql = text("""
            SELECT
                cu.id,
                cu.url,
                cu.status_code,
                COALESCE(cu.seo_data->>'title', '') AS title,
                cu.word_count,
                cu.is_indexable
            FROM crawled_urls cu
            WHERE cu.crawl_id = :crawl_id
                AND cu.content_type LIKE 'text/html%%'
                AND NOT EXISTS (
                    SELECT 1 FROM page_links pl
                    WHERE pl.crawl_id = cu.crawl_id
                        AND pl.target_url_hash = cu.url_hash
                        AND pl.link_type = 'internal'
                        AND pl.source_url_id != cu.id
                )
            ORDER BY cu.url
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
                "title": r.title or "",
                "word_count": r.word_count,
                "is_indexable": r.is_indexable,
            }
            for r in result.all()
        ]

    async def get_content_quality(
        self, crawl_id: uuid.UUID, limit: int = 200
    ) -> dict[str, Any]:
        """Analyze content quality metrics: thin content, word count distribution, readability."""
        s = self._session

        # Word count distribution
        dist_sql = text("""
            SELECT
                CASE
                    WHEN word_count IS NULL OR word_count = 0 THEN 'empty'
                    WHEN word_count < 100 THEN 'thin (<100)'
                    WHEN word_count < 300 THEN 'short (100-300)'
                    WHEN word_count < 1000 THEN 'medium (300-1000)'
                    WHEN word_count < 3000 THEN 'long (1000-3000)'
                    ELSE 'very_long (3000+)'
                END AS bucket,
                COUNT(*) AS count,
                AVG(word_count)::int AS avg_words
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
            GROUP BY bucket
            ORDER BY MIN(COALESCE(word_count, 0))
        """)
        dist_result = await s.execute(dist_sql, {"crawl_id": str(crawl_id)})
        distribution = [
            {"bucket": r.bucket, "count": r.count, "avg_words": r.avg_words}
            for r in dist_result.all()
        ]

        # Thin content pages
        thin_sql = text("""
            SELECT
                id, url, word_count,
                COALESCE(seo_data->>'title', '') AS title,
                status_code, is_indexable
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND (word_count IS NULL OR word_count < 100)
                AND status_code >= 200 AND status_code < 300
            ORDER BY COALESCE(word_count, 0) ASC
            LIMIT :limit
        """)
        thin_result = await s.execute(thin_sql, {"crawl_id": str(crawl_id), "limit": limit})
        thin_pages = [
            {
                "url_id": str(r.id),
                "url": r.url,
                "word_count": r.word_count or 0,
                "title": r.title or "",
                "status_code": r.status_code,
                "is_indexable": r.is_indexable,
            }
            for r in thin_result.all()
        ]

        # Overall stats
        stats_sql = text("""
            SELECT
                COUNT(*) AS total,
                AVG(word_count)::int AS avg_words,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY word_count)::int AS median_words,
                MAX(word_count) AS max_words,
                SUM(CASE WHEN word_count IS NULL OR word_count < 100 THEN 1 ELSE 0 END) AS thin_count
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND status_code >= 200 AND status_code < 300
        """)
        stats_result = await s.execute(stats_sql, {"crawl_id": str(crawl_id)})
        stats_row = stats_result.first()

        return {
            "distribution": distribution,
            "thin_pages": thin_pages,
            "stats": {
                "total_pages": stats_row.total if stats_row else 0,
                "avg_words": stats_row.avg_words if stats_row else 0,
                "median_words": stats_row.median_words if stats_row else 0,
                "max_words": stats_row.max_words if stats_row else 0,
                "thin_count": stats_row.thin_count if stats_row else 0,
            },
        }

    async def get_crawl_depth_analysis(
        self, crawl_id: uuid.UUID
    ) -> dict[str, Any]:
        """Analyze crawl depth distribution and pages per depth level."""
        s = self._session

        sql = text("""
            SELECT
                crawl_depth,
                COUNT(*) AS page_count,
                SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) AS ok_count,
                SUM(CASE WHEN is_indexable THEN 1 ELSE 0 END) AS indexable_count,
                AVG(response_time_ms)::int AS avg_response_ms,
                AVG(word_count)::int AS avg_words
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
            GROUP BY crawl_depth
            ORDER BY crawl_depth
        """)
        result = await s.execute(sql, {"crawl_id": str(crawl_id)})
        levels = [
            {
                "depth": r.crawl_depth,
                "page_count": r.page_count,
                "ok_count": r.ok_count,
                "indexable_count": r.indexable_count,
                "avg_response_ms": r.avg_response_ms or 0,
                "avg_words": r.avg_words or 0,
            }
            for r in result.all()
        ]

        # Pages at each depth with details (limited)
        detail_sql = text("""
            SELECT
                id, url, crawl_depth, status_code,
                COALESCE(seo_data->>'title', '') AS title,
                response_time_ms, word_count, is_indexable
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
            ORDER BY crawl_depth, url
            LIMIT 500
        """)
        detail_result = await s.execute(detail_sql, {"crawl_id": str(crawl_id)})
        pages = [
            {
                "url_id": str(r.id),
                "url": r.url,
                "depth": r.crawl_depth,
                "status_code": r.status_code,
                "title": r.title or "",
                "response_time_ms": r.response_time_ms or 0,
                "word_count": r.word_count or 0,
                "is_indexable": r.is_indexable,
            }
            for r in detail_result.all()
        ]

        total = sum(l["page_count"] for l in levels)
        max_depth = max((l["depth"] for l in levels), default=0)

        return {
            "levels": levels,
            "pages": pages,
            "stats": {
                "total_pages": total,
                "max_depth": max_depth,
                "depth_levels": len(levels),
            },
        }

    async def get_response_time_distribution(
        self, crawl_id: uuid.UUID
    ) -> dict[str, Any]:
        """Get response time distribution for heatmap visualization."""
        s = self._session

        sql = text("""
            SELECT
                CASE
                    WHEN response_time_ms IS NULL THEN 'unknown'
                    WHEN response_time_ms < 100 THEN '<100ms'
                    WHEN response_time_ms < 200 THEN '100-200ms'
                    WHEN response_time_ms < 500 THEN '200-500ms'
                    WHEN response_time_ms < 1000 THEN '500ms-1s'
                    WHEN response_time_ms < 2000 THEN '1-2s'
                    WHEN response_time_ms < 5000 THEN '2-5s'
                    ELSE '5s+'
                END AS bucket,
                COUNT(*) AS count,
                AVG(response_time_ms)::int AS avg_ms,
                MIN(response_time_ms) AS min_ms,
                MAX(response_time_ms) AS max_ms
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
            GROUP BY bucket
            ORDER BY MIN(COALESCE(response_time_ms, 999999))
        """)
        result = await s.execute(sql, {"crawl_id": str(crawl_id)})
        buckets = [
            {
                "bucket": r.bucket,
                "count": r.count,
                "avg_ms": r.avg_ms or 0,
                "min_ms": r.min_ms,
                "max_ms": r.max_ms,
            }
            for r in result.all()
        ]

        # Slowest pages
        slow_sql = text("""
            SELECT
                id, url, response_time_ms, status_code,
                COALESCE(seo_data->>'title', '') AS title
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND response_time_ms IS NOT NULL
            ORDER BY response_time_ms DESC
            LIMIT 20
        """)
        slow_result = await s.execute(slow_sql, {"crawl_id": str(crawl_id)})
        slowest = [
            {
                "url_id": str(r.id),
                "url": r.url,
                "response_time_ms": r.response_time_ms,
                "status_code": r.status_code,
                "title": r.title or "",
            }
            for r in slow_result.all()
        ]

        return {
            "distribution": buckets,
            "slowest_pages": slowest,
        }

    async def get_readability_analysis(
        self, crawl_id: uuid.UUID, limit: int = 200
    ) -> dict[str, Any]:
        """Analyze readability scores, text ratio, and sentence complexity."""
        s = self._session

        stats_sql = text("""
            SELECT
                COUNT(*) AS total,
                AVG((seo_data->>'text_ratio')::float)::numeric(5,2) AS avg_text_ratio,
                AVG((seo_data->>'readability_score')::float)::numeric(5,1) AS avg_readability,
                AVG((seo_data->>'avg_words_per_sentence')::float)::numeric(5,1) AS avg_sentence_len
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND status_code >= 200 AND status_code < 300
                AND seo_data->>'text_ratio' IS NOT NULL
        """)
        stats_result = await s.execute(stats_sql, {"crawl_id": str(crawl_id)})
        sr = stats_result.first()

        # Text ratio distribution
        ratio_sql = text("""
            SELECT
                CASE
                    WHEN (seo_data->>'text_ratio')::float < 0.1 THEN '<10%'
                    WHEN (seo_data->>'text_ratio')::float < 0.2 THEN '10-20%'
                    WHEN (seo_data->>'text_ratio')::float < 0.3 THEN '20-30%'
                    WHEN (seo_data->>'text_ratio')::float < 0.5 THEN '30-50%'
                    ELSE '50%+'
                END AS bucket,
                COUNT(*) AS count
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND status_code >= 200 AND status_code < 300
                AND seo_data->>'text_ratio' IS NOT NULL
            GROUP BY bucket
            ORDER BY MIN((seo_data->>'text_ratio')::float)
        """)
        ratio_result = await s.execute(ratio_sql, {"crawl_id": str(crawl_id)})
        ratio_dist = [{"bucket": r.bucket, "count": r.count} for r in ratio_result.all()]

        # Pages with readability data
        pages_sql = text("""
            SELECT
                id, url,
                COALESCE(seo_data->>'title', '') AS title,
                (seo_data->>'text_ratio')::float AS text_ratio,
                (seo_data->>'readability_score')::float AS readability_score,
                (seo_data->>'avg_words_per_sentence')::float AS avg_sentence_len,
                word_count
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND status_code >= 200 AND status_code < 300
                AND seo_data->>'readability_score' IS NOT NULL
            ORDER BY (seo_data->>'readability_score')::float ASC
            LIMIT :limit
        """)
        pages_result = await s.execute(pages_sql, {"crawl_id": str(crawl_id), "limit": limit})
        pages = [
            {
                "url_id": str(r.id),
                "url": r.url,
                "title": r.title or "",
                "text_ratio": round(float(r.text_ratio or 0), 3),
                "readability_score": round(float(r.readability_score or 0), 1),
                "avg_sentence_len": round(float(r.avg_sentence_len or 0), 1),
                "word_count": r.word_count or 0,
            }
            for r in pages_result.all()
        ]

        return {
            "stats": {
                "total_pages": sr.total if sr else 0,
                "avg_text_ratio": float(sr.avg_text_ratio) if sr and sr.avg_text_ratio else 0,
                "avg_readability": float(sr.avg_readability) if sr and sr.avg_readability else 0,
                "avg_sentence_len": float(sr.avg_sentence_len) if sr and sr.avg_sentence_len else 0,
            },
            "text_ratio_distribution": ratio_dist,
            "pages": pages,
        }

    async def get_og_audit(
        self, crawl_id: uuid.UUID, limit: int = 200
    ) -> dict[str, Any]:
        """Audit Open Graph and social media meta tags."""
        s = self._session

        sql = text("""
            SELECT
                id, url,
                COALESCE(seo_data->>'title', '') AS title,
                seo_data->'og' AS og_data,
                CASE WHEN seo_data->'og' IS NOT NULL AND seo_data->'og' != 'null'::jsonb THEN true ELSE false END AS has_og
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND status_code >= 200 AND status_code < 300
            ORDER BY url
            LIMIT :limit
        """)
        result = await s.execute(sql, {"crawl_id": str(crawl_id), "limit": limit})
        rows = result.all()

        pages = []
        has_og_count = 0
        missing_og_title = 0
        missing_og_desc = 0
        missing_og_image = 0

        for r in rows:
            og = r.og_data if isinstance(r.og_data, dict) else {}
            has_og = bool(og)
            if has_og:
                has_og_count += 1
            if not og.get("og:title"):
                missing_og_title += 1
            if not og.get("og:description"):
                missing_og_desc += 1
            if not og.get("og:image"):
                missing_og_image += 1

            pages.append({
                "url_id": str(r.id),
                "url": r.url,
                "title": r.title or "",
                "has_og": has_og,
                "og_title": og.get("og:title", ""),
                "og_description": og.get("og:description", ""),
                "og_image": og.get("og:image", ""),
                "og_type": og.get("og:type", ""),
            })

        total = len(rows)
        return {
            "stats": {
                "total_pages": total,
                "has_og": has_og_count,
                "missing_og": total - has_og_count,
                "missing_og_title": missing_og_title,
                "missing_og_description": missing_og_desc,
                "missing_og_image": missing_og_image,
            },
            "pages": pages,
        }

    async def get_resources_audit(
        self, crawl_id: uuid.UUID, limit: int = 300
    ) -> dict[str, Any]:
        """Audit JS, CSS, and other non-HTML resources."""
        s = self._session

        # Resource type breakdown
        type_sql = text("""
            SELECT
                CASE
                    WHEN content_type LIKE '%%javascript%%' THEN 'JavaScript'
                    WHEN content_type LIKE '%%css%%' THEN 'CSS'
                    WHEN content_type LIKE '%%image/%%' THEN 'Image'
                    WHEN content_type LIKE '%%font%%' OR content_type LIKE '%%woff%%' THEN 'Font'
                    WHEN content_type LIKE '%%pdf%%' THEN 'PDF'
                    WHEN content_type LIKE '%%json%%' THEN 'JSON'
                    WHEN content_type LIKE '%%xml%%' THEN 'XML'
                    WHEN content_type LIKE '%%text/html%%' THEN 'HTML'
                    ELSE 'Other'
                END AS resource_type,
                COUNT(*) AS count,
                SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) AS ok_count,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS error_count,
                AVG(response_time_ms)::int AS avg_response_ms
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
            GROUP BY resource_type
            ORDER BY count DESC
        """)
        type_result = await s.execute(type_sql, {"crawl_id": str(crawl_id)})
        types = [
            {
                "type": r.resource_type,
                "count": r.count,
                "ok_count": r.ok_count,
                "error_count": r.error_count,
                "avg_response_ms": r.avg_response_ms or 0,
            }
            for r in type_result.all()
        ]

        # Non-HTML resources list
        resources_sql = text("""
            SELECT
                id, url, content_type, status_code, response_time_ms
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type NOT LIKE 'text/html%%'
            ORDER BY
                CASE
                    WHEN status_code >= 400 THEN 0
                    ELSE 1
                END,
                response_time_ms DESC NULLS LAST
            LIMIT :limit
        """)
        resources_result = await s.execute(
            resources_sql, {"crawl_id": str(crawl_id), "limit": limit}
        )
        resources = [
            {
                "url_id": str(r.id),
                "url": r.url,
                "content_type": r.content_type or "unknown",
                "status_code": r.status_code,
                "response_time_ms": r.response_time_ms or 0,
            }
            for r in resources_result.all()
        ]

        return {"types": types, "resources": resources}

    async def get_mobile_audit(
        self, crawl_id: uuid.UUID, limit: int = 200
    ) -> dict[str, Any]:
        """Audit mobile-friendliness: viewport meta, responsive indicators."""
        s = self._session

        # Check viewport meta tag presence from seo_data
        sql = text("""
            SELECT
                id, url,
                COALESCE(seo_data->>'title', '') AS title,
                seo_data->>'viewport' AS viewport,
                CASE WHEN seo_data->>'viewport' IS NOT NULL
                     AND seo_data->>'viewport' != '' THEN true ELSE false END AS has_viewport,
                CASE WHEN seo_data->>'viewport' LIKE '%%width=device-width%%' THEN true ELSE false END AS responsive_viewport,
                word_count,
                is_indexable
            FROM crawled_urls
            WHERE crawl_id = :crawl_id
                AND content_type LIKE 'text/html%%'
                AND status_code >= 200 AND status_code < 300
            ORDER BY url
            LIMIT :limit
        """)
        result = await s.execute(sql, {"crawl_id": str(crawl_id), "limit": limit})
        rows = result.all()

        pages = []
        has_viewport_count = 0
        responsive_count = 0
        for r in rows:
            if r.has_viewport:
                has_viewport_count += 1
            if r.responsive_viewport:
                responsive_count += 1
            pages.append({
                "url_id": str(r.id),
                "url": r.url,
                "title": r.title or "",
                "viewport": r.viewport or "",
                "has_viewport": r.has_viewport,
                "responsive_viewport": r.responsive_viewport,
                "word_count": r.word_count or 0,
                "is_indexable": r.is_indexable,
            })

        total = len(rows)
        return {
            "stats": {
                "total_pages": total,
                "has_viewport": has_viewport_count,
                "responsive_viewport": responsive_count,
                "missing_viewport": total - has_viewport_count,
            },
            "pages": pages,
        }
