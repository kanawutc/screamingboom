"""Meta Descriptions Analyzer (F2.2) — inline per-URL checks."""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData


def analyze_meta_descriptions(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
) -> list[tuple]:
    """Check meta description for SEO issues. Returns issue tuples."""
    issues: list[tuple] = []

    # Missing meta description
    if not page_data.meta_description:
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_meta_description"))
        return issues

    # Multiple meta description tags
    if page_data.meta_desc_count > 1:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "multiple_meta_descriptions",
                {"count": page_data.meta_desc_count},
            )
        )

    # Too long (> 155 chars)
    desc_len = (
        page_data.meta_desc_length
        if page_data.meta_desc_length is not None
        else len(page_data.meta_description)
    )
    if desc_len > 155:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "meta_description_too_long",
                {"length": desc_len},
            )
        )

    # Too short (< 70 chars, but > 0)
    if 0 < desc_len < 70:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "meta_description_too_short",
                {"length": desc_len},
            )
        )

    return issues
