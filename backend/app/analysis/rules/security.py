"""Security Analyzer (F2.8) — inline per-URL checks for security issues."""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData
from app.crawler.fetcher import FetchResult


def analyze_security(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
    fetch_result: FetchResult,
    url: str,
) -> list[tuple]:
    """Check security posture for a URL. Returns issue tuples."""
    issues: list[tuple] = []

    # HTTP URL (not HTTPS)
    if url.startswith("http://"):
        issues.append(_make_issue_tuple(crawl_id, url_id, "http_url"))

    # Mixed content (HTTPS page loading HTTP resources)
    if page_data.mixed_content_urls:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "mixed_content",
                {
                    "count": len(page_data.mixed_content_urls),
                    "urls": page_data.mixed_content_urls[:5],
                },
            )
        )

    # Security headers checks (only for pages we fetched successfully)
    # Lowercase keys: HTTP header names are case-insensitive (RFC 7230)
    headers_lower = {k.lower(): v for k, v in (fetch_result.headers or {}).items()}

    if not headers_lower.get("strict-transport-security"):
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_hsts"))

    if not headers_lower.get("content-security-policy"):
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_csp"))

    if not headers_lower.get("x-content-type-options"):
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_x_content_type_options"))

    if not headers_lower.get("x-frame-options"):
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_x_frame_options"))

    return issues
