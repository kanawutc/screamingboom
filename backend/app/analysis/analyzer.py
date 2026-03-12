"""CrawlAnalyzer: orchestrates inline (per-URL) and post-crawl (cross-URL) analysis.

Inline analysis runs for each crawled URL during the crawl loop.
Post-crawl analysis runs SQL-based cross-URL checks after the crawl completes.
"""

import json
import uuid
from typing import Any

import asyncpg
import structlog

from app.analysis.issue_registry import ISSUE_REGISTRY, Severity, Category
from app.crawler.parser import PageData
from app.crawler.fetcher import FetchResult

logger = structlog.get_logger(__name__)


def _make_issue_tuple(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    issue_type: str,
    details: dict[str, Any] | None = None,
) -> tuple:
    """Create a url_issues row tuple for batch insert.

    Returns: (id, crawl_id, url_id, issue_type, severity, category, details_json)
    """
    defn = ISSUE_REGISTRY[issue_type]
    return (
        uuid.uuid4(),
        crawl_id,
        url_id,
        issue_type,
        defn.severity.value,
        defn.category.value,
        json.dumps(details or {}, default=str),
    )


class CrawlAnalyzer:
    """Orchestrates SEO analysis for a crawl session.

    Usage in engine:
        analyzer = CrawlAnalyzer(pool, crawl_id)
        issues = analyzer.run_inline_analysis(url_id, page_data, fetch_result, url)
        inserter.add_issues(issues)
        # After crawl loop:
        await analyzer.run_post_crawl_analysis()
    """

    def __init__(self, pool: asyncpg.Pool, crawl_id: uuid.UUID) -> None:
        self._pool = pool
        self._crawl_id = crawl_id

    def run_inline_analysis(
        self,
        url_id: uuid.UUID,
        page_data: PageData,
        fetch_result: FetchResult,
        url: str,
    ) -> list[tuple]:
        """Run all inline (per-URL) analyzers. Returns issue tuples for batch insert.

        This is synchronous and stateless — no cross-URL state.
        """
        issues: list[tuple] = []

        # Import analyzers lazily to avoid circular imports
        from app.analysis.rules.titles import analyze_titles
        from app.analysis.rules.meta_descriptions import analyze_meta_descriptions
        from app.analysis.rules.headings import analyze_headings
        from app.analysis.rules.images import analyze_images
        from app.analysis.rules.canonicals import analyze_canonicals
        from app.analysis.rules.directives import analyze_directives
        from app.analysis.rules.url_quality import analyze_url_quality
        from app.analysis.rules.security import analyze_security

        # Only run content analyzers on HTML pages with page_data
        is_html = page_data.title is not None or page_data.word_count > 0

        if is_html:
            issues.extend(analyze_titles(self._crawl_id, url_id, page_data, url))
            issues.extend(analyze_meta_descriptions(self._crawl_id, url_id, page_data))
            issues.extend(analyze_headings(self._crawl_id, url_id, page_data))
            issues.extend(analyze_images(self._crawl_id, url_id, page_data))
            issues.extend(analyze_canonicals(self._crawl_id, url_id, page_data, url))
            issues.extend(analyze_directives(self._crawl_id, url_id, page_data, fetch_result))

        # URL quality and security run for ALL URLs (not just HTML)
        issues.extend(analyze_url_quality(self._crawl_id, url_id, url))
        issues.extend(analyze_security(self._crawl_id, url_id, page_data, fetch_result, url))

        return issues

    async def run_post_crawl_analysis(self) -> int:
        """Run cross-URL analysis via SQL. Returns total issues created."""
        from app.analysis.post_crawl import run_post_crawl_analysis

        return await run_post_crawl_analysis(self._pool, self._crawl_id)
