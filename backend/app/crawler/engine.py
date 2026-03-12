"""Crawl Engine: the main orchestrator that ties frontier → fetcher → parser → inserter.

Coordinates the BFS crawl loop, respects robots.txt, rate limits,
and publishes real-time progress via Redis pub/sub.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from app.crawler.fetcher import FetchResult, FetcherPool
from app.crawler.frontier import URLFrontier
from app.crawler.inserter import BatchInserter
from app.crawler.parser import ParserPool
from app.crawler.robots import RobotsChecker
from app.crawler.utils import extract_domain, normalize_url
from app.analysis.analyzer import CrawlAnalyzer

logger = structlog.get_logger(__name__)

# Maximum response body size we'll parse (10 MB)
_MAX_BODY_SIZE = 10 * 1024 * 1024

# Consecutive domain failures before aborting
_MAX_CONSECUTIVE_FAILURES = 10

# Progress publish interval
_PROGRESS_INTERVAL_URLS = 10
_PROGRESS_INTERVAL_SECONDS = 0.5

# HTML content types we'll parse
_HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})


@dataclass
class CrawlConfig:
    """Configuration for a single crawl session."""

    start_url: str
    max_urls: int = 10000
    max_depth: int = 10
    user_agent: str = "SEOSpider/1.0"
    respect_robots: bool = True
    follow_subdomains: bool = False
    request_timeout: int = 30
    crawl_delay: float = 0.0
    max_per_host: int = 2
    mode: str = "spider"
    urls: list[str] = field(default_factory=list)


@dataclass
class CrawlStats:
    """Runtime statistics for a crawl."""

    crawled_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    links_discovered: int = 0
    start_time: float = 0.0
    last_progress_time: float = 0.0
    last_progress_count: int = 0


class CrawlEngine:
    """Main crawl orchestrator — BFS loop with fetch → parse → insert pipeline.

    Usage::

        engine = CrawlEngine(
            crawl_id=crawl.id,
            config=CrawlConfig(start_url="https://example.com", max_urls=100),
            redis=redis_client,
            asyncpg_pool=pool,
        )
        await engine.run()
    """

    def __init__(
        self,
        crawl_id: uuid.UUID,
        config: CrawlConfig,
        redis: Any,  # redis.asyncio.Redis
        asyncpg_pool: Any,  # asyncpg.Pool
    ) -> None:
        self._crawl_id = crawl_id
        self._config = config
        self._redis = redis
        self._pool = asyncpg_pool

        # State flags
        self._paused = False
        self._stopped = False

        # Stats
        self._stats = CrawlStats()

        # Components (initialized in run())
        self._frontier: URLFrontier | None = None
        self._fetcher: FetcherPool | None = None
        self._parser: ParserPool | None = None
        self._inserter: BatchInserter | None = None
        self._robots: RobotsChecker | None = None
        self._analyzer: CrawlAnalyzer | None = None

        # Effective domain (resolved after potential start URL redirect)
        self._base_domain: str = ""

    @property
    def crawled_count(self) -> int:
        return self._stats.crawled_count

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    def pause(self) -> None:
        """Pause the crawl (resumes on next loop iteration)."""
        self._paused = True
        logger.info("crawl_paused", crawl_id=str(self._crawl_id))

    def resume(self) -> None:
        """Resume a paused crawl."""
        self._paused = False
        logger.info("crawl_resumed", crawl_id=str(self._crawl_id))

    def stop(self) -> None:
        """Stop the crawl gracefully."""
        self._stopped = True
        logger.info("crawl_stop_requested", crawl_id=str(self._crawl_id))

    async def run(self) -> CrawlStats:
        """Execute the crawl. Returns final stats."""
        crawl_id_str = str(self._crawl_id)

        logger.info("crawl_starting", crawl_id=crawl_id_str, start_url=self._config.start_url)
        self._stats.start_time = time.monotonic()
        self._stats.last_progress_time = self._stats.start_time

        # Initialize components
        self._frontier = URLFrontier(
            redis=self._redis, crawl_id=crawl_id_str, max_urls=self._config.max_urls
        )
        self._parser = ParserPool()
        self._inserter = BatchInserter(pool=self._pool)
        self._analyzer = CrawlAnalyzer(pool=self._pool, crawl_id=self._crawl_id)
        self._fetcher = FetcherPool(
            user_agent=self._config.user_agent,
            max_per_host=self._config.max_per_host,
            request_timeout=self._config.request_timeout,
        )

        try:
            async with self._fetcher:
                self._robots = RobotsChecker(
                    redis=self._redis,
                    fetcher=self._fetcher,
                    respect_robots=self._config.respect_robots,
                )

                # Determine base domain from start URL
                normalized_start = normalize_url(self._config.start_url)
                if not normalized_start:
                    await self._fail("Invalid start URL")
                    return self._stats

                self._base_domain = extract_domain(normalized_start)

                if self._config.mode == "list" and self._config.urls:
                    # List mode: seed all URLs at depth 0, no link following
                    for raw_url in self._config.urls:
                        norm = normalize_url(raw_url)
                        if norm:
                            await self._frontier.add(norm, depth=0)
                    # Override max_depth to 0 so we don't follow outlinks
                    self._config.max_depth = 0
                else:
                    # Spider mode: seed single start URL
                    await self._frontier.add(normalized_start, depth=0)

                # Main crawl loop
                await self._crawl_loop()

                # Drain inserter
                await self._inserter.close()

                # Update crawl status based on outcome
                if self._stopped:
                    await self._update_crawl_status("cancelled")
                else:
                    # Sprint 2: COMPLETING state + post-crawl analysis
                    await self._update_crawl_status("completing")
                    try:
                        if self._analyzer:
                            post_crawl_count = await self._analyzer.run_post_crawl_analysis()
                            logger.info(
                                "post_crawl_analysis_done",
                                crawl_id=crawl_id_str,
                                issues_created=post_crawl_count,
                            )
                    except Exception as e:
                        # Analysis failure must NOT fail the crawl
                        logger.exception(
                            "post_crawl_analysis_failed",
                            crawl_id=crawl_id_str,
                            error=str(e),
                        )

                    await self._update_crawl_status("completed")

                # Cleanup
                if self._robots:
                    await self._robots.close()
                await self._frontier.clear()

        except Exception as e:
            logger.exception("crawl_unrecoverable_error", crawl_id=crawl_id_str, error=str(e))
            try:
                if self._inserter:
                    await self._inserter.close()
                if self._robots:
                    await self._robots.close()
                if self._frontier:
                    await self._frontier.clear()
                await self._fail(str(e))
            except Exception:
                pass

        elapsed = time.monotonic() - self._stats.start_time
        logger.info(
            "crawl_finished",
            crawl_id=crawl_id_str,
            crawled=self._stats.crawled_count,
            errors=self._stats.error_count,
            elapsed_s=round(elapsed, 1),
        )

        return self._stats

    # ------------------------------------------------------------------
    # Main BFS crawl loop
    # ------------------------------------------------------------------

    async def _crawl_loop(self) -> None:
        """BFS loop: pop URL → check robots → fetch → parse → insert → repeat."""
        crawl_id_str = str(self._crawl_id)
        consecutive_failures = 0

        while True:
            # Check stop condition
            if self._stopped:
                break

            # Handle pause
            if self._paused:
                await asyncio.sleep(0.5)
                await self._publish_progress(force=True)
                continue

            # Check max_urls limit
            if self._stats.crawled_count >= self._config.max_urls:
                logger.info(
                    "crawl_max_urls_reached", crawl_id=crawl_id_str, limit=self._config.max_urls
                )
                break

            # Check consecutive failures
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                await self._fail(f"{_MAX_CONSECUTIVE_FAILURES} consecutive fetch failures")
                return

            # Pop next URL from frontier
            entry = await self._frontier.pop()
            if entry is None:
                # Frontier is empty — crawl complete
                break

            url, depth = entry

            # Check depth limit
            if depth > self._config.max_depth:
                self._stats.skipped_count += 1
                continue

            # Check robots.txt
            if not await self._robots.can_fetch(crawl_id_str, url, self._config.user_agent):
                self._stats.skipped_count += 1
                continue

            # Respect crawl delay
            if self._config.crawl_delay > 0:
                await asyncio.sleep(self._config.crawl_delay)

            # Fetch
            try:
                result = await self._fetcher.fetch(url)
            except Exception as e:
                logger.warning("fetch_exception", url=url, error=str(e))
                self._stats.error_count += 1
                consecutive_failures += 1
                continue

            # Check for fetch failure
            if result.status_code == 0:
                # Connection error
                if self._stats.crawled_count == 0:
                    # Start URL unreachable — fail immediately
                    await self._fail(f"Start URL unreachable: {result.error}")
                    return
                self._stats.error_count += 1
                consecutive_failures += 1
                continue

            # Reset consecutive failures on success
            consecutive_failures = 0

            # Parse HTML content (if applicable)
            page_data = None
            is_html = self._is_html_content(result.content_type)

            if is_html and len(result.body) <= _MAX_BODY_SIZE and result.body:
                try:
                    page_data = self._parser.parse(
                        result.body,
                        base_url=result.final_url,
                        content_type_header=result.content_type,
                    )
                except Exception as e:
                    logger.warning("parse_error", url=result.final_url, error=str(e))
            elif len(result.body) > _MAX_BODY_SIZE:
                logger.warning(
                    "body_too_large_skipping_parse", url=result.final_url, size=len(result.body)
                )

            effective_page_data = page_data if page_data else _empty_page_data()

            # --- Sprint 2: T4 — Merge X-Robots-Tag HTTP header into robots_meta ---
            # Lowercase header keys for case-insensitive lookup (RFC 7230)
            _headers_lower = {k.lower(): v for k, v in (result.headers or {}).items()}
            x_robots_raw = _headers_lower.get("x-robots-tag", "")
            if x_robots_raw and page_data:
                for directive in x_robots_raw.split(","):
                    d = directive.strip().lower()
                    if d and d not in page_data.robots_meta:
                        page_data.robots_meta.append(d)

            # --- Sprint 2: T6 — Enrich indexability beyond just noindex ---
            self._enrich_indexability(effective_page_data, result, url)

            # Insert URL record
            url_id = self._inserter.add_url(
                crawl_id=self._crawl_id,
                page_data=effective_page_data,
                fetch_result=result,
                crawl_depth=depth,
            )

            # --- Sprint 2: T7 — Run inline analysis and buffer issues ---
            if self._analyzer:
                try:
                    issues = self._analyzer.run_inline_analysis(
                        url_id,
                        effective_page_data,
                        result,
                        result.final_url,
                    )
                    if issues:
                        self._inserter.add_issues(issues)
                except Exception as e:
                    logger.warning("inline_analysis_error", url=result.final_url, error=str(e))

            # Insert links
            if page_data and page_data.links:
                self._inserter.add_links(self._crawl_id, url_id, page_data.links)

                # Add internal links to frontier for BFS
                for link in page_data.links:
                    if link.link_type == "internal" and self._is_in_scope(link.url):
                        await self._frontier.add(link.url, depth=depth + 1)
                        self._stats.links_discovered += 1

            # Insert redirect chain
            if result.redirect_chain:
                self._inserter.add_redirects(
                    self._crawl_id, result.redirect_chain, final_url=result.final_url
                )

            # Update stats
            self._stats.crawled_count += 1

            # Auto-flush inserter if needed
            if self._inserter.needs_flush:
                await self._inserter.flush()

            # Publish progress
            await self._publish_progress()

    # ------------------------------------------------------------------
    # Scope checking
    # ------------------------------------------------------------------

    def _is_in_scope(self, url: str) -> bool:
        """Check if a URL is within the crawl scope (same domain/subdomain)."""
        link_domain = extract_domain(url)
        if not link_domain:
            return False

        if link_domain == self._base_domain:
            return True

        if self._config.follow_subdomains:
            # Allow subdomains of the base domain
            return link_domain.endswith(f".{self._base_domain}")

        return False

    def _is_html_content(self, content_type: str) -> bool:
        """Check if Content-Type indicates HTML."""
        if not content_type:
            return False
        # Take only the media type, ignore charset params
        media_type = content_type.split(";")[0].strip().lower()
        return media_type in _HTML_CONTENT_TYPES

    # ------------------------------------------------------------------
    # Sprint 2: Enriched indexability (T6)
    # ------------------------------------------------------------------

    def _enrich_indexability(self, page_data: Any, fetch_result: FetchResult, url: str) -> None:
        """Determine indexability from multiple signals beyond just noindex.

        Checks: noindex, canonical mismatch, 3xx redirect, 4xx, 5xx, robots.txt blocked.
        The parser already sets noindex/none. We enrich with status code and canonical checks.
        """
        # Already marked non-indexable by parser (noindex/none)
        if not page_data.is_indexable:
            return

        status = fetch_result.status_code or 0

        # 3xx redirect → non-indexable
        if 300 <= status < 400:
            page_data.is_indexable = False
            page_data.indexability_reason = "redirect"
            return

        # 4xx client error → non-indexable
        if 400 <= status < 500:
            page_data.is_indexable = False
            page_data.indexability_reason = "client_error"
            return

        # 5xx server error → non-indexable
        if status >= 500:
            page_data.is_indexable = False
            page_data.indexability_reason = "server_error"
            return

        # Canonical points to different URL → non-indexable
        if page_data.canonical_url:
            canonical = page_data.canonical_url.rstrip("/")
            page_url = url.rstrip("/")
            if canonical.lower() != page_url.lower():
                page_data.is_indexable = False
                page_data.indexability_reason = "canonicalized"
                return

    # ------------------------------------------------------------------
    # Progress & status
    # ------------------------------------------------------------------

    async def _publish_progress(self, force: bool = False) -> None:
        """Publish crawl progress via Redis pub/sub."""
        now = time.monotonic()
        count_delta = self._stats.crawled_count - self._stats.last_progress_count
        time_delta = now - self._stats.last_progress_time

        if (
            not force
            and count_delta < _PROGRESS_INTERVAL_URLS
            and time_delta < _PROGRESS_INTERVAL_SECONDS
        ):
            return

        self._stats.last_progress_time = now
        self._stats.last_progress_count = self._stats.crawled_count

        payload = {
            "type": "progress",
            "crawl_id": str(self._crawl_id),
            "crawled_count": self._stats.crawled_count,
            "error_count": self._stats.error_count,
            "urls_in_frontier": 0,  # Could query frontier size but expensive
            "elapsed_seconds": round(now - self._stats.start_time, 1),
            "paused": self._paused,
        }

        try:
            channel = f"crawl:{self._crawl_id}:events"
            await self._redis.publish(channel, json.dumps(payload))
        except Exception:
            pass  # Non-critical: don't fail crawl for pub/sub error

    async def _update_crawl_status(self, status: str, error_msg: str | None = None) -> None:
        """Update crawl record in database."""
        try:
            async with self._pool.acquire() as conn:
                if status in ("completed", "failed", "cancelled"):
                    await conn.execute(
                        """
                        UPDATE crawls
                        SET status = $1,
                            completed_at = NOW(),
                            crawled_urls_count = $2,
                            error_count = $3,
                            total_urls = $2
                        WHERE id = $4
                        """,
                        status,
                        self._stats.crawled_count,
                        self._stats.error_count,
                        self._crawl_id,
                    )
                else:
                    await conn.execute(
                        "UPDATE crawls SET status = $1 WHERE id = $2",
                        status,
                        self._crawl_id,
                    )

            payload = {
                "type": "status_change",
                "crawl_id": str(self._crawl_id),
                "status": status,
                "crawled_count": self._stats.crawled_count,
                "error_count": self._stats.error_count,
                "elapsed_seconds": round(time.monotonic() - self._stats.start_time, 1),
            }
            if error_msg:
                payload["error"] = error_msg

            channel = f"crawl:{self._crawl_id}:events"
            await self._redis.publish(channel, json.dumps(payload))

        except Exception as e:
            logger.error("failed_to_update_crawl_status", error=str(e))

    async def _fail(self, error_msg: str) -> None:
        """Mark crawl as failed."""
        logger.error("crawl_failed", crawl_id=str(self._crawl_id), error=error_msg)
        await self._update_crawl_status("failed", error_msg=error_msg)


def _empty_page_data():
    """Return an empty PageData for non-HTML responses."""
    from app.crawler.parser import PageData

    return PageData(is_indexable=False, indexability_reason="non_html")
