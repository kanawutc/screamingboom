"""URL Quality Analyzer (F2.7) — inline per-URL checks on URL string itself."""

import re
import uuid
from urllib.parse import urlparse

from app.analysis.analyzer import _make_issue_tuple


def analyze_url_quality(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    url: str,
) -> list[tuple]:
    """Check URL string for SEO quality issues. Returns issue tuples."""
    issues: list[tuple] = []
    parsed = urlparse(url)

    # URL too long (> 115 chars)
    if len(url) > 115:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "url_too_long",
                {"length": len(url)},
            )
        )

    # URL has non-ASCII characters
    try:
        url.encode("ascii")
    except UnicodeEncodeError:
        issues.append(_make_issue_tuple(crawl_id, url_id, "url_non_ascii"))

    path = parsed.path

    # URL has underscores in path
    if "_" in path:
        issues.append(_make_issue_tuple(crawl_id, url_id, "url_has_underscores"))

    # URL has uppercase in path (not domain)
    if path != path.lower():
        issues.append(_make_issue_tuple(crawl_id, url_id, "url_has_uppercase"))

    # URL has query parameters
    if parsed.query:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "url_has_parameters",
                {"query": parsed.query[:100]},
            )
        )

    # URL has multiple consecutive slashes in path (not the scheme://)
    if "//" in path:
        issues.append(_make_issue_tuple(crawl_id, url_id, "url_has_multiple_slashes"))

    return issues
