"""Canonical registry of all SEO issue types with severity and category.

Every issue created by inline or post-crawl analyzers MUST reference a type
defined here. The registry is the single source of truth for issue metadata.
"""

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"
    opportunity = "opportunity"


class Category(str, Enum):
    titles = "titles"
    meta_descriptions = "meta_descriptions"
    headings = "headings"
    images = "images"
    canonicals = "canonicals"
    directives = "directives"
    url_quality = "url_quality"
    security = "security"
    links = "links"
    indexability = "indexability"


@dataclass(frozen=True)
class IssueDefinition:
    issue_type: str
    severity: Severity
    category: Category
    description: str


ISSUE_REGISTRY: dict[str, IssueDefinition] = {}


def _register(issue_type: str, severity: Severity, category: Category, description: str) -> None:
    ISSUE_REGISTRY[issue_type] = IssueDefinition(issue_type, severity, category, description)


# ---------------------------------------------------------------------------
# Titles (F2.1)
# ---------------------------------------------------------------------------
_register("missing_title", Severity.critical, Category.titles, "Page has no <title> tag")
_register(
    "duplicate_title", Severity.warning, Category.titles, "Title is identical to another page"
)
_register("title_too_long", Severity.warning, Category.titles, "Title exceeds 60 characters")
_register("title_too_short", Severity.warning, Category.titles, "Title is under 30 characters")
_register(
    "title_pixel_too_wide",
    Severity.warning,
    Category.titles,
    "Title exceeds 580px SERP display width",
)
_register(
    "title_same_as_h1", Severity.info, Category.titles, "Title is identical to the H1 heading"
)
_register(
    "multiple_titles", Severity.warning, Category.titles, "Page has more than one <title> tag"
)

# ---------------------------------------------------------------------------
# Meta Descriptions (F2.2)
# ---------------------------------------------------------------------------
_register(
    "missing_meta_description",
    Severity.warning,
    Category.meta_descriptions,
    "Page has no meta description",
)
_register(
    "duplicate_meta_description",
    Severity.warning,
    Category.meta_descriptions,
    "Meta description is identical to another page",
)
_register(
    "meta_description_too_long",
    Severity.info,
    Category.meta_descriptions,
    "Meta description exceeds 155 characters",
)
_register(
    "meta_description_too_short",
    Severity.info,
    Category.meta_descriptions,
    "Meta description is under 70 characters",
)
_register(
    "multiple_meta_descriptions",
    Severity.warning,
    Category.meta_descriptions,
    "Page has more than one meta description",
)

# ---------------------------------------------------------------------------
# Headings (F2.3)
# ---------------------------------------------------------------------------
_register("missing_h1", Severity.warning, Category.headings, "Page has no H1 heading")
_register(
    "duplicate_h1", Severity.warning, Category.headings, "H1 is identical to another page's H1"
)
_register("multiple_h1", Severity.warning, Category.headings, "Page has more than one H1 heading")
_register("h1_too_long", Severity.info, Category.headings, "H1 exceeds 70 characters")
_register(
    "non_sequential_headings",
    Severity.info,
    Category.headings,
    "Heading hierarchy skips levels (e.g. H1 → H3)",
)

# ---------------------------------------------------------------------------
# Images (F2.4)
# ---------------------------------------------------------------------------
_register("missing_alt_text", Severity.warning, Category.images, "Image has no alt attribute")
_register(
    "alt_text_too_long", Severity.info, Category.images, "Image alt text exceeds 125 characters"
)
_register(
    "missing_image_dimensions",
    Severity.info,
    Category.images,
    "Image missing width or height attributes (causes CLS)",
)

# ---------------------------------------------------------------------------
# Canonicals (F2.5)
# ---------------------------------------------------------------------------
_register("missing_canonical", Severity.warning, Category.canonicals, "Page has no canonical tag")
_register(
    "self_referencing_canonical", Severity.info, Category.canonicals, "Canonical points to itself"
)
_register(
    "multiple_canonicals",
    Severity.critical,
    Category.canonicals,
    "Page has more than one canonical tag",
)
_register(
    "canonical_mismatch",
    Severity.warning,
    Category.canonicals,
    "Canonical points to a different URL",
)
_register(
    "non_indexable_canonical",
    Severity.warning,
    Category.canonicals,
    "Canonical target is non-indexable",
)

# ---------------------------------------------------------------------------
# Directives (F2.6)
# ---------------------------------------------------------------------------
_register("has_noindex", Severity.info, Category.directives, "Page has noindex directive")
_register("has_nofollow", Severity.info, Category.directives, "Page has nofollow directive")
_register(
    "has_noindex_nofollow", Severity.info, Category.directives, "Page has both noindex and nofollow"
)
_register(
    "multiple_robots_meta",
    Severity.warning,
    Category.directives,
    "Page has multiple meta robots tags",
)
_register(
    "has_x_robots_tag", Severity.info, Category.directives, "X-Robots-Tag HTTP header present"
)

# ---------------------------------------------------------------------------
# URL Quality (F2.7)
# ---------------------------------------------------------------------------
_register(
    "url_non_ascii", Severity.warning, Category.url_quality, "URL contains non-ASCII characters"
)
_register(
    "url_has_underscores",
    Severity.info,
    Category.url_quality,
    "URL contains underscores instead of hyphens",
)
_register(
    "url_has_uppercase", Severity.info, Category.url_quality, "URL contains uppercase characters"
)
_register("url_too_long", Severity.warning, Category.url_quality, "URL exceeds 115 characters")
_register(
    "url_has_parameters", Severity.info, Category.url_quality, "URL contains query parameters"
)
_register(
    "url_has_multiple_slashes",
    Severity.info,
    Category.url_quality,
    "URL contains consecutive slashes in path",
)

# ---------------------------------------------------------------------------
# Security (F2.8)
# ---------------------------------------------------------------------------
_register("http_url", Severity.warning, Category.security, "Page served over HTTP (not HTTPS)")
_register("mixed_content", Severity.warning, Category.security, "HTTPS page loads HTTP resources")
_register(
    "missing_hsts", Severity.info, Category.security, "Missing Strict-Transport-Security header"
)
_register("missing_csp", Severity.info, Category.security, "Missing Content-Security-Policy header")
_register(
    "missing_x_content_type_options",
    Severity.info,
    Category.security,
    "Missing X-Content-Type-Options header",
)
_register(
    "missing_x_frame_options", Severity.info, Category.security, "Missing X-Frame-Options header"
)

# ---------------------------------------------------------------------------
# Links (F2.9)
# ---------------------------------------------------------------------------
_register(
    "broken_link_4xx", Severity.critical, Category.links, "Link target returns 4xx client error"
)
_register(
    "broken_link_5xx", Severity.warning, Category.links, "Link target returns 5xx server error"
)

# ---------------------------------------------------------------------------
# Indexability (F2.13)
# ---------------------------------------------------------------------------
_register(
    "non_indexable_noindex",
    Severity.info,
    Category.indexability,
    "Non-indexable: noindex directive",
)
_register(
    "non_indexable_canonicalized",
    Severity.info,
    Category.indexability,
    "Non-indexable: canonicalized to different URL",
)
_register(
    "non_indexable_redirect",
    Severity.info,
    Category.indexability,
    "Non-indexable: URL redirects (3xx)",
)
_register(
    "non_indexable_client_error",
    Severity.warning,
    Category.indexability,
    "Non-indexable: client error (4xx)",
)
_register(
    "non_indexable_server_error",
    Severity.critical,
    Category.indexability,
    "Non-indexable: server error (5xx)",
)
