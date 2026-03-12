"""Directives Analyzer (F2.6) — inline per-URL checks for robot directives."""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData
from app.crawler.fetcher import FetchResult


def analyze_directives(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
    fetch_result: FetchResult,
) -> list[tuple]:
    """Check robot directives for informational issues. Returns issue tuples."""
    issues: list[tuple] = []
    robots = page_data.robots_meta

    has_noindex = "noindex" in robots or "none" in robots
    has_nofollow = "nofollow" in robots or "none" in robots

    # Combined noindex + nofollow (report as single combined issue)
    if has_noindex and has_nofollow:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "has_noindex_nofollow",
                {"directives": robots},
            )
        )
    elif has_noindex:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "has_noindex",
                {"directives": robots},
            )
        )
    elif has_nofollow:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "has_nofollow",
                {"directives": robots},
            )
        )

    # Multiple meta robots tags
    if page_data.robots_meta_tag_count > 1:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "multiple_robots_meta",
                {"count": page_data.robots_meta_tag_count},
            )
        )

    # RFC 7230: case-insensitive header lookup
    headers_lower = {k.lower(): v for k, v in (fetch_result.headers or {}).items()}
    x_robots_val = headers_lower.get("x-robots-tag")
    if x_robots_val:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "has_x_robots_tag",
                {"value": x_robots_val},
            )
        )

    return issues
