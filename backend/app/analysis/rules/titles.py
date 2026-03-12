"""Titles Analyzer (F2.1) — inline per-URL checks for title tag issues."""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData


def analyze_titles(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
    url: str,
) -> list[tuple]:
    """Check title tag for SEO issues. Returns issue tuples."""
    issues: list[tuple] = []

    # Missing title
    if not page_data.title:
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_title"))
        return issues  # No further title checks if missing

    # Multiple title tags
    if page_data.title_count > 1:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "multiple_titles",
                {"count": page_data.title_count},
            )
        )

    # Title too long (> 60 chars)
    title_len = (
        page_data.title_length if page_data.title_length is not None else len(page_data.title)
    )
    if title_len > 60:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "title_too_long",
                {"length": title_len, "title": page_data.title[:100]},
            )
        )

    # Title too short (< 30 chars, but > 0)
    if 0 < title_len < 30:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "title_too_short",
                {"length": title_len, "title": page_data.title},
            )
        )

    # Title pixel width too wide (> 580px)
    from app.analysis.pixel_width import calculate_pixel_width, TITLE_PIXEL_LIMIT

    px_width = calculate_pixel_width(page_data.title)
    if px_width > TITLE_PIXEL_LIMIT:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "title_pixel_too_wide",
                {"pixel_width": px_width, "limit": TITLE_PIXEL_LIMIT},
            )
        )

    # Title same as H1
    if page_data.h1:
        h1_text = page_data.h1[0].strip().lower()
        if page_data.title.strip().lower() == h1_text:
            issues.append(_make_issue_tuple(crawl_id, url_id, "title_same_as_h1"))

    return issues
