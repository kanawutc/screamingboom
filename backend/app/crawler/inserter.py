"""Batch Inserter: high-throughput DB writes via asyncpg COPY protocol.

Buffers crawled URL data, page links, and redirects in memory, then flushes
to PostgreSQL using COPY (50k rows/sec) with fallback to individual INSERTs
for error isolation.
"""

import asyncio
import time
import uuid
from typing import Any

import asyncpg
import structlog

from app.crawler.parser import LinkData, PageData
from app.crawler.fetcher import FetchResult
from app.crawler.utils import url_hash, normalize_url
from app.analysis.pixel_width import calculate_pixel_width

logger = structlog.get_logger(__name__)

# Buffer thresholds
_MAX_BUFFER_SIZE = 500
_FLUSH_INTERVAL_SECONDS = 2.0


class BatchInserter:
    """Manages bulk DB writes for crawl results.

    Accumulates rows in memory buffers and flushes them to PostgreSQL
    using asyncpg COPY protocol for maximum throughput.

    Usage::

        inserter = BatchInserter(pool=asyncpg_pool)
        inserter.add_url(crawl_id, page_data, fetch_result)
        inserter.add_links(crawl_id, source_url_id, links)
        await inserter.flush()
        await inserter.close()
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._url_buffer: list[tuple] = []
        self._link_buffer: list[tuple] = []
        self._redirect_buffer: list[tuple] = []
        self._issue_buffer: list[tuple] = []
        self._last_flush_time: float = time.monotonic()
        self._total_flushed_urls: int = 0
        self._total_flushed_links: int = 0
        self._total_flushed_redirects: int = 0
        self._total_flushed_issues: int = 0
        self._total_errors: int = 0

    @property
    def buffer_size(self) -> int:
        """Total items buffered across all tables."""
        return (
            len(self._url_buffer)
            + len(self._link_buffer)
            + len(self._redirect_buffer)
            + len(self._issue_buffer)
        )

    @property
    def needs_flush(self) -> bool:
        """True if buffer exceeds size threshold or time threshold."""
        if len(self._url_buffer) >= _MAX_BUFFER_SIZE:
            return True
        elapsed = time.monotonic() - self._last_flush_time
        return elapsed >= _FLUSH_INTERVAL_SECONDS and self.buffer_size > 0

    def add_url(
        self,
        crawl_id: uuid.UUID,
        page_data: PageData,
        fetch_result: FetchResult,
        crawl_depth: int = 0,
    ) -> uuid.UUID:
        """Buffer one crawled URL record. Returns the pre-generated UUID."""
        url_id = uuid.uuid4()

        # Build seo_data JSON with OG tags, structured data, etc.
        seo_data: dict[str, Any] = {}
        if page_data.og_tags:
            seo_data["og"] = page_data.og_tags
        if page_data.structured_data_blocks:
            seo_data["json_ld"] = page_data.structured_data_blocks
        if page_data.hreflang_tags:
            seo_data["hreflang"] = [
                {"lang": h.hreflang, "href": h.href} for h in page_data.hreflang_tags
            ]

        # Sprint 2: Store images in seo_data
        if page_data.images:
            seo_data["images"] = [
                {
                    "src": img.src,
                    "alt": img.alt,
                    "width": img.width,
                    "height": img.height,
                }
                for img in page_data.images
            ]

        # Sprint 2: Heading sequence for hierarchy validation
        if page_data.heading_sequence:
            seo_data["heading_sequence"] = page_data.heading_sequence

        # Sprint 2: Tag counts for multi-tag detection
        seo_data["title_count"] = page_data.title_count
        seo_data["meta_desc_count"] = page_data.meta_desc_count
        seo_data["canonical_count"] = page_data.canonical_count
        seo_data["robots_meta_tag_count"] = page_data.robots_meta_tag_count

        # Sprint 2: Mixed content URLs
        if page_data.mixed_content_urls:
            seo_data["mixed_content_urls"] = page_data.mixed_content_urls

        # Phase 3E: Custom extraction results
        if page_data.custom_extractions:
            seo_data["custom_extractions"] = page_data.custom_extractions

        # Pagination attributes (rel=next/prev)
        if page_data.pagination:
            seo_data["pagination"] = {
                "rel_next": page_data.pagination.rel_next,
                "rel_prev": page_data.pagination.rel_prev,
                "next_count": page_data.pagination_count.get("next", 0),
                "prev_count": page_data.pagination_count.get("prev", 0),
            }

        # Sprint 2: Security headers from response
        # Lowercase keys for case-insensitive lookup (HTTP headers are case-insensitive per RFC 7230)
        headers = {k.lower(): v for k, v in (fetch_result.headers or {}).items()}
        seo_data["security_headers"] = {
            "strict_transport_security": headers.get("strict-transport-security"),
            "content_security_policy": headers.get("content-security-policy"),
            "x_frame_options": headers.get("x-frame-options"),
            "x_content_type_options": headers.get("x-content-type-options"),
            "referrer_policy": headers.get("referrer-policy"),
        }

        # Sprint 2: X-Robots-Tag raw header value
        x_robots = headers.get("x-robots-tag")
        if x_robots:
            seo_data["x_robots_tag"] = x_robots

        redirect_chain = fetch_result.redirect_chain if fetch_result.redirect_chain else []

        # Sprint 2: Compute title pixel width
        title_pixel_width = None
        if page_data.title:
            title_pixel_width = calculate_pixel_width(page_data.title)

        # Tuple matching crawled_urls column order
        row = (
            url_id,  # id
            crawl_id,  # crawl_id
            fetch_result.final_url,  # url
            url_hash(fetch_result.final_url),  # url_hash
            fetch_result.status_code or None,  # status_code
            fetch_result.content_type[:100] if fetch_result.content_type else None,  # content_type
            fetch_result.final_url if fetch_result.is_redirect else None,  # redirect_url
            _json_dumps(redirect_chain),  # redirect_chain (JSONB)
            fetch_result.response_time_ms,  # response_time_ms
            page_data.title,  # title
            page_data.title_length,  # title_length
            title_pixel_width,  # title_pixel_width
            page_data.meta_description,  # meta_description
            page_data.meta_desc_length,  # meta_desc_length
            page_data.h1 if page_data.h1 else None,  # h1 (TEXT[])
            page_data.h2 if page_data.h2 else None,  # h2 (TEXT[])
            page_data.canonical_url,  # canonical_url
            page_data.robots_meta if page_data.robots_meta else None,  # robots_meta (TEXT[])
            page_data.is_indexable,  # is_indexable
            page_data.indexability_reason,  # indexability_reason
            page_data.word_count,  # word_count
            page_data.content_hash if page_data.content_hash else None,  # content_hash
            crawl_depth,  # crawl_depth
            _json_dumps(seo_data),  # seo_data (JSONB)
        )

        self._url_buffer.append(row)
        return url_id

    def add_links(
        self,
        crawl_id: uuid.UUID,
        source_url_id: uuid.UUID,
        links: list[LinkData],
    ) -> None:
        """Buffer page link records."""
        for link in links:
            normalized = normalize_url(link.url)
            if not normalized:
                continue
            target_hash = url_hash(normalized)

            row = (
                crawl_id,  # crawl_id
                source_url_id,  # source_url_id
                normalized,  # target_url
                target_hash,  # target_url_hash
                link.anchor_text[:500] if link.anchor_text else None,  # anchor_text
                link.link_type,  # link_type
                link.rel_attrs if link.rel_attrs else None,  # rel_attrs (TEXT[])
                None,  # link_position (Sprint 2)
                False,  # is_javascript (Sprint 4)
            )
            self._link_buffer.append(row)

    def add_redirects(
        self,
        crawl_id: uuid.UUID,
        chain: list[dict[str, object]],
        final_url: str | None = None,
    ) -> None:
        """Buffer redirect hop records from a fetch result's redirect_chain."""
        if not chain or len(chain) < 1:
            return

        chain_id = uuid.uuid4()
        for hop_num, hop in enumerate(chain, start=1):
            source_url = str(hop.get("url", ""))
            status_code = int(hop.get("status_code", 0))

            # Target is the next hop's URL, or final URL for last hop
            if hop_num < len(chain):
                target_url = str(chain[hop_num].get("url", ""))
            elif final_url:
                target_url = final_url
            else:
                continue

            row = (
                crawl_id,  # crawl_id
                chain_id,  # chain_id
                source_url,  # source_url
                target_url,  # target_url
                status_code,  # status_code
                hop_num,  # hop_number
            )
            self._redirect_buffer.append(row)

    def add_issues(
        self,
        issues: list[tuple],
    ) -> None:
        """Buffer issue records for batch insert into url_issues.

        Each tuple: (id, crawl_id, url_id, issue_type, severity, category, details_json)
        """
        self._issue_buffer.extend(issues)

    async def flush(self) -> dict[str, int]:
        """Flush all buffers to the database.

        Returns dict with counts of flushed rows per table.
        """
        results = {"urls": 0, "links": 0, "redirects": 0, "issues": 0, "errors": 0}

        async with self._pool.acquire() as conn:
            # Flush URLs
            if self._url_buffer:
                flushed, errors = await self._flush_urls(conn, list(self._url_buffer))
                results["urls"] = flushed
                results["errors"] += errors
                self._total_flushed_urls += flushed
                self._url_buffer.clear()

            # Flush Links
            if self._link_buffer:
                flushed, errors = await self._flush_links(conn, list(self._link_buffer))
                results["links"] = flushed
                results["errors"] += errors
                self._total_flushed_links += flushed
                self._link_buffer.clear()

            # Flush Redirects
            if self._redirect_buffer:
                flushed, errors = await self._flush_redirects(conn, list(self._redirect_buffer))
                results["redirects"] = flushed
                results["errors"] += errors
                self._total_flushed_redirects += flushed
                self._redirect_buffer.clear()

            # Flush Issues
            if self._issue_buffer:
                flushed, errors = await self._flush_issues(conn, list(self._issue_buffer))
                results["issues"] = flushed
                results["errors"] += errors
                self._total_flushed_issues += flushed
                self._issue_buffer.clear()

        self._total_errors += results["errors"]
        self._last_flush_time = time.monotonic()

        if results["urls"] or results["links"] or results["redirects"] or results["issues"]:
            logger.info(
                "batch_flush_complete",
                urls=results["urls"],
                links=results["links"],
                redirects=results["redirects"],
                issues=results["issues"],
                errors=results["errors"],
            )

        return results

    async def close(self) -> dict[str, int]:
        """Final flush and report totals."""
        results = await self.flush()
        logger.info(
            "batch_inserter_closed",
            total_urls=self._total_flushed_urls,
            total_links=self._total_flushed_links,
            total_redirects=self._total_flushed_redirects,
            total_issues=self._total_flushed_issues,
            total_errors=self._total_errors,
        )
        return results

    # ------------------------------------------------------------------
    # COPY flush methods with error isolation fallback
    # ------------------------------------------------------------------

    async def _flush_urls(self, conn: asyncpg.Connection, rows: list[tuple]) -> tuple[int, int]:
        """COPY crawled_urls rows. Returns (flushed_count, error_count)."""
        columns = [
            "id",
            "crawl_id",
            "url",
            "url_hash",
            "status_code",
            "content_type",
            "redirect_url",
            "redirect_chain",
            "response_time_ms",
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
            "content_hash",
            "crawl_depth",
            "seo_data",
            # search_vector excluded — auto-populated by DB trigger
        ]
        return await self._copy_with_fallback(conn, "crawled_urls", columns, rows)

    async def _flush_links(self, conn: asyncpg.Connection, rows: list[tuple]) -> tuple[int, int]:
        """COPY page_links rows. Returns (flushed_count, error_count)."""
        columns = [
            "crawl_id",
            "source_url_id",
            "target_url",
            "target_url_hash",
            "anchor_text",
            "link_type",
            "rel_attrs",
            "link_position",
            "is_javascript",
        ]
        return await self._copy_with_fallback(conn, "page_links", columns, rows)

    async def _flush_redirects(
        self, conn: asyncpg.Connection, rows: list[tuple]
    ) -> tuple[int, int]:
        """COPY redirects rows. Returns (flushed_count, error_count)."""
        columns = [
            "crawl_id",
            "chain_id",
            "source_url",
            "target_url",
            "status_code",
            "hop_number",
        ]
        return await self._copy_with_fallback(conn, "redirects", columns, rows)

    async def _flush_issues(self, conn: asyncpg.Connection, rows: list[tuple]) -> tuple[int, int]:
        """COPY url_issues rows. Returns (flushed_count, error_count)."""
        columns = [
            "id",
            "crawl_id",
            "url_id",
            "issue_type",
            "severity",
            "category",
            "details",
        ]
        return await self._copy_with_fallback(conn, "url_issues", columns, rows)

    async def _copy_with_fallback(
        self,
        conn: asyncpg.Connection,
        table: str,
        columns: list[str],
        rows: list[tuple],
    ) -> tuple[int, int]:
        """Try COPY first (fast path), fall back to individual INSERTs on failure.

        Returns (success_count, error_count).
        """
        try:
            await conn.copy_records_to_table(
                table,
                records=rows,
                columns=columns,
            )
            return len(rows), 0
        except Exception as e:
            logger.warning(
                "copy_failed_fallback_to_inserts",
                table=table,
                row_count=len(rows),
                error=str(e),
            )
            return await self._insert_individually(conn, table, columns, rows)

    async def _insert_individually(
        self,
        conn: asyncpg.Connection,
        table: str,
        columns: list[str],
        rows: list[tuple],
    ) -> tuple[int, int]:
        """Insert rows one by one to isolate bad rows."""
        col_str = ", ".join(columns)
        placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
        query = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"

        success = 0
        errors = 0
        for row in rows:
            try:
                await conn.execute(query, *row)
                success += 1
            except Exception as e:
                errors += 1
                logger.warning(
                    "insert_row_failed",
                    table=table,
                    error=str(e),
                    row_preview=str(row[:3]),  # Log first 3 fields for debugging
                )
        return success, errors


def _json_dumps(obj: Any) -> str:
    """Serialize to JSON string for JSONB columns."""
    import json

    return json.dumps(obj, default=str)
