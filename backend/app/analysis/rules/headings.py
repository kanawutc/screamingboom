"""Headings Analyzer (F2.3) — inline per-URL checks for heading issues."""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData


def analyze_headings(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
) -> list[tuple]:
    """Check headings for SEO issues. Returns issue tuples."""
    issues: list[tuple] = []

    # Missing H1
    if not page_data.h1:
        issues.append(_make_issue_tuple(crawl_id, url_id, "missing_h1"))
    else:
        # Multiple H1s
        if len(page_data.h1) > 1:
            issues.append(
                _make_issue_tuple(
                    crawl_id,
                    url_id,
                    "multiple_h1",
                    {"count": len(page_data.h1), "h1s": [h[:100] for h in page_data.h1]},
                )
            )

        # H1 too long (> 70 chars)
        for h1_text in page_data.h1:
            if len(h1_text) > 70:
                issues.append(
                    _make_issue_tuple(
                        crawl_id,
                        url_id,
                        "h1_too_long",
                        {"length": len(h1_text), "h1": h1_text[:100]},
                    )
                )
                break  # One issue per page is enough

    # Non-sequential headings (e.g. h1 → h3, skipping h2)
    if page_data.heading_sequence:
        seq = page_data.heading_sequence
        for i in range(1, len(seq)):
            # Extract numeric level from "h1", "h2", etc.
            try:
                current_level = int(seq[i].lstrip("hH"))
                prev_level = int(seq[i - 1].lstrip("hH"))
            except (ValueError, IndexError):
                continue  # Skip malformed heading tags
            # A jump of more than 1 level down is non-sequential
            if current_level > prev_level + 1:
                issues.append(
                    _make_issue_tuple(
                        crawl_id,
                        url_id,
                        "non_sequential_headings",
                        {"sequence": seq[:20], "skip_at": f"{seq[i - 1]} → {seq[i]}"},
                    )
                )
                break  # Report once per page

    return issues
