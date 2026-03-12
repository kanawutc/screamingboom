"""Canonicals Analyzer (F2.5) — inline per-URL checks for canonical issues.

Cross-URL canonical verification (non-indexable targets) is handled in post_crawl.py.
"""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData


def analyze_canonicals(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
    url: str,
) -> list[tuple]:
    """Check canonical tags for SEO issues. Returns issue tuples."""
    issues: list[tuple] = []

    # Only check canonicals on indexable HTML pages (non-redirects)
    if not page_data.is_indexable and page_data.indexability_reason in (
        "redirect",
        "client_error",
        "server_error",
        "non_html",
    ):
        return issues

    # Missing canonical
    if not page_data.canonical_url:
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_canonical"))
        return issues

    # Multiple canonical tags
    if page_data.canonical_count > 1:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "multiple_canonicals",
                {"count": page_data.canonical_count},
            )
        )

    # Self-referencing canonical (informational — not an error)
    canonical = page_data.canonical_url.rstrip("/")
    page_url = url.rstrip("/")
    if canonical.lower() == page_url.lower():
        issues.append(_make_issue_tuple(crawl_id, url_id, "self_referencing_canonical"))
    # Note: A canonical pointing to a different URL is NORMAL behaviour.
    # Cross-URL canonical issues (e.g. target is non-indexable) are caught
    # in post_crawl.py, not here.

    return issues
