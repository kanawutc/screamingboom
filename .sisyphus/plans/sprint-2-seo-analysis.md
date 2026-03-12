# Sprint 2 — Core SEO Analysis

## Scope

Features F2.1-F2.9 + F2.13 from PLAN.md: Page Titles, Meta Descriptions, Headings, Images, Canonicals, Directives, URL Quality, Security, Broken Links, Indexability.

## Architecture Decisions

1. **Zero schema migrations** — use existing `seo_data` JSONB and `url_issues` table
2. **Hybrid analysis** — inline analyzers (single-URL) + post-crawl SQL (cross-URL)
3. **Issue type registry** — canonical catalog of all issue types with severity/category
4. **COMPLETING state** — engine transitions crawling → completing → completed
5. **3 frontend tabs** — Overview (existing stats), URLs (with filters), Issues (new)
6. **Flat issues API** — `/issues` with `severity`/`category` filters + `/issues/summary`
7. **Pixel width** — Arial char-width lookup table (no PIL/font rendering)
8. **Image file size** — DEFERRED to Sprint 3 (requires HTTP HEAD per image)
9. **Images stored in seo_data.images** — no new table

## Execution Waves

```
Wave 0 (T1-T7):  Foundation — issue registry, analyzer pipeline, engine COMPLETING, parser gaps, issues API
Wave 1 (T8-T15): Inline Analyzers — F2.13, F2.1-F2.8 (parallelizable after foundation)
Wave 2 (T16-T18): Post-Crawl Analysis — duplicates, broken links, canonical verification
Wave 3 (T19-T22): Frontend — Issues tab, filter UI, summary cards, issue detail
Wave F (F1-F2):  Verification — E2E smoke test + review
```

---

## Wave 0: Foundation (T1-T7)

### T1: Issue Type Registry

**File**: `backend/app/analysis/issue_registry.py` (NEW)

Create canonical catalog of all Sprint 2 issue types:

```python
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

# Master registry — every issue type used across all analyzers
ISSUE_REGISTRY: dict[str, IssueDefinition] = {}

def _register(issue_type: str, severity: Severity, category: Category, description: str):
    ISSUE_REGISTRY[issue_type] = IssueDefinition(issue_type, severity, category, description)

# --- Titles (F2.1) ---
_register("missing_title", Severity.critical, Category.titles, "Page has no <title> tag")
_register("duplicate_title", Severity.warning, Category.titles, "Title is identical to another page")
_register("title_too_long", Severity.warning, Category.titles, "Title exceeds 60 characters")
_register("title_too_short", Severity.warning, Category.titles, "Title is under 30 characters")
_register("title_pixel_too_wide", Severity.warning, Category.titles, "Title exceeds 580px SERP display width")
_register("title_same_as_h1", Severity.info, Category.titles, "Title is identical to the H1 heading")
_register("multiple_titles", Severity.warning, Category.titles, "Page has more than one <title> tag")

# --- Meta Descriptions (F2.2) ---
_register("missing_meta_description", Severity.warning, Category.meta_descriptions, "Page has no meta description")
_register("duplicate_meta_description", Severity.warning, Category.meta_descriptions, "Meta description is identical to another page")
_register("meta_description_too_long", Severity.info, Category.meta_descriptions, "Meta description exceeds 155 characters")
_register("meta_description_too_short", Severity.info, Category.meta_descriptions, "Meta description is under 70 characters")
_register("multiple_meta_descriptions", Severity.warning, Category.meta_descriptions, "Page has more than one meta description")

# --- Headings (F2.3) ---
_register("missing_h1", Severity.warning, Category.headings, "Page has no H1 heading")
_register("duplicate_h1", Severity.warning, Category.headings, "H1 is identical to another page's H1")
_register("multiple_h1", Severity.warning, Category.headings, "Page has more than one H1 heading")
_register("h1_too_long", Severity.info, Category.headings, "H1 exceeds 70 characters")
_register("non_sequential_headings", Severity.info, Category.headings, "Heading hierarchy skips levels (e.g. H1 → H3)")

# --- Images (F2.4) ---
_register("missing_alt_text", Severity.warning, Category.images, "Image has no alt attribute")
_register("alt_text_too_long", Severity.info, Category.images, "Image alt text exceeds 125 characters")
_register("missing_image_dimensions", Severity.info, Category.images, "Image missing width or height attributes (causes CLS)")

# --- Canonicals (F2.5) ---
_register("missing_canonical", Severity.warning, Category.canonicals, "Page has no canonical tag")
_register("self_referencing_canonical", Severity.info, Category.canonicals, "Canonical points to itself")
_register("multiple_canonicals", Severity.critical, Category.canonicals, "Page has more than one canonical tag")
_register("canonical_mismatch", Severity.warning, Category.canonicals, "Canonical points to a different URL")
_register("non_indexable_canonical", Severity.warning, Category.canonicals, "Canonical target is non-indexable")

# --- Directives (F2.6) ---
_register("has_noindex", Severity.info, Category.directives, "Page has noindex directive")
_register("has_nofollow", Severity.info, Category.directives, "Page has nofollow directive")
_register("has_noindex_nofollow", Severity.info, Category.directives, "Page has both noindex and nofollow")
_register("multiple_robots_meta", Severity.warning, Category.directives, "Page has multiple meta robots tags")
_register("has_x_robots_tag", Severity.info, Category.directives, "X-Robots-Tag HTTP header present")

# --- URL Quality (F2.7) ---
_register("url_non_ascii", Severity.warning, Category.url_quality, "URL contains non-ASCII characters")
_register("url_has_underscores", Severity.info, Category.url_quality, "URL contains underscores instead of hyphens")
_register("url_has_uppercase", Severity.info, Category.url_quality, "URL contains uppercase characters")
_register("url_too_long", Severity.warning, Category.url_quality, "URL exceeds 115 characters")
_register("url_has_parameters", Severity.info, Category.url_quality, "URL contains query parameters")
_register("url_has_multiple_slashes", Severity.info, Category.url_quality, "URL contains consecutive slashes in path")

# --- Security (F2.8) ---
_register("http_url", Severity.warning, Category.security, "Page served over HTTP (not HTTPS)")
_register("mixed_content", Severity.warning, Category.security, "HTTPS page loads HTTP resources")
_register("missing_hsts", Severity.info, Category.security, "Missing Strict-Transport-Security header")
_register("missing_csp", Severity.info, Category.security, "Missing Content-Security-Policy header")
_register("missing_x_content_type_options", Severity.info, Category.security, "Missing X-Content-Type-Options header")
_register("missing_x_frame_options", Severity.info, Category.security, "Missing X-Frame-Options header")

# --- Links (F2.9) ---
_register("broken_link_4xx", Severity.critical, Category.links, "Link target returns 4xx client error")
_register("broken_link_5xx", Severity.warning, Category.links, "Link target returns 5xx server error")

# --- Indexability (F2.13) ---
_register("non_indexable_noindex", Severity.info, Category.indexability, "Non-indexable: noindex directive")
_register("non_indexable_canonicalized", Severity.info, Category.indexability, "Non-indexable: canonicalized to different URL")
_register("non_indexable_redirect", Severity.info, Category.indexability, "Non-indexable: URL redirects (3xx)")
_register("non_indexable_client_error", Severity.warning, Category.indexability, "Non-indexable: client error (4xx)")
_register("non_indexable_server_error", Severity.critical, Category.indexability, "Non-indexable: server error (5xx)")
```

Also create `backend/app/analysis/__init__.py` (replace empty file).

**Acceptance**: `python -c "from app.analysis.issue_registry import ISSUE_REGISTRY; print(len(ISSUE_REGISTRY))"` → ~45 issue types.

---

### T2: Pixel Width Calculator

**File**: `backend/app/analysis/pixel_width.py` (NEW)

Arial character-width lookup table for SERP display width estimation.

```python
# Google uses Roboto/Arial ~13px for titles, ~14px for descriptions
# Character widths in pixels (Arial 13px approximation)
# Source: measured from font metrics

def calculate_pixel_width(text: str, font_size: int = 13) -> int:
    """Estimate pixel width of text using Arial character widths."""
    ...
```

Key data: ~100 character widths for ASCII + common Unicode. Title SERP width limit: ~580px. Description limit: ~920px.

**Acceptance**: `calculate_pixel_width("Screaming Frog SEO Spider")` returns a reasonable int (200-400px range).

---

### T3: Enhance Parser — Store Images + Count Title/Meta Tags + Heading Sequence + Security Headers

**Files**: `backend/app/crawler/parser.py`, `backend/app/crawler/inserter.py`

**Parser changes**:
1. Count `<title>` tags (detect multiple)  
2. Count `<meta name="description">` tags (detect multiple)
3. Extract all heading levels h1-h6 for sequence validation → store in `seo_data.heading_sequence` as `["h1", "h2", "h2", "h3"]`
4. Detect mixed content: on HTTPS pages, find HTTP resource URLs (img src, script src, link href)

Add to `PageData` dataclass:
```python
title_count: int = 0
meta_desc_count: int = 0
heading_sequence: list[str] = field(default_factory=list)  # ["h1","h2","h3",...]
mixed_content_urls: list[str] = field(default_factory=list)
```

**Inserter changes**:
1. Store images in `seo_data.images` as `[{src, alt, width, height}]`
2. Store `heading_sequence` in `seo_data.heading_sequence`
3. Store `title_count`, `meta_desc_count` in `seo_data`
4. Store `mixed_content_urls` in `seo_data`
5. Compute and store `title_pixel_width` using pixel width calculator

**Acceptance**: After crawl, `seo_data` contains `images`, `heading_sequence`, `title_count`, `meta_desc_count`. `title_pixel_width` is non-NULL for pages with titles.

---

### T4: Merge X-Robots-Tag into robots_meta

**File**: `backend/app/crawler/engine.py`

After fetch, before parse/analyze: read `X-Robots-Tag` from `FetchResult.headers`, parse directives, merge into `PageData.robots_meta`.

In `_process_url()` method, after parsing:
```python
x_robots = fetch_result.headers.get("X-Robots-Tag", "")
if x_robots:
    directives = [d.strip().lower() for d in x_robots.split(",")]
    page_data.robots_meta.extend(directives)
    page_data.robots_meta = list(set(page_data.robots_meta))
```

Also store raw X-Robots-Tag in `seo_data.x_robots_tag`.

**Acceptance**: Crawl a site with X-Robots-Tag header → `robots_meta` array includes those directives, `seo_data.x_robots_tag` contains the raw header value.

---

### T5: Store Security Headers in seo_data

**File**: `backend/app/crawler/inserter.py` (or engine.py before insert)

Read from `FetchResult.headers` and store in `seo_data.security_headers`:
```json
{
  "strict_transport_security": "max-age=31536000",
  "content_security_policy": "default-src 'self'",
  "x_frame_options": "DENY",
  "x_content_type_options": "nosniff",
  "referrer_policy": "no-referrer"
}
```

Store NULL for headers not present (distinguishes "not checked" from "missing").

**Acceptance**: After crawl, `seo_data.security_headers` contains actual header values or null per header.

---

### T6: Enrich Indexability (F2.13)

**File**: `backend/app/crawler/engine.py` or a new `backend/app/analysis/indexability.py`

Currently `is_indexable` only checks `noindex` in robots_meta. Enrich to also check:
- Canonical points to different URL → non-indexable (reason: "canonicalized")
- Status code 3xx → non-indexable (reason: "redirect")
- Status code 4xx → non-indexable (reason: "client_error")
- Status code 5xx → non-indexable (reason: "server_error")
- Robots.txt blocked → non-indexable (reason: "blocked_by_robots")

Run this determination in the engine after fetch+parse, updating `page_data.is_indexable` and `page_data.indexability_reason` before insert.

**Acceptance**: Crawl books.toscrape.com. URLs with 200 and no noindex are indexable. Any 404 URLs show is_indexable=false, indexability_reason="client_error".

---

### T7: Engine COMPLETING State + Analyzer Pipeline

**Files**: `backend/app/crawler/engine.py`, `backend/app/analysis/analyzer.py` (NEW)

**Engine change** — after `_crawl_loop()` and `_inserter.close()`, before setting status to completed:

```python
# After main crawl loop finishes
await self._inserter.close()

# Post-crawl analysis phase
if not self._stopped:
    await self._update_crawl_status("completing")
    try:
        await self._run_post_crawl_analysis()
    except Exception as e:
        logger.exception("post_crawl_analysis_failed", error=str(e))
        # Analysis failure doesn't fail the crawl — just log it

    await self._update_crawl_status("completed")
else:
    await self._update_crawl_status("cancelled")
```

**Analyzer pipeline** (`backend/app/analysis/analyzer.py`):

```python
class CrawlAnalyzer:
    """Runs post-crawl cross-URL analysis and writes issues to url_issues."""
    
    def __init__(self, pool: asyncpg.Pool, crawl_id: uuid.UUID):
        ...
    
    async def run_inline_analysis(self, url_id: uuid.UUID, page_data: PageData, fetch_result: FetchResult, url: str) -> list[tuple]:
        """Per-URL inline analysis — returns issue tuples for batch insert."""
        ...
    
    async def run_post_crawl_analysis(self) -> int:
        """Cross-URL analysis via SQL. Returns issues created count."""
        ...
```

The inline analysis is called from the engine's `_process_url()` for each URL. The post-crawl analysis is called from `_run_post_crawl_analysis()`.

**Issue insertion**: Add `_issue_buffer: list[tuple]` to `BatchInserter` with a `add_issues()` method and COPY into `url_issues`.

**Acceptance**: After crawl completes, status transitions through "completing" before "completed". Issues exist in url_issues table.

---

## Wave 0.5: Issues API (T8-T9)

### T8: Issues API Endpoints

**Files**: `backend/app/api/v1/issues.py` (NEW), `backend/app/schemas/issue.py` (NEW), `backend/app/repositories/issue_repo.py` (NEW)

**Schema**:
```python
class IssueResponse(BaseModel):
    id: str
    crawl_id: str
    url_id: str
    url: str  # joined from crawled_urls
    issue_type: str
    severity: str
    category: str
    description: str  # from registry
    details: dict

class IssueSummary(BaseModel):
    total: int
    by_severity: dict[str, int]  # {"critical": 5, "warning": 23, ...}
    by_category: dict[str, int]  # {"titles": 8, "security": 12, ...}
```

**Endpoints**:
```
GET /api/v1/crawls/{crawl_id}/issues?severity=&category=&issue_type=&cursor=&limit=
GET /api/v1/crawls/{crawl_id}/issues/summary
```

Wire into `backend/app/api/v1/router.py`.

**Acceptance**: `curl /api/v1/crawls/{id}/issues` returns paginated issues. `curl /api/v1/crawls/{id}/issues/summary` returns counts grouped by severity and category.

---

### T9: Issues Repository

**File**: `backend/app/repositories/issue_repo.py` (NEW)

Methods:
- `list_issues(crawl_id, severity, category, issue_type, cursor, limit)` → CursorPage[IssueResponse]
- `get_summary(crawl_id)` → IssueSummary
- SQL JOINs `url_issues` with `crawled_urls` to include the URL string in results

Use raw asyncpg queries (following url_repo pattern) for performance with partitioned tables.

**Acceptance**: Repository returns correct data with cursor pagination and filters.

---

## Wave 1: Inline Analyzers (T10-T17)

All inline analyzers follow the same pattern — they receive `PageData`, `FetchResult`, and `url` string, and return a list of issue tuples.

Each analyzer is a module in `backend/app/analysis/rules/`:

### T10: Titles Analyzer (F2.1)

**File**: `backend/app/analysis/rules/titles.py`

Checks (inline — per URL):
- `missing_title` — title is None or empty
- `title_too_long` — title_length > 60
- `title_too_short` — title_length > 0 and < 30
- `title_pixel_too_wide` — title_pixel_width > 580
- `title_same_as_h1` — title matches first h1 (case-insensitive)
- `multiple_titles` — seo_data.title_count > 1

**Acceptance**: Crawl site with missing titles → `missing_title` issues generated.

---

### T11: Meta Descriptions Analyzer (F2.2)

**File**: `backend/app/analysis/rules/meta_descriptions.py`

Checks (inline):
- `missing_meta_description` — meta_description is None or empty
- `meta_description_too_long` — meta_desc_length > 155
- `meta_description_too_short` — meta_desc_length > 0 and < 70
- `multiple_meta_descriptions` — seo_data.meta_desc_count > 1

**Acceptance**: Issues generated for pages with/without meta descriptions.

---

### T12: Headings Analyzer (F2.3)

**File**: `backend/app/analysis/rules/headings.py`

Checks (inline):
- `missing_h1` — h1 is empty list
- `multiple_h1` — len(h1) > 1
- `h1_too_long` — any h1 > 70 chars
- `non_sequential_headings` — heading_sequence skips levels (h1 → h3 without h2)

**Acceptance**: Page with multiple H1s → `multiple_h1` issue generated.

---

### T13: Images Analyzer (F2.4)

**File**: `backend/app/analysis/rules/images.py`

Checks (inline — from seo_data.images):
- `missing_alt_text` — image has no alt or empty alt (one issue per image, details include src)
- `alt_text_too_long` — alt > 125 chars
- `missing_image_dimensions` — width or height missing

Note: Generates one issue per image, not per page. Details JSONB includes `{src, alt}`.

**Acceptance**: Pages with images missing alt text → `missing_alt_text` issues.

---

### T14: Canonicals Analyzer (F2.5)

**File**: `backend/app/analysis/rules/canonicals.py`

Checks (inline):
- `missing_canonical` — canonical_url is None (for indexable HTML pages)
- `self_referencing_canonical` — canonical_url == page URL (info, not an error)
- `multiple_canonicals` — detect via parser (count canonical link tags)
- `canonical_mismatch` — canonical_url != page URL and != None (inline check; cross-URL verification in post-crawl)

**Acceptance**: Page with canonical pointing elsewhere → `canonical_mismatch` issue.

---

### T15: Directives Analyzer (F2.6)

**File**: `backend/app/analysis/rules/directives.py`

Checks (inline):
- `has_noindex` — "noindex" in robots_meta
- `has_nofollow` — "nofollow" in robots_meta
- `has_noindex_nofollow` — both present
- `multiple_robots_meta` — more than one meta robots tag
- `has_x_robots_tag` — X-Robots-Tag header present

**Acceptance**: Page with noindex → `has_noindex` issue with severity=info.

---

### T16: URL Quality Analyzer (F2.7)

**File**: `backend/app/analysis/rules/url_quality.py`

Checks (inline — pure URL string analysis):
- `url_non_ascii` — any non-ASCII chars in URL
- `url_has_underscores` — underscore in path
- `url_has_uppercase` — uppercase in path (not domain)
- `url_too_long` — len(url) > 115
- `url_has_parameters` — "?" in URL
- `url_has_multiple_slashes` — "//" in path (not scheme)

**Acceptance**: URL with uppercase letters → `url_has_uppercase` issue.

---

### T17: Security Analyzer (F2.8)

**File**: `backend/app/analysis/rules/security.py`

Checks (inline):
- `http_url` — URL scheme is http (not https)
- `mixed_content` — HTTPS page with HTTP resources (from seo_data.mixed_content_urls)
- `missing_hsts` — security_headers.strict_transport_security is null
- `missing_csp` — security_headers.content_security_policy is null
- `missing_x_content_type_options` — security_headers.x_content_type_options is null
- `missing_x_frame_options` — security_headers.x_frame_options is null

**Acceptance**: HTTP pages → `http_url` issues. Pages missing HSTS → `missing_hsts` issues.

---

## Wave 2: Post-Crawl Analysis (T18-T20)

### T18: Duplicate Detection (Post-Crawl SQL)

**File**: `backend/app/analysis/post_crawl.py` (NEW)

SQL queries run during COMPLETING state:

1. **Duplicate titles**: `GROUP BY title WHERE title IS NOT NULL HAVING COUNT(*) > 1` → insert `duplicate_title` issues for each URL in the group
2. **Duplicate meta descriptions**: Same pattern → `duplicate_meta_description`
3. **Duplicate H1s**: `GROUP BY h1[1] WHERE h1 IS NOT NULL AND array_length(h1,1) > 0 HAVING COUNT(*) > 1` → `duplicate_h1`

Use `asyncpg` raw queries. Insert results directly into `url_issues`.

**Acceptance**: Crawl a site with duplicate titles → `duplicate_title` issues exist with details containing the duplicate title text and count.

---

### T19: Broken Links Detection (F2.9 — Post-Crawl SQL)

**File**: Added to `backend/app/analysis/post_crawl.py`

SQL query joining `page_links` + `crawled_urls`:
```sql
SELECT pl.source_url_id, pl.target_url, pl.anchor_text, cu.status_code, cu.url as source_url
FROM page_links pl
JOIN crawled_urls cu_target ON pl.target_url_hash = cu_target.url_hash AND pl.crawl_id = cu_target.crawl_id
JOIN crawled_urls cu ON pl.source_url_id = cu.id AND pl.crawl_id = cu.crawl_id
WHERE pl.crawl_id = $1
  AND cu_target.status_code >= 400
  AND pl.link_type = 'internal'
```

For each broken link found, create an issue on the SOURCE URL with details: `{target_url, status_code, anchor_text}`.

- 4xx → `broken_link_4xx` (severity: critical)
- 5xx → `broken_link_5xx` (severity: warning)

**Acceptance**: If crawl encounters any 404 pages, source pages linking to them get `broken_link_4xx` issues.

---

### T20: Canonical Cross-URL Verification (Post-Crawl SQL)

**File**: Added to `backend/app/analysis/post_crawl.py`

SQL to find canonical targets that are non-indexable:
```sql
SELECT cu.id, cu.url, cu.canonical_url, cu_target.is_indexable
FROM crawled_urls cu
JOIN crawled_urls cu_target ON cu_target.url_hash = encode(digest(cu.canonical_url, 'md5'), 'hex')::bytea
  AND cu_target.crawl_id = cu.crawl_id
WHERE cu.crawl_id = $1
  AND cu.canonical_url IS NOT NULL
  AND cu.canonical_url != cu.url
  AND cu_target.is_indexable = false
```

→ `non_indexable_canonical` issue on the source URL.

Also: URLs whose canonical points to a URL NOT in the crawl → `canonical_mismatch` with details `{target_not_crawled: true}`.

**Acceptance**: If canonical target is non-indexable → issue created.

---

## Wave 3: Frontend (T21-T24)

### T21: Issues Types + API Client

**Files**: `frontend/types/index.ts`, `frontend/lib/api-client.ts`

Add types:
```typescript
interface Issue {
  id: string;
  crawl_id: string;
  url_id: string;
  url: string;
  issue_type: string;
  severity: IssueSeverity;
  category: string;
  description: string;
  details: Record<string, unknown>;
}

interface IssueSummary {
  total: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}

interface IssueFilterParams {
  cursor?: string | null;
  limit?: number;
  severity?: string | null;
  category?: string | null;
  issue_type?: string | null;
}
```

Add to API client:
```typescript
issuesApi: {
  list: (crawlId: string, params: IssueFilterParams) => ...,
  summary: (crawlId: string) => ...,
}
```

**Acceptance**: TypeScript compiles. API client methods callable.

---

### T22: Issues Tab on Crawl Detail

**File**: `frontend/app/(dashboard)/crawls/[crawlId]/page.tsx`

Add "Issues" tab to existing Tabs component:
- Summary cards at top: Critical (red), Warning (yellow), Info (blue), Opportunity (green) counts
- Filter chips: severity dropdown, category dropdown
- Issues table: URL (truncated, linked), Issue Type, Severity (badge), Category, Description
- Cursor pagination (same pattern as URLs tab)

Use React Query with key `["crawl-issues", crawlId, severity, category]`.

**Acceptance**: Issues tab renders. Summary counts match API. Clicking severity/category filters the list.

---

### T23: URL Table Filter Dropdowns

**File**: `frontend/app/(dashboard)/crawls/[crawlId]/page.tsx`

Add filter dropdowns above the existing URLs table:
- Status Code filter: All / 2xx / 3xx / 4xx / 5xx
- Content Type filter: All / text/html / application/json / text/css / etc.
- Indexable filter: All / Yes / No

These use the existing `urlsApi.list()` filters (already supported by API but not exposed in UI).

**Acceptance**: Selecting "4xx" in status code filter shows only 4xx URLs. Selecting "No" for indexable shows non-indexable URLs.

---

### T24: Issues Summary on Crawl Overview

**File**: `frontend/app/(dashboard)/crawls/[crawlId]/page.tsx`

Add issues summary section to the overview area (between stats cards and tabs):
- Small bar/cards showing: "12 Critical · 45 Warnings · 23 Info · 8 Opportunities"
- Color-coded badges matching severity colors
- Only shown for completed crawls (not while crawling)

**Acceptance**: Completed crawl shows issue counts. Numbers match `/issues/summary` API.

---

## Verification Wave (F1-F2)

### F1: E2E Smoke Test

Run full pipeline:
1. Start spider crawl (books.toscrape.com, max_urls=50)
2. Wait for completion (should now go through "completing" state)
3. Verify issues exist: `curl /api/v1/crawls/{id}/issues/summary`
4. Verify specific issue types exist (books.toscrape.com should have URL quality issues, possibly missing meta descriptions)
5. Verify frontend Issues tab shows data
6. Verify URL table filters work
7. Test list mode still works

### F2: Verification Checklist

- [ ] All 45+ issue types in registry
- [ ] Inline analyzers generate issues during crawl
- [ ] Post-crawl analyzers find duplicates and broken links
- [ ] Issues API returns paginated results with filters
- [ ] Issues summary returns correct counts
- [ ] Frontend Issues tab renders with filters
- [ ] URL table has working filter dropdowns
- [ ] Engine goes through COMPLETING state
- [ ] X-Robots-Tag header merged into robots_meta
- [ ] Security headers stored in seo_data
- [ ] Images stored in seo_data.images
- [ ] title_pixel_width computed and stored
- [ ] Enriched indexability (redirects, 4xx, 5xx, canonical)
- [ ] Duplicate title/meta/h1 detection works
- [ ] Docker compose up works cleanly

---

## File Inventory (New + Modified)

### New Files (12)
```
backend/app/analysis/__init__.py          (replace empty)
backend/app/analysis/issue_registry.py    (T1)
backend/app/analysis/pixel_width.py       (T2)
backend/app/analysis/analyzer.py          (T7)
backend/app/analysis/post_crawl.py        (T18-T20)
backend/app/analysis/rules/__init__.py    
backend/app/analysis/rules/titles.py      (T10)
backend/app/analysis/rules/meta_descriptions.py  (T11)
backend/app/analysis/rules/headings.py    (T12)
backend/app/analysis/rules/images.py      (T13)
backend/app/analysis/rules/canonicals.py  (T14)
backend/app/analysis/rules/directives.py  (T15)
backend/app/analysis/rules/url_quality.py (T16)
backend/app/analysis/rules/security.py    (T17)
backend/app/schemas/issue.py              (T8)
backend/app/repositories/issue_repo.py    (T9)
backend/app/api/v1/issues.py              (T8)
```

### Modified Files (8)
```
backend/app/crawler/parser.py             (T3: title_count, meta_desc_count, heading_sequence, mixed_content)
backend/app/crawler/inserter.py           (T3: images in seo_data, T5: security headers, T7: issue buffer)
backend/app/crawler/engine.py             (T4: X-Robots-Tag, T6: indexability, T7: COMPLETING state)
backend/app/api/v1/router.py              (T8: wire issues routes)
frontend/types/index.ts                   (T21: Issue types)
frontend/lib/api-client.ts                (T21: issues API methods)
frontend/app/(dashboard)/crawls/[crawlId]/page.tsx  (T22-T24: issues tab, filters, summary)
```

---

## Guardrails (Hard Boundaries)

- NO new database tables — use seo_data JSONB and existing url_issues
- NO new database migrations — existing schema supports everything
- NO image file size checking (HTTP HEAD per image) — Sprint 3
- NO PIL/font rendering for pixel width — character-width lookup table only
- NO separate frontend pages per analysis category — tabs + filters on crawl detail
- NO more than 2 new API endpoints (issues list + issues summary)
- Analysis failure during COMPLETING must NOT fail the crawl — log and continue
- Inline analyzers must be stateless — no cross-URL state in memory
- Post-crawl analysis uses SQL only — no loading all URLs into memory
