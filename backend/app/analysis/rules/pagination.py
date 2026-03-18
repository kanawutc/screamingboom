"""Pagination analysis rules: inline per-URL checks for rel=next/prev.

Checks:
- Pagination URL not present as anchor tag link
- Multiple rel=next or rel=prev on page
- Non-indexable paginated page
"""

import uuid

from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData


def analyze_pagination(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
) -> list[tuple]:
    """Run inline pagination analysis. Returns issue tuples."""
    issues: list[tuple] = []

    if not page_data.pagination:
        return issues

    pag = page_data.pagination

    # --- Multiple pagination URLs ---
    next_count = page_data.pagination_count.get("next", 0)
    prev_count = page_data.pagination_count.get("prev", 0)
    if next_count > 1 or prev_count > 1:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "multiple_pagination_urls",
                {"next_count": next_count, "prev_count": prev_count},
            )
        )

    # --- Pagination URL not in anchor tag ---
    # Collect all <a> href URLs on the page
    anchor_urls = {link.url for link in page_data.links if link.tag == "a"}

    for pag_url, label in [(pag.rel_next, "rel_next"), (pag.rel_prev, "rel_prev")]:
        if pag_url and pag_url not in anchor_urls:
            issues.append(
                _make_issue_tuple(
                    crawl_id,
                    url_id,
                    "pagination_url_not_in_anchor",
                    {"pagination_url": pag_url, "attribute": label},
                )
            )

    # --- Non-indexable paginated page ---
    if not page_data.is_indexable:
        issues.append(
            _make_issue_tuple(
                crawl_id,
                url_id,
                "non_indexable_paginated",
                {"reason": page_data.indexability_reason},
            )
        )

    return issues
