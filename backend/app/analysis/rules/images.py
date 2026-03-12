"""Images Analyzer (F2.4) — inline per-URL checks for image issues.

Note: Generates one issue per image (not per page) for missing_alt_text
and missing_image_dimensions.
"""

import uuid
from app.analysis.analyzer import _make_issue_tuple
from app.crawler.parser import PageData


def analyze_images(
    crawl_id: uuid.UUID,
    url_id: uuid.UUID,
    page_data: PageData,
) -> list[tuple]:
    """Check images for SEO issues. Returns issue tuples."""
    issues: list[tuple] = []

    for img in page_data.images:
        if not img.alt or not img.alt.strip():
            issues.append(
                _make_issue_tuple(
                    crawl_id,
                    url_id,
                    "missing_alt_text",
                    {"src": img.src[:200]},
                )
            )

        # Alt text too long (> 125 chars)
        if img.alt and len(img.alt) > 125:
            issues.append(
                _make_issue_tuple(
                    crawl_id,
                    url_id,
                    "alt_text_too_long",
                    {"src": img.src[:200], "alt_length": len(img.alt)},
                )
            )

        # Missing image dimensions (causes CLS)
        if not img.width or not img.height:
            issues.append(
                _make_issue_tuple(
                    crawl_id,
                    url_id,
                    "missing_image_dimensions",
                    {"src": img.src[:200]},
                )
            )

    return issues
