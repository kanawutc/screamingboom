# SEO Analysis — AGENTS.md

## Two-Phase Architecture

### Phase 1: Inline Analysis (per-URL, during crawl)
- Runs synchronously in the crawl loop for each URL.
- Scope: single URL only (no cross-URL state).
- Orchestrator: `analyzer.py` calls all rule modules, collects issue tuples.
- Output: list of issue tuples passed to `inserter.add_issues()`.

### Phase 2: Post-Crawl Analysis (SQL-based, after crawl completes)
- Runs after all URLs fetched, before status=completed.
- Scope: cross-URL SQL queries (GROUP BY, JOIN). Never loads all URLs into memory.
- Orchestrator: `post_crawl.py` runs 8+ SQL-based checks.
- Output: issue tuples inserted via COPY to `url_issues`.

## Files & Responsibilities

| File | Purpose |
|------|---------|
| `analyzer.py` | Orchestrates both phases. Calls rule modules for inline, calls post_crawl for cross-URL. |
| `post_crawl.py` | SQL-based checks: duplicate titles/meta/H1, broken links, non-indexable canonicals, pagination validation. |
| `pixel_width.py` | Title pixel width calculator (estimated at 13px Arial for Google SERP). |
| `issue_registry.py` | Central registry of 40+ issue types. Single source of truth for severity/category/description. |

## Rule Modules (9 total, in `rules/`)

| Module | Issues Detected |
|--------|----------------|
| `titles.py` | missing, multiple, too long (>60), too short (<30), pixel width (>580px), same as H1 |
| `meta_descriptions.py` | missing, multiple, too long (>155), too short (<70) |
| `headings.py` | missing H1, multiple H1, H1 too long (>70), non-sequential hierarchy |
| `images.py` | missing alt, empty alt, missing srcset |
| `canonicals.py` | missing, multiple, self-referential |
| `directives.py` | noindex, nofollow, both, multiple robots meta, X-Robots-Tag header |
| `url_quality.py` | non-ASCII, underscores, uppercase, too long (>115), parameters, multiple slashes |
| `security.py` | HTTP (not HTTPS), mixed content, missing HSTS/CSP/X-Frame-Options/X-Content-Type-Options |
| `pagination.py` | multiple rel=next/prev, non-indexable paginated, unlinked pagination |

## Rule Module Pattern (follow this exactly)

```python
def analyze_X(crawl_id: uuid.UUID, url_id: int, page_data: PageData, url: str) -> list[tuple]:
    issues = []
    if not page_data.field:
        issues.append(_make_issue_tuple(crawl_id, url_id, "issue_type"))
        return issues
    # more checks...
    return issues
```

- Signature: `analyze_X(crawl_id, url_id, page_data, [fetch_result], [url]) -> list[tuple]`
- Returns: list of issue tuples (id, crawl_id, url_id, issue_type, severity, category, details_json)
- Details: JSON dict with context (e.g., `{"length": 75, "title": "..."}`)
- Each function checks one SEO category. Return early if primary field is missing.
- Issue types MUST be registered in `issue_registry.py` first.

## Post-Crawl Checks (SQL patterns)

| Check | SQL Pattern |
|-------|-------------|
| Duplicate titles | `GROUP BY title HAVING COUNT(*) > 1` |
| Duplicate meta | `GROUP BY meta_description HAVING COUNT(*) > 1` |
| Duplicate H1 | `GROUP BY h1[1] HAVING COUNT(*) > 1` |
| Broken links | `JOIN page_links ON target → crawled_urls WHERE status_code >= 400` |
| Non-indexable canonical | `canonical target WHERE is_indexable = false` |
| Pagination loops | Recursive CTE detecting cycles in rel=next chains |

## Issue Severity Levels
- `critical` — directly impacts indexability or ranking
- `warning` — best practice violation
- `info` — informational, no direct SEO impact
- `opportunity` — improvement suggestion

## Adding a New Rule
1. Register issue types in `issue_registry.py` with severity + category.
2. Create `rules/new_category.py` with `analyze_new_category()` function.
3. Add call in `analyzer.py` inline analysis method.
4. If cross-URL check needed, add SQL query in `post_crawl.py`.
