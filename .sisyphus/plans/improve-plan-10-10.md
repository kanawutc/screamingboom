# Improve PLAN.md to 10/10 Quality — Full Specification

## TL;DR

> **Quick Summary**: Upgrade the existing PLAN.md (currently 6/10 — good feature inventory) into a full engineering specification (10/10) by adding 12 new technical sections: architecture deep dive, complete database schema, API specification, project structure, crawler engine algorithms, WebSocket protocol, performance strategy, testing strategy, Docker configuration, error handling, missing features, and feature dependency graph.
> 
> **Deliverables**: 
> - Improved `PLAN.md` with 12 new sections added
> - Tech stack updates: selectolax, ARQ, asyncpg, dual-parser strategy
> - Zero "TBD" or placeholder text
> - Cross-referenced consistency (DB↔API↔Project Structure)
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Task 1 → Task 3 → Task 7 → Task 14 → F1-F4

---

## Context

### Original Request
User asked to improve existing PLAN.md for Screaming Frog SEO Spider clone to "10/10" quality. Currently at 6/10 — excellent feature inventory (57 features, 6 phases) but lacking technical depth (no DB schema columns, no API endpoints, no project structure, no testing strategy, no performance targets).

### Interview Summary
**Key Discussions**:
- User chose to **improve existing PLAN.md** (not create new)
- User chose **Full Specification** depth (column-level DB, endpoint-level API)
- 3 tech stack upgrades confirmed: selectolax (35x faster), ARQ (async-native), asyncpg (bulk inserts)

**Research Findings** (3 parallel agents):
- selectolax is 35x faster than BeautifulSoup4 but **lacks XPath support** → need lxml as secondary parser
- ARQ is async-native, simpler than Celery, uses Redis already in stack
- asyncpg COPY achieves 50k rows/sec for bulk inserts
- Bloom filter: 12MB per 1M URLs at 0.1% false positive rate
- PostgreSQL HASH partitioning by crawl_id for data isolation
- Keyset/cursor pagination (not OFFSET) for 100k+ rows
- Two-level URL frontier: front queues (priority) + back queues (per-domain politeness)
- Redis pub/sub for decoupling WebSocket from crawler workers
- Router → Service → Repository pattern for FastAPI (50+ endpoints)
- TanStack Query + Server Components for Next.js data fetching
- Layered test pyramid: unit → API → integration → E2E

### Metis Review
**Identified Gaps** (addressed):
- **selectolax/XPath contradiction**: Feature 4.1 requires XPath 1.0-3.1, selectolax doesn't support it → Resolved: dual-parser strategy (selectolax primary + lxml for XPath)
- **Single-user vs Multi-user**: Feature 6.5 (Collaboration) contradicts "self-hosted single-user" → Resolved: V1 is single-user, Feature 6.5 marked as future
- **File size concern**: Adding 12 sections may push PLAN.md to 4000-6000 lines → Resolved: add Table of Contents with anchor links for navigation
- **HASH partition issue**: links table crosses crawl boundaries → Resolved: only partition `crawled_urls` and `url_issues`, keep `links` unpartitioned
- **Old draft contradiction**: `.sisyphus/drafts/seo-spider-clone.md` has wrong tech stack → Resolved: note for cleanup
- **Concurrent file editing**: Tasks writing to same PLAN.md → Resolved: sequential waves with explicit insertion points

---

## Work Objectives

### Core Objective
Transform PLAN.md from a feature inventory (6/10) into a complete engineering specification (10/10) by adding 12 technical sections with full detail.

### Concrete Deliverables
- 12 new sections added to PLAN.md
- Updated tech stack table
- Table of Contents with anchor links
- Zero placeholder text

### Definition of Done
- [ ] `grep -c "CREATE TABLE" PLAN.md` returns ≥ 15 tables
- [ ] `grep -c "### .*\(GET\|POST\|PUT\|DELETE\|PATCH\|WebSocket\)" PLAN.md` returns ≥ 40 endpoints
- [ ] `grep -ci "TBD\|TODO\|\[fill" PLAN.md` returns 0
- [ ] Every DB table referenced by at least one API endpoint
- [ ] All tech stack changes reflected (selectolax, ARQ, asyncpg)

### Must Have
- Complete database schema with columns, types, indexes, foreign keys
- API specification with request/response schemas
- Project directory structure (frontend + backend)
- Crawler state machine diagram
- WebSocket message protocol
- Performance targets with specific numbers
- Testing strategy with tools and patterns
- Docker Compose YAML
- Error handling patterns
- Feature dependency graph (Mermaid DAG)

### Must NOT Have (Guardrails)
- ❌ Working code files (no .py, .ts, .sql migration files) — this is documentation only
- ❌ New features beyond the 5 explicitly named missing features
- ❌ Multi-user/auth system design (V1 is single-user)
- ❌ Kubernetes/cloud deployment (Docker Compose local only)
- ❌ Observability stack (no Prometheus/Grafana/Jaeger)
- ❌ Rewriting existing Thai feature descriptions (augment, don't replace)
- ❌ Benchmark results or load test configurations
- ❌ Time estimates or resource allocation in dependency graph

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: NO (this is documentation editing, not code)
- **Automated tests**: NO — verification via grep commands and cross-reference checks
- **Framework**: N/A

### QA Policy
Every task MUST include agent-executed QA scenarios verifying:
1. Content was inserted at correct location in PLAN.md
2. No placeholder text remains
3. Cross-references to other sections are valid
4. Section depth matches target quality
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — sequential within wave, blocks everything):
├── Task 1: Update Tech Stack + Add Table of Contents [quick]
├── Task 2: Rewrite Architecture section [deep]
└── Task 3: Add Complete Database Schema [unspecified-high]

Wave 2 (Core specs — parallel, depends on Wave 1):
├── Task 4: Add Project Structure [quick]
├── Task 5: Add Crawler Engine Deep Dive [deep]
└── Task 6: Add WebSocket Protocol [unspecified-high]

Wave 3 (Dependent specs — parallel, depends on Wave 1-2):
├── Task 7: Add API Specification [unspecified-high]
├── Task 8: Add Performance Strategy [unspecified-high]
└── Task 9: Add Error Handling Strategy [unspecified-high]

Wave 4 (Infrastructure + testing — parallel):
├── Task 10: Add Testing Strategy [unspecified-high]
└── Task 11: Add Docker Compose Configuration [quick]

Wave 5 (Feature updates — sequential):
├── Task 12: Update existing features with tech changes [quick]
└── Task 13: Add 5 missing features [unspecified-high]

Wave 6 (Final — sequential, depends on ALL):
└── Task 14: Add Feature Dependency Graph + Cross-Reference Audit [deep]

Wave FINAL (Verification — 4 parallel):
├── F1: Plan compliance audit (oracle)
├── F2: Content quality review (unspecified-high)
├── F3: Cross-reference validation (unspecified-high)
└── F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 3 → Task 7 → Task 14 → F1-F4
Max Concurrent: 3 (Waves 2, 3)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 |
| 2 | 1 | 5, 6, 7, 8, 9, 14 |
| 3 | 1 | 7, 10, 14 |
| 4 | 1 | 10, 14 |
| 5 | 2 | 8, 14 |
| 6 | 2 | 7, 14 |
| 7 | 3, 6 | 10, 14 |
| 8 | 5 | 14 |
| 9 | 2 | 14 |
| 10 | 4, 7 | 14 |
| 11 | 1 | 14 |
| 12 | 1 | 13, 14 |
| 13 | 12 | 14 |
| 14 | ALL | F1-F4 |
| F1-F4 | 14 | — |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 `quick`, T2 `deep`, T3 `unspecified-high`
- **Wave 2**: 3 tasks — T4 `quick`, T5 `deep`, T6 `unspecified-high`
- **Wave 3**: 3 tasks — T7 `unspecified-high`, T8 `unspecified-high`, T9 `unspecified-high`
- **Wave 4**: 2 tasks — T10 `unspecified-high`, T11 `quick`
- **Wave 5**: 2 tasks — T12 `quick`, T13 `unspecified-high`
- **Wave 6**: 1 task — T14 `deep`
- **FINAL**: 4 tasks — F1 `oracle`, F2-F3 `unspecified-high`, F4 `deep`

---

## TODOs

> Each task edits PLAN.md at a specific insertion point. Tasks within the same wave target non-overlapping sections.
> **CRITICAL**: Every task must `Read PLAN.md` first to get current state, then `Edit` at the specified insertion point.
> **FILE**: `/Users/kc/Desktop/Screaming Frog Clone/PLAN.md`

### Wave 1 — Foundation (sequential: T1 → T2 → T3)

- [x] 1. Update Tech Stack Table + Add Table of Contents

  **What to do**:
  - Read current PLAN.md
  - Replace the Tech Stack table (line ~874-891) with updated entries:
    - Change `aiohttp + BeautifulSoup4` → `aiohttp + selectolax (primary) + lxml (XPath fallback)`
    - Change `Redis + Celery` → `Redis + ARQ`
    - Add row: `Bulk DB Operations | asyncpg | 50k rows/sec COPY insert for hot path`
    - Add row: `URL Dedup | pybloom-live (Bloom filter) | 12MB per 1M URLs, 0.1% false positive`
    - Add row: `State Management | Zustand | Lightweight, no boilerplate`
    - Add row: `Data Fetching | TanStack Query v5 | Server prefetch + client cache`
    - Change `TanStack Table (virtualized)` → `TanStack Table + react-virtual | Virtual scrolling for 1M+ rows`
    - Add row: `Reverse Proxy | Nginx | Route frontend/backend, WebSocket upgrade`
  - Add a Table of Contents section at the very top (after the title and before "สรุป Feature ทั้งหมด") with anchor links to ALL sections (existing + new ones that will be added later)
  - Add a note under the title: `> **V1 Scope**: Single-user, self-hosted. Multi-user collaboration (Feature 6.5) is deferred to V2.`
  - Update the Architecture ASCII diagram labels to reflect new tech (selectolax, ARQ, asyncpg, Nginx)

  **Must NOT do**:
  - Don't change existing feature descriptions
  - Don't add new features
  - Don't change the overall document structure

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (first task, sets foundation)
  - **Parallel Group**: Wave 1 (sequential)
  - **Blocks**: All other tasks
  - **Blocked By**: None

  **References**:
  - `PLAN.md:874-891` — Current Tech Stack table to update
  - `PLAN.md:29-50` — Architecture ASCII diagram to update labels
  - `PLAN.md:5-6` — Title area where Table of Contents goes
  - `.sisyphus/drafts/plan-improvement.md` — Tech stack decisions list

  **Acceptance Criteria**:
  - [ ] Tech Stack table has selectolax, ARQ, asyncpg, pybloom-live, Zustand, TanStack Query, Nginx entries
  - [ ] Table of Contents exists with ≥18 anchor links (6 phases + 12 new sections)
  - [ ] V1 single-user scope note present
  - [ ] Architecture diagram updated

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Tech stack table updated correctly
    Tool: Bash (grep)
    Steps:
      1. grep -c "selectolax" PLAN.md → Expected: ≥ 1
      2. grep -c "ARQ" PLAN.md → Expected: ≥ 1
      3. grep -c "asyncpg" PLAN.md → Expected: ≥ 1
      4. grep -c "pybloom" PLAN.md → Expected: ≥ 1
      5. grep -ci "BeautifulSoup4" PLAN.md → Expected: 0 (removed from tech stack)
      6. grep -ci "Celery" PLAN.md → Expected: 0 (removed from tech stack)
    Expected Result: All counts match
    Evidence: .sisyphus/evidence/task-1-tech-stack.txt

  Scenario: Table of Contents present
    Tool: Bash (grep)
    Steps:
      1. grep -c "Table of Contents\|สารบัญ" PLAN.md → Expected: ≥ 1
      2. grep -c "](#" PLAN.md → Expected: ≥ 18 (anchor links)
    Expected Result: ToC exists with working anchor links
    Evidence: .sisyphus/evidence/task-1-toc.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): update tech stack + add table of contents`
  - Files: `PLAN.md`

---

- [x] 2. Rewrite Architecture Section — Deep Technical Diagrams

  **What to do**:
  - Read current PLAN.md
  - Replace the existing "Architecture Overview" section (lines ~26-50) with a comprehensive architecture section containing:

  **2a. System Architecture Diagram** (enhanced ASCII/text):
  ```
  Replace the existing simple diagram with a detailed component diagram showing:
  - Frontend layer: Next.js 15 App Router, pages, components, WebSocket client
  - API Gateway: Nginx reverse proxy, WebSocket upgrade
  - Backend layer: FastAPI (API routers, services, repositories)
  - Crawler Engine: URL Frontier, Fetcher Pool, Parser Pool, Analyzer Pipeline
  - Data layer: PostgreSQL (partitioned), Redis (frontier, pub/sub, cache), Playwright
  - Show data flow arrows between components
  ```

  **2b. Crawler State Machine**:
  ```
  Define states: IDLE → CONFIGURING → QUEUED → CRAWLING → PAUSED → COMPLETING → COMPLETED → FAILED → CANCELLED
  Define transitions with trigger events:
  - IDLE → CONFIGURING: user submits crawl form
  - CONFIGURING → QUEUED: config validated, job enqueued
  - QUEUED → CRAWLING: worker picks up job
  - CRAWLING → PAUSED: user clicks pause
  - PAUSED → CRAWLING: user clicks resume
  - CRAWLING → COMPLETING: frontier empty, in-flight requests draining
  - COMPLETING → COMPLETED: all requests done, analysis complete
  - CRAWLING → FAILED: unrecoverable error
  - Any → CANCELLED: user clicks stop
  Use Mermaid stateDiagram-v2 syntax
  ```

  **2c. Data Flow Diagram** (request lifecycle):
  ```
  Show the complete path of a single crawled URL:
  1. User enters URL → Frontend → API POST /crawls
  2. Backend creates crawl record → Redis frontier ZADD
  3. CrawlEngine pops URL from frontier → Bloom filter check
  4. Fetcher pool sends HTTP request (aiohttp) → Response received
  5. Parser pool extracts data (selectolax) → SEO analysis inline
  6. BatchInserter accumulates → asyncpg COPY to PostgreSQL
  7. Issues detected → Redis pub/sub publish
  8. WebSocket manager → Frontend real-time update
  Use Mermaid sequenceDiagram syntax
  ```

  **2d. Component Interaction Map**:
  ```
  Define each major component with:
  - Input/Output contracts
  - Technology used
  - Scaling characteristics (CPU-bound vs I/O-bound)
  Components: URLFrontier, FetcherPool, ParserPool, SEOAnalyzer, BatchInserter, 
  WebSocketManager, RedisManager, DatabasePool
  ```

  **Must NOT do**:
  - Don't change any feature descriptions below the Architecture section
  - Don't add implementation code (pseudocode in Mermaid diagrams is OK)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 1 is sequential)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 5, 6, 7, 8, 9, 14
  - **Blocked By**: Task 1

  **References**:
  - `PLAN.md:26-50` — Current Architecture Overview section to replace
  - `PLAN.md:58-77` — Feature 1.1 Spider Mode (BFS queue, Redis, asyncio) — use for data flow accuracy
  - `PLAN.md:116-128` — Feature 1.4 JavaScript Rendering (Playwright integration) — include in architecture
  - `.sisyphus/drafts/plan-improvement.md` — Research findings: two-level URL frontier, Bloom filter, pub/sub
  - Research: Scrapy architecture pattern (Engine coordinates Scheduler→Downloader→Spider→Pipeline)

  **Acceptance Criteria**:
  - [ ] System architecture diagram shows all 5 layers (Frontend, Nginx, Backend, Crawler Engine, Data)
  - [ ] Crawler state machine has ≥ 8 states with labeled transitions (Mermaid stateDiagram-v2)
  - [ ] Data flow diagram shows complete URL lifecycle from input to WebSocket update (Mermaid sequenceDiagram)
  - [ ] Component interaction map lists ≥ 8 components with I/O contracts

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Architecture section has required diagrams
    Tool: Bash (grep)
    Steps:
      1. grep -c "stateDiagram-v2" PLAN.md → Expected: ≥ 1
      2. grep -c "sequenceDiagram" PLAN.md → Expected: ≥ 1
      3. grep -c "URLFrontier\|FetcherPool\|ParserPool\|BatchInserter" PLAN.md → Expected: ≥ 4
      4. grep -c "IDLE\|CRAWLING\|PAUSED\|COMPLETED\|FAILED" PLAN.md → Expected: ≥ 5
    Expected Result: All diagram types present with correct components
    Evidence: .sisyphus/evidence/task-2-architecture.txt

  Scenario: No existing feature descriptions modified
    Tool: Bash (diff)
    Steps:
      1. Compare lines 54+ (Feature 1.1 onward) with git diff — no changes expected
    Expected Result: Feature descriptions unchanged
    Evidence: .sisyphus/evidence/task-2-preserved.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add architecture deep dive with state machine and data flow diagrams`
  - Files: `PLAN.md`

---

- [x] 3. Add Complete Database Schema

  **What to do**:
  - Read current PLAN.md
  - Replace the existing "Database Schema (Simplified)" section (lines ~789-832) with a complete schema specification containing:

  **3a. Schema Design Principles**:
  - HASH partitioning by `crawl_id` for `crawled_urls` and `url_issues` tables (data isolation per crawl)
  - `page_links` table stays unpartitioned (needed for cross-crawl analysis in Feature 3.10)
  - JSONB for flexible SEO metadata (`seo_data` column) — avoids schema migrations for new signals
  - `TSVECTOR` + GIN index for full-text search on titles/descriptions/URLs
  - `pgvector` extension for vector embeddings (Feature 4.4)
  - URL deduplication via `url_hash` (MD5 bytea) for O(1) lookups

  **3b. Complete Table Definitions** (each table needs: all columns with types, NOT NULL, DEFAULT, CHECK constraints, PRIMARY KEY, FOREIGN KEY):
  - `projects` — id (UUID), name, domain, settings (JSONB), created_at, updated_at
  - `crawls` — id, project_id (FK), status (CHECK enum), mode, config (JSONB), started_at, completed_at, total_urls, crawled_urls, error_count
  - `crawl_configs` — id, name, is_default, config_data (JSONB), created_at
  - `crawled_urls` — id (BIGSERIAL), crawl_id (FK), url, url_hash (BYTEA), status_code, content_type, redirect_url, redirect_chain (JSONB), response_time_ms, title, title_length, title_pixel_width, meta_description, meta_desc_length, h1 (TEXT[]), h2 (TEXT[]), canonical_url, robots_meta, is_indexable, indexability_reason, word_count, content_hash (BYTEA for SimHash), crawl_depth, seo_data (JSONB), search_vector (TSVECTOR), crawled_at — **PARTITION BY HASH (crawl_id)**
  - `page_links` — id, crawl_id (FK), source_url_id (FK), target_url, target_url_hash, anchor_text, link_type (CHECK: internal/external/resource), rel_attrs (nofollow, sponsored, ugc), link_position, is_javascript
  - `url_issues` — id, crawl_id (FK), url_id (FK), issue_type, severity (CHECK: critical/warning/info/opportunity), category, details (JSONB) — **PARTITION BY HASH (crawl_id)**
  - `redirects` — id, crawl_id, source_url, target_url, status_code, hop_number, chain_id
  - `images` — id, crawl_id, url_id (FK), src, alt_text, width, height, file_size, is_linked, issues (JSONB)
  - `structured_data` — id, crawl_id, url_id (FK), format (json-ld/microdata/rdfa), schema_type, raw_data (JSONB), validation_errors (JSONB)
  - `hreflang_tags` — id, crawl_id, url_id (FK), lang, region, href, return_link_status
  - `sitemaps` — id, crawl_id, sitemap_url, url_count, is_index
  - `sitemap_urls` — id, sitemap_id (FK), url, lastmod, priority, changefreq
  - `custom_extractions` — id, crawl_id, url_id (FK), extractor_name, value, method (xpath/css/regex)
  - `custom_searches` — id, crawl_id, url_id (FK), search_name, matched (BOOLEAN), match_count
  - `ai_results` — id, crawl_id, url_id (FK), prompt_name, model, input_text, output_text, tokens_used, cost
  - `embeddings` — id, crawl_id, url_id (FK), model, vector (VECTOR(1536)), created_at
  - `analytics_data` — id, crawl_id, url_id (FK), source (ga4/gsc), metrics (JSONB)
  - `spelling_errors` — id, crawl_id, url_id (FK), word, error_type, suggestion, page_section, language
  - `accessibility_violations` — id, crawl_id, url_id (FK), rule_id, impact, wcag_level, description, dom_selector
  - `link_scores` — id, crawl_id, url_id (FK), score (NUMERIC), iteration_count
  - `crawl_comparisons` — id, crawl_id_a (FK), crawl_id_b (FK), created_at, summary (JSONB)

  **3c. Indexes** (per table: primary key, foreign keys, query-pattern indexes, partial indexes):
  - Show CREATE INDEX statements for critical query patterns
  - Include partial indexes (e.g., WHERE status_code >= 400 for error queries)
  - Include GIN indexes for JSONB and TSVECTOR columns

  **3d. Full-Text Search Trigger**:
  - Auto-update `search_vector` on INSERT/UPDATE
  - Weighted: title (A), meta_description (B), url (C)

  **3e. ER Diagram** (Mermaid erDiagram):
  - Show relationships between all tables
  - Mark cardinality (1:N, N:M)

  **Must NOT do**:
  - Don't write actual SQL migration files (this is documentation only)
  - Don't add multi-tenant columns (user_id, tenant_id) — V1 is single-user
  - Don't add audit columns (created_by, updated_by) — keep simple

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 1 is sequential)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 7, 10, 14
  - **Blocked By**: Task 1

  **References**:
  - `PLAN.md:789-832` — Current simplified schema to replace
  - `PLAN.md:246-298` — Features 2.1-2.8 (columns needed: title length/pixel, meta desc length, h1/h2 arrays, canonical, robots directives, security headers)
  - `PLAN.md:400-420` — Feature 3.1 Structured Data (JSON-LD/Microdata/RDFa formats, validation errors)
  - `PLAN.md:415-420` — Feature 3.2 Hreflang (13 error categories → hreflang_tags columns)
  - `PLAN.md:459-469` — Feature 3.6 Link Score (damping=0.85, 10 iterations → link_scores table)
  - `PLAN.md:486-497` — Feature 3.8 Accessibility (AXE 92 rules, WCAG levels → accessibility_violations columns)
  - `PLAN.md:580-593` — Feature 4.4 Vector Embeddings (cosine similarity → pgvector extension)
  - Research: PostgreSQL HASH partitioning, asyncpg COPY patterns, JSONB indexing strategy

  **Acceptance Criteria**:
  - [ ] ≥ 20 tables defined with full column specifications
  - [ ] Every table has: column name, data type, constraints (NOT NULL/DEFAULT/CHECK), primary key
  - [ ] Foreign key relationships defined between all related tables
  - [ ] ≥ 15 CREATE INDEX statements (including GIN, partial, composite)
  - [ ] TSVECTOR trigger for full-text search documented
  - [ ] Mermaid erDiagram showing all table relationships
  - [ ] pgvector extension mentioned for embeddings table

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Schema completeness check
    Tool: Bash (grep)
    Steps:
      1. grep -c "CREATE TABLE\|^### .*Table:" PLAN.md → Expected: ≥ 20
      2. grep -c "FOREIGN KEY\|REFERENCES\|FK" PLAN.md → Expected: ≥ 10
      3. grep -c "CREATE INDEX" PLAN.md → Expected: ≥ 15
      4. grep -c "erDiagram" PLAN.md → Expected: ≥ 1
      5. grep -c "pgvector\|VECTOR(" PLAN.md → Expected: ≥ 1
      6. grep -c "TSVECTOR\|search_vector" PLAN.md → Expected: ≥ 2
    Expected Result: All minimums met
    Evidence: .sisyphus/evidence/task-3-schema.txt

  Scenario: No placeholder columns
    Tool: Bash (grep)
    Steps:
      1. grep -ci "TBD\|TODO\|\[column\]\|\[type\]" PLAN.md → Expected: 0
    Expected Result: Zero placeholder text in schema
    Evidence: .sisyphus/evidence/task-3-no-placeholders.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add complete database schema with 20+ tables, indexes, and ER diagram`
  - Files: `PLAN.md`

### Wave 2 — Core Specs (parallel: T4, T5, T6 — all depend on Wave 1)

- [ ] 4. Add Project Structure (Frontend + Backend Directory Trees)

  **What to do**:
  - Read current PLAN.md
  - Add a new section "## Project Structure" after the Architecture section and before Phase 1
  - Include complete directory trees for:

  **4a. Root Structure**:
  ```
  seo-spider/
  ├── frontend/          # Next.js 15 App Router
  ├── backend/           # Python FastAPI
  ├── docker-compose.yml
  ├── nginx/             # Nginx config
  ├── .env.example
  └── README.md
  ```

  **4b. Frontend Structure** (Next.js 15 App Router, 3 levels deep with descriptions):
  ```
  frontend/
  ├── app/
  │   ├── layout.tsx                 # Root layout (providers, fonts)
  │   ├── page.tsx                   # Landing/redirect to dashboard
  │   ├── (dashboard)/
  │   │   ├── layout.tsx             # Dashboard shell (sidebar, topbar)
  │   │   ├── page.tsx               # Dashboard overview (SEO score, recent crawls)
  │   │   ├── crawls/
  │   │   │   ├── page.tsx           # Crawl list
  │   │   │   ├── new/page.tsx       # New crawl form
  │   │   │   └── [crawlId]/
  │   │   │       ├── page.tsx       # Crawl detail (main data grid)
  │   │   │       ├── loading.tsx    # Suspense skeleton
  │   │   │       ├── error.tsx      # Error boundary
  │   │   │       └── _components/   # Co-located client components
  │   │   │           ├── UrlDataGrid.tsx       # Virtual scrolling data grid
  │   │   │           ├── FilterPanel.tsx       # Dynamic filters
  │   │   │           ├── CrawlProgress.tsx     # Real-time WebSocket progress
  │   │   │           ├── TabPanel.tsx          # Top tabs (Internal, External, etc.)
  │   │   │           ├── DetailPanel.tsx       # Bottom panel (per-URL details)
  │   │   │           ├── RightSidebar.tsx      # Issues, structure, segments
  │   │   │           └── SerpPreview.tsx       # SERP snippet preview
  │   │   ├── reports/page.tsx
  │   │   ├── visualizations/page.tsx
  │   │   └── settings/
  │   │       ├── page.tsx           # General settings
  │   │       ├── profiles/page.tsx  # Configuration profiles
  │   │       └── integrations/page.tsx
  │   └── api/                       # Next.js Route Handlers (proxy to FastAPI)
  │       └── stream/[crawlId]/route.ts  # SSE endpoint
  ├── components/
  │   ├── ui/                        # shadcn/ui components
  │   ├── crawl/                     # Crawl-specific components
  │   ├── charts/                    # Recharts wrappers
  │   └── layout/                    # Shell, sidebar, topbar
  ├── hooks/
  │   ├── use-crawl-websocket.ts     # WebSocket hook with reconnection
  │   ├── use-crawl-data.ts          # TanStack Query crawl queries
  │   └── use-filters.ts            # Filter state management
  ├── lib/
  │   ├── api-client.ts             # Typed fetch wrapper for FastAPI
  │   ├── query-client.ts           # TanStack Query configuration
  │   └── utils.ts
  ├── stores/
  │   └── crawl-store.ts            # Zustand store for crawl UI state
  ├── types/
  │   └── index.ts                  # Shared TypeScript types
  └── package.json
  ```

  **4c. Backend Structure** (FastAPI, Router → Service → Repository pattern):
  ```
  backend/
  ├── app/
  │   ├── main.py                    # App factory, lifespan, middleware
  │   ├── api/
  │   │   ├── deps.py                # Shared dependencies (DB, Redis, auth)
  │   │   └── v1/
  │   │       ├── router.py          # Aggregates all v1 routers
  │   │       ├── crawls.py          # /crawls endpoints + WebSocket
  │   │       ├── urls.py            # /crawls/{id}/urls endpoints
  │   │       ├── issues.py          # /crawls/{id}/issues endpoints
  │   │       ├── reports.py         # /reports endpoints
  │   │       ├── projects.py        # /projects endpoints
  │   │       ├── configs.py         # /configs endpoints
  │   │       ├── extractors.py      # /extractors endpoints
  │   │       ├── integrations.py    # /integrations endpoints
  │   │       └── export.py          # /export endpoints
  │   ├── core/
  │   │   ├── config.py              # Pydantic Settings (env vars)
  │   │   ├── exceptions.py          # Custom exception handlers
  │   │   └── logging.py             # Structured logging (structlog)
  │   ├── crawler/
  │   │   ├── engine.py              # CrawlEngine (async event loop)
  │   │   ├── frontier.py            # URLFrontier (Redis sorted sets + Bloom filter)
  │   │   ├── fetcher.py             # FetcherPool (aiohttp, rate limiting)
  │   │   ├── parser.py              # ParserPool (selectolax + lxml)
  │   │   ├── analyzer.py            # SEOAnalyzer (pluggable analyzers)
  │   │   ├── renderer.py            # Playwright JS rendering
  │   │   └── robots.py              # robots.txt parser + cache
  │   ├── analysis/
  │   │   ├── titles.py              # TitleAnalyzer
  │   │   ├── meta.py                # MetaDescriptionAnalyzer
  │   │   ├── headings.py            # HeadingAnalyzer
  │   │   ├── links.py               # LinkAnalyzer
  │   │   ├── canonicals.py          # CanonicalAnalyzer
  │   │   ├── duplicates.py          # DuplicateContentAnalyzer (SimHash/MinHash)
  │   │   ├── structured_data.py     # StructuredDataValidator
  │   │   ├── accessibility.py       # AccessibilityAnalyzer (AXE)
  │   │   ├── security.py            # SecurityAnalyzer
  │   │   └── link_score.py          # LinkScoreCalculator (PageRank)
  │   ├── models/                    # SQLAlchemy ORM models
  │   │   ├── base.py
  │   │   ├── project.py
  │   │   ├── crawl.py
  │   │   ├── url.py
  │   │   └── ...
  │   ├── schemas/                   # Pydantic request/response schemas
  │   │   ├── crawl.py
  │   │   ├── url.py
  │   │   ├── pagination.py
  │   │   └── ...
  │   ├── repositories/              # DB query layer
  │   │   ├── base.py                # Generic CRUD base
  │   │   ├── crawl_repo.py
  │   │   ├── url_repo.py
  │   │   └── ...
  │   ├── services/                  # Business logic layer
  │   │   ├── crawl_service.py
  │   │   ├── analysis_service.py
  │   │   ├── report_service.py
  │   │   └── export_service.py
  │   ├── db/
  │   │   ├── session.py             # Async engine + session factory
  │   │   ├── migrations/            # Alembic migrations
  │   │   └── init.sql               # Extension setup (pgvector, pg_trgm)
  │   ├── worker/
  │   │   ├── settings.py            # ARQ WorkerSettings
  │   │   └── tasks/
  │   │       ├── crawl_tasks.py     # start_crawl, process_batch
  │   │       └── analysis_tasks.py  # post_crawl_analysis, link_score
  │   └── websocket/
  │       └── manager.py             # WebSocket manager (Redis pub/sub)
  ├── tests/
  │   ├── conftest.py                # Shared fixtures
  │   ├── unit/
  │   ├── api/
  │   ├── integration/
  │   └── crawler/
  ├── Dockerfile
  └── pyproject.toml
  ```

  **Must NOT do**:
  - Don't create actual files/directories (documentation only)
  - Don't add boilerplate code examples in the structure

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Tasks 10, 14
  - **Blocked By**: Task 1

  **References**:
  - `PLAN.md:836-868` — Current UI Layout section (use for frontend page mapping)
  - `PLAN.md:54-238` — Phase 1 features (maps to backend/crawler/ modules)
  - `PLAN.md:241-395` — Phase 2 features (maps to backend/analysis/ modules)
  - Research: FastAPI Router→Service→Repository pattern, Next.js 15 App Router conventions

  **Acceptance Criteria**:
  - [ ] Root, frontend, and backend directory trees present
  - [ ] Frontend has ≥ 20 files/directories listed with descriptions
  - [ ] Backend has ≥ 30 files/directories listed with descriptions
  - [ ] Every backend router file maps to a group of API endpoints
  - [ ] Every analysis module maps to a Phase 2 feature

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Project structure completeness
    Tool: Bash (grep)
    Steps:
      1. grep -c "├──\|└──" PLAN.md → Expected: ≥ 80 (tree entries)
      2. grep -c "frontend/" PLAN.md → Expected: ≥ 5
      3. grep -c "backend/" PLAN.md → Expected: ≥ 5
      4. grep -c ".tsx\|.ts" PLAN.md → Expected: ≥ 15 (TypeScript files)
      5. grep -c ".py" PLAN.md → Expected: ≥ 20 (Python files)
    Expected Result: Adequate file counts per layer
    Evidence: .sisyphus/evidence/task-4-structure.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add complete project structure for frontend and backend`
  - Files: `PLAN.md`

---

- [ ] 5. Add Crawler Engine Deep Dive

  **What to do**:
  - Read current PLAN.md
  - Add a new section "## Crawler Engine — Technical Deep Dive" after the new Database Schema section
  - Include:

  **5a. URL Frontier Architecture**:
  - Two-level queue design: front queues (priority tiers 0-2) + back queues (per-domain FIFO with rate limiting)
  - Redis sorted sets (ZADD/ZPOPMIN) for O(log N) operations
  - Bloom filter for URL deduplication (ScalableBloomFilter, initial_capacity=100k, error_rate=0.001, ~12MB per 1M URLs)
  - URL normalization algorithm: lowercase, strip fragments, decode percent-encoding, normalize trailing slashes, handle IDN/punycode, ignore data:/javascript:/mailto: URIs

  **5b. Fetcher Pool Design**:
  - aiohttp TCPConnector: limit=100 total, limit_per_host=5, ttl_dns_cache=300, keepalive_timeout=30
  - Per-domain rate limiter: respect robots.txt Crawl-delay, minimum 1s between requests to same domain
  - Redirect handling: manual (don't auto-follow), track each hop, detect loops, max 10 hops
  - Timeout strategy: total=30s, connect=10s, sock_read=20s
  - Retry with exponential backoff: delay = min(2^attempt, 60s), max 3 retries
  - Anti-bot handling: document behavior for 429 (backoff), Cloudflare challenges (skip + log), CAPTCHAs (skip + report)

  **5c. Parser Pipeline**:
  - Primary parser: selectolax (HTMLParser) — 35x faster than BS4
  - Secondary parser: lxml — for XPath queries (Feature 4.1 Custom Extraction requires XPath 1.0-3.1)
  - Extraction order: title, meta_desc, h1/h2, canonical, robots_meta, links (a[href]), images (img[src+srcset]), structured data (script[type="application/ld+json"]), hreflang (link[rel="alternate"][hreflang])
  - Content cleanup: decompose script/style/noscript before word count
  - Content hashing: SimHash for near-duplicate comparison, MD5 for exact duplicate

  **5d. SEO Analyzer Pipeline** (pluggable architecture):
  - List all analyzer modules with what they check:
    - TitleAnalyzer: missing, too long (>60 chars / >580px), too short (<30 chars), duplicate, same as H1, multiple, outside head
    - MetaDescriptionAnalyzer: missing, too long (>155 chars / >920px), too short (<70 chars), duplicate, multiple
    - HeadingAnalyzer: missing H1, multiple H1, H1 same as title, non-sequential headings
    - LinkAnalyzer: broken (4XX/5XX), redirect chains, nofollow internal, orphan detection
    - CanonicalAnalyzer: missing, self-referencing, non-indexable target, mismatch, multiple
    - SecurityAnalyzer: HTTP URLs, mixed content, missing HSTS/CSP/X-Frame-Options
    - ImageAnalyzer: missing alt, alt too long, oversized, missing dimensions
  - Each analyzer returns list of Issue objects: { type, severity, details }
  - Analyzers run inline during crawl (streaming) — not batch after

  **5e. Batch Inserter**:
  - asyncpg COPY for 50k rows/sec throughput
  - Buffer: accumulate 500 rows OR 2 seconds, whichever comes first
  - Flush on crawl pause/stop/complete
  - Error handling: if batch fails, retry individual rows to isolate bad data

  **5f. Post-Crawl Analysis** (runs after crawl completes):
  - Link Score calculation: PageRank algorithm, D=0.85, 10 iterations
  - Near-duplicate detection: MinHash with k=128, bands=8, rows=16, threshold=90%
  - Orphan page detection: URLs in sitemap/GA/GSC but not in crawl link graph
  - Sitemap cross-reference: match crawled URLs against uploaded sitemaps

  **Must NOT do**:
  - Don't include working Python code (pseudocode and algorithm descriptions only)
  - Don't duplicate content from feature descriptions (reference them instead)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Tasks 8, 14
  - **Blocked By**: Task 2

  **References**:
  - `PLAN.md:58-77` — Feature 1.1 Spider Mode (BFS, asyncio, aiohttp, Redis queue)
  - `PLAN.md:116-128` — Feature 1.4 JS Rendering (Playwright modes, viewport, AJAX timeout)
  - `PLAN.md:130-145` — Feature 1.5 HTTP Response Handling (status codes, redirects, retries)
  - `PLAN.md:173-186` — Feature 1.8 Crawl Limits (threads, rate, URLs)
  - `PLAN.md:340-357` — Feature 2.12 Duplicate Detection (MD5, MinHash, similarity threshold)
  - `PLAN.md:459-469` — Feature 3.6 Link Score (PageRank formula, D=0.85, 10 iterations)
  - Research: selectolax benchmarks, Bloom filter sizing, two-level frontier design, asyncpg COPY

  **Acceptance Criteria**:
  - [ ] URL Frontier section with Bloom filter sizing math
  - [ ] Fetcher Pool with all timeout/retry/rate-limit values
  - [ ] Parser pipeline with selectolax + lxml dual-parser explanation
  - [ ] SEO Analyzer lists ≥ 7 analyzer modules with specific checks
  - [ ] Batch Inserter with buffer strategy
  - [ ] Post-crawl analysis with algorithm parameters (MinHash k/bands/rows)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Crawler engine section completeness
    Tool: Bash (grep)
    Steps:
      1. grep -c "Bloom filter\|BloomFilter" PLAN.md → Expected: ≥ 2
      2. grep -c "selectolax\|lxml" PLAN.md → Expected: ≥ 3
      3. grep -c "MinHash\|SimHash" PLAN.md → Expected: ≥ 2
      4. grep -c "asyncpg\|COPY" PLAN.md → Expected: ≥ 2
      5. grep -c "rate.limit\|Crawl-delay\|per-domain" PLAN.md → Expected: ≥ 2
    Expected Result: All key algorithms documented
    Evidence: .sisyphus/evidence/task-5-crawler.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add crawler engine deep dive with algorithms and data structures`
  - Files: `PLAN.md`

---

- [ ] 6. Add WebSocket Protocol Specification

  **What to do**:
  - Read current PLAN.md
  - Add a new section "## WebSocket Protocol" after the Crawler Engine section
  - Include:

  **6a. Architecture**:
  ```
  Crawler Workers → Redis Pub/Sub (channel: crawl:{id}:events) → FastAPI WebSocketManager → Client
  ```
  - Why Redis pub/sub in the middle: decouples crawler (may be separate process) from WS connections
  - Multiple FastAPI instances can subscribe to same channel (horizontal scaling)
  - Per-client bounded queue (maxsize=100) for backpressure

  **6b. Connection Protocol**:
  - Endpoint: `ws://localhost:8000/api/v1/crawls/{crawlId}/ws`
  - Heartbeat: server sends `{"type":"ping"}` every 30s; client responds `{"type":"pong"}`
  - No pong in 60s → server closes connection
  - Client reconnection: exponential backoff (1s, 2s, 4s, 8s, max 30s), reset on successful connect

  **6c. Message Types** (JSON schema for each):
  ```json
  // Server → Client
  { "type": "progress", "data": { "crawled": 1250, "queued": 3750, "errors": 12, "rate": 23.5, "elapsed_ms": 54000 } }
  { "type": "page_crawled", "data": { "url": "...", "status_code": 200, "title": "...", "issues_count": 3 } }
  { "type": "issue_found", "data": { "url": "...", "issue_type": "missing_title", "severity": "warning" } }
  { "type": "state_change", "data": { "from": "crawling", "to": "paused" } }
  { "type": "crawl_complete", "data": { "total_urls": 5000, "total_issues": 142, "duration_ms": 240000 } }
  { "type": "error", "data": { "message": "Connection refused", "url": "..." } }
  { "type": "ping" }

  // Client → Server
  { "type": "pong" }
  { "type": "command", "action": "pause" | "resume" | "stop" }
  ```

  **6d. Backpressure Strategy**:
  - Server-side: bounded asyncio.Queue per client (maxsize=100)
  - If queue full: drop oldest event, add newest (sliding window)
  - Client-side: keep last 500 events in React state (ring buffer)
  - Progress events throttled: max 1 per 500ms (aggregate in Redis)

  **6e. Frontend Hook Pattern**:
  - `useCrawlWebSocket(crawlId)` — returns { events, isConnected, lastProgress }
  - Uses `useRef` for WebSocket instance, `useState` for events
  - Cleanup on unmount: close WebSocket
  - Reconnection on `onclose` event (not `onerror`)

  **Must NOT do**:
  - Don't include full React/Python code implementations
  - Don't add authentication to WebSocket (V1 is single-user)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Tasks 7, 14
  - **Blocked By**: Task 2

  **References**:
  - `PLAN.md:77` — "WebSocket push updates ไป frontend ทุก 500ms"
  - `PLAN.md:67-68` — "Real-time progress bar, Pause/Resume/Stop controls"
  - Research: Redis pub/sub → FastAPI WebSocket manager pattern, backpressure with bounded queues
  - Research: Next.js useCrawlWebSocket hook with exponential backoff

  **Acceptance Criteria**:
  - [ ] Architecture diagram showing Redis pub/sub → WS Manager → Client
  - [ ] ≥ 6 message types defined with JSON schemas
  - [ ] Heartbeat strategy documented (30s ping, 60s timeout)
  - [ ] Reconnection strategy with backoff values
  - [ ] Backpressure mechanism documented (bounded queue, drop oldest)
  - [ ] Client → Server command messages (pause/resume/stop)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: WebSocket protocol section completeness
    Tool: Bash (grep)
    Steps:
      1. grep -c '"type":' PLAN.md → Expected: ≥ 8 (message examples)
      2. grep -c "heartbeat\|ping\|pong" PLAN.md → Expected: ≥ 3
      3. grep -c "backpressure\|bounded queue" PLAN.md → Expected: ≥ 2
      4. grep -c "reconnect\|backoff" PLAN.md → Expected: ≥ 2
    Expected Result: Protocol fully specified
    Evidence: .sisyphus/evidence/task-6-websocket.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add WebSocket protocol spec with message types and backpressure`
  - Files: `PLAN.md`

---

### Wave 3 — Dependent Specs (parallel: T7, T8, T9 — depend on Wave 1-2)

- [ ] 7. Add API Specification

  **What to do**:
  - Read current PLAN.md (especially the new DB Schema and WebSocket Protocol sections)
  - Add a new section "## API Specification" after the WebSocket Protocol section
  - Include ALL endpoints grouped by resource, with method, path, request body, response body, and notes

  **7a. Design Principles**:
  - Base URL: `/api/v1/`
  - Pagination: Keyset/cursor-based (NOT OFFSET) — O(1) at any depth
  - Filtering: Query parameters per field (e.g., `?status_code=404&is_indexable=false`)
  - Sorting: `?sort_by=response_time_ms&sort_dir=desc`
  - Error responses: `{ "detail": "string", "code": "string", "errors": [...] }`
  - Rate limiting: None for V1 (single-user, local)

  **7b. Endpoint Groups** (each endpoint needs: method, path, request schema, response schema, notes):

  **Projects** (5 endpoints):
  - POST /projects — Create project { name, domain }
  - GET /projects — List projects (cursor pagination)
  - GET /projects/{id} — Get project detail
  - PUT /projects/{id} — Update project
  - DELETE /projects/{id} — Delete project + all crawls

  **Crawls** (8 endpoints + 1 WebSocket):
  - POST /projects/{id}/crawls — Start new crawl { start_url, mode, config }
  - GET /projects/{id}/crawls — List crawls for project
  - GET /crawls/{id} — Get crawl detail (status, progress, config)
  - POST /crawls/{id}/pause — Pause crawl
  - POST /crawls/{id}/resume — Resume crawl
  - POST /crawls/{id}/stop — Stop crawl
  - DELETE /crawls/{id} — Delete crawl + all data
  - GET /crawls/{id}/summary — Aggregated dashboard data (status code distribution, issue counts, top issues)
  - WS /crawls/{id}/ws — WebSocket for real-time updates (reference Protocol section)

  **URLs** (4 endpoints):
  - GET /crawls/{id}/urls — List crawled URLs (cursor pagination, filters, sorting)
  - GET /crawls/{id}/urls/{urlId} — Get URL detail (all SEO data, seo_data JSONB expanded)
  - GET /crawls/{id}/urls/{urlId}/inlinks — Inbound links to this URL
  - GET /crawls/{id}/urls/{urlId}/outlinks — Outbound links from this URL

  **Issues** (3 endpoints):
  - GET /crawls/{id}/issues — List issues (group by type, filter by severity)
  - GET /crawls/{id}/issues/summary — Issue counts by type and severity
  - GET /crawls/{id}/issues/{issueType}/urls — URLs affected by specific issue

  **Analysis** (6 endpoints):
  - GET /crawls/{id}/duplicates — Duplicate content pairs (exact + near)
  - GET /crawls/{id}/redirects — Redirect chains
  - GET /crawls/{id}/orphans — Orphan pages
  - GET /crawls/{id}/link-scores — Link scores (PageRank)
  - GET /crawls/{id}/structured-data — Structured data validation
  - GET /crawls/{id}/accessibility — Accessibility violations

  **Configuration** (5 endpoints):
  - GET /configs — List saved configurations
  - POST /configs — Save configuration { name, config_data }
  - GET /configs/{id} — Get configuration
  - PUT /configs/{id} — Update configuration
  - DELETE /configs/{id} — Delete configuration

  **Custom Extraction** (4 endpoints):
  - GET /crawls/{id}/extractors — List extractors
  - POST /crawls/{id}/extractors — Add extractor { name, method, selector }
  - GET /crawls/{id}/extractions — Get extraction results
  - POST /crawls/{id}/extractors/test — Test extractor on single URL

  **Custom Search** (3 endpoints):
  - GET /crawls/{id}/searches — List custom searches
  - POST /crawls/{id}/searches — Add search pattern { name, pattern, contains }
  - GET /crawls/{id}/search-results — Get search results

  **AI Integration** (4 endpoints):
  - GET /prompts — List saved prompts
  - POST /prompts — Save prompt { name, model, prompt_text, content_type }
  - POST /crawls/{id}/ai/run — Run AI prompts on crawl data
  - GET /crawls/{id}/ai/results — Get AI results

  **Reports & Export** (5 endpoints):
  - GET /crawls/{id}/reports/{type} — Get report (crawl-overview, serp-summary, redirect-chains, etc.)
  - POST /crawls/{id}/export — Export data { format: csv|xlsx, tab, filters }
  - GET /crawls/{id}/sitemap/generate — Generate XML sitemap
  - POST /crawls/{id}/compare/{otherId} — Compare two crawls
  - GET /crawls/{id}/visualizations/{type} — Get visualization data (force-directed, tree)

  **Integrations** (4 endpoints):
  - POST /integrations/ga/connect — Connect Google Analytics
  - POST /integrations/gsc/connect — Connect Google Search Console
  - POST /integrations/psi/fetch — Fetch PageSpeed Insights
  - POST /integrations/links/fetch — Fetch Ahrefs/Moz metrics

  **System** (2 endpoints):
  - GET /health — Health check (DB, Redis, Playwright status)
  - GET /system/info — System info (version, storage used, active crawls)

  **7c. Pagination Schema** (used across all list endpoints):
  ```json
  // Request: ?cursor=eyJpZCI6MTIzfQ&limit=100&sort_by=id&sort_dir=asc
  // Response:
  {
    "items": [...],
    "next_cursor": "eyJpZCI6MjIzfQ" | null,
    "prev_cursor": "eyJpZCI6MTIzfQ" | null,
    "total": 5000  // optional, expensive
  }
  ```

  **7d. Error Response Schema**:
  ```json
  {
    "detail": "Crawl not found",
    "code": "CRAWL_NOT_FOUND",
    "status": 404
  }
  ```

  **Must NOT do**:
  - Don't write OpenAPI/Swagger YAML (text descriptions with JSON examples are sufficient)
  - Don't add authentication endpoints (V1 is single-user)
  - Don't add user management endpoints

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: Tasks 10, 14
  - **Blocked By**: Tasks 3, 6

  **References**:
  - `PLAN.md` (new DB Schema section from Task 3) — column names must match response fields
  - `PLAN.md` (new WebSocket section from Task 6) — WS endpoint referenced here
  - `PLAN.md:637-655` — Feature 5.1 Export System (3 export methods, bulk categories)
  - `PLAN.md:656-665` — Feature 5.2 Reports (12 report types)
  - `PLAN.md:595-612` — Features 4.5-4.8 (integration endpoints)
  - Research: Keyset pagination pattern, filtering/sorting API design

  **Acceptance Criteria**:
  - [ ] ≥ 50 endpoints defined (method + path + description)
  - [ ] ≥ 10 endpoints with full request/response JSON schemas
  - [ ] Pagination schema documented with cursor pattern
  - [ ] Error response schema documented
  - [ ] Every endpoint references its DB table (from Task 3 schema)
  - [ ] WebSocket endpoint cross-references Task 6 protocol

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: API specification completeness
    Tool: Bash (grep)
    Steps:
      1. grep -c "GET \|POST \|PUT \|DELETE \|PATCH \|WS " PLAN.md → Expected: ≥ 50
      2. grep -c "/api/v1/" PLAN.md → Expected: ≥ 20
      3. grep -c "cursor\|pagination" PLAN.md → Expected: ≥ 3
      4. grep -c "response.*:" PLAN.md → Expected: ≥ 10
    Expected Result: All endpoint categories covered
    Evidence: .sisyphus/evidence/task-7-api.txt

  Scenario: DB↔API cross-reference check
    Tool: Bash (grep)
    Steps:
      1. Verify key DB table names appear near their API endpoints
      2. grep "crawled_urls\|page_links\|url_issues" PLAN.md → Expected: appears in both schema and API sections
    Expected Result: No orphaned references
    Evidence: .sisyphus/evidence/task-7-crossref.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add API specification with 50+ endpoints and schemas`
  - Files: `PLAN.md`

---

- [ ] 8. Add Performance Strategy & Targets

  **What to do**:
  - Read current PLAN.md (especially Crawler Engine and DB Schema sections)
  - Add a new section "## Performance Strategy" after the API Specification section
  - Include:

  **8a. Performance Targets**:
  | Metric | Target | Measurement Method |
  |--------|--------|--------------------|
  | Crawl throughput | 20-50 pages/sec | URLs crawled / elapsed time |
  | API response (p95) | < 200ms | FastAPI middleware timer |
  | API response (p99) | < 500ms | Same |
  | Frontend interaction | < 100ms | Lighthouse TBT |
  | WebSocket latency | < 100ms | Event timestamp delta |
  | Memory (100k URLs) | < 2GB | Docker stats |
  | Memory (1M URLs) | < 8GB | Docker stats |
  | DB query (filtered) | < 50ms | EXPLAIN ANALYZE |
  | Data grid render | < 200ms | React Profiler |
  | Bloom filter memory | ~12MB/1M URLs | pybloom-live stats |

  **8b. Scaling Strategy**:
  - Vertical: Increase threads (1-20), increase DB pool size, add Redis memory
  - Horizontal: ARQ workers can scale independently (Docker replicas)
  - Data: PostgreSQL HASH partitioning (16 partitions for crawled_urls)
  - Frontend: Virtual scrolling (react-virtual) — only render visible rows

  **8c. Optimization Techniques**:
  - HTTP: DNS caching (ttl_dns_cache=300), connection keep-alive, gzip/brotli compression
  - Parsing: selectolax (35x faster than BS4), decompose script/style before processing
  - DB: asyncpg COPY for bulk inserts, partial indexes (WHERE status_code >= 400), materialized views for dashboard
  - Frontend: Server Components for initial load (zero JS), TanStack Query staleTime=30s, debounced filters
  - Redis: Pipeline commands (batch ZADD), Pub/Sub for event fan-out instead of polling
  - Crawl: Bloom filter for O(k) URL dedup vs O(n) set lookup

  **8d. Memory Management**:
  - Bloom filter: persisted to Redis blob every 1000 URLs for crash recovery
  - HTML content: stream-parse, don't load full page into memory
  - Data grid: cursor pagination (never load all rows into frontend memory)
  - Crawl results: batch insert → don't accumulate in Python memory

  **Must NOT do**:
  - Don't include benchmark results or load test scripts
  - Don't add monitoring tools (Prometheus/Grafana)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 9)
  - **Blocks**: Task 14
  - **Blocked By**: Task 5

  **References**:
  - Task 5 (Crawler Engine) — throughput depends on fetcher/parser design
  - Task 3 (DB Schema) — query performance depends on indexes
  - Research: selectolax 35x benchmark, asyncpg COPY 50k rows/sec, Bloom filter 12MB/1M

  **Acceptance Criteria**:
  - [ ] ≥ 10 performance targets with specific numbers
  - [ ] Scaling strategy covers vertical + horizontal + data
  - [ ] ≥ 6 optimization techniques with rationale
  - [ ] Memory management section for Bloom filter, HTML, data grid, crawl results

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Performance targets present
    Tool: Bash (grep)
    Steps:
      1. grep -c "pages/sec\|ms\|MB\|GB" PLAN.md → Expected: ≥ 10
      2. grep -c "p95\|p99\|latency\|throughput" PLAN.md → Expected: ≥ 4
    Expected Result: Concrete numeric targets documented
    Evidence: .sisyphus/evidence/task-8-performance.txt
  ```

  **Commit**: YES (group with Task 9)
  - Message: `docs(plan): add performance strategy and error handling`
  - Files: `PLAN.md`

---

- [ ] 9. Add Error Handling Strategy

  **What to do**:
  - Read current PLAN.md
  - Add a new section "## Error Handling Strategy" after Performance Strategy
  - Include:

  **9a. Error Categories**:
  | Category | Examples | Strategy |
  |----------|----------|----------|
  | Network errors | Connection refused, DNS failure, timeout | Retry 3x with exponential backoff |
  | HTTP errors | 4XX client errors, 5XX server errors | Log + continue crawl (don't stop) |
  | Parse errors | Malformed HTML, encoding issues | Use best-effort parsing, log warning |
  | Database errors | Connection pool exhausted, deadlock | Retry once, then fail job with alert |
  | Redis errors | Connection lost | Reconnect with backoff, buffer in memory temporarily |
  | Playwright errors | Browser crash, timeout | Restart browser instance, retry page |
  | Rate limit (429) | Target site rate limiting | Exponential backoff for that domain |

  **9b. Retry Policy**:
  - Default: 3 retries with exponential backoff (1s, 2s, 4s)
  - 429 responses: domain-specific backoff (30s, 60s, 120s)
  - 5XX responses: 2 retries (may be temporary server error)
  - Timeout: 2 retries with increased timeout (30s → 45s → 60s)
  - Dead letter: URLs that fail 3x go to `crawl_errors` table, not re-queued

  **9c. Circuit Breaker** (per domain):
  - If > 50% of requests to a domain fail in last 60s → circuit OPEN
  - OPEN state: skip domain for 120s, log warning
  - After cooldown → HALF-OPEN: try 1 request
  - If succeeds → CLOSED, resume normal crawling
  - If fails → OPEN again, double cooldown

  **9d. Graceful Degradation**:
  - Playwright crashes → fall back to text-only mode for that URL
  - LanguageTool unavailable → skip spelling check, don't block crawl
  - Redis connection lost → buffer events in memory, reconnect with backoff
  - Database slow → increase batch size, reduce flush frequency

  **9e. Crawl Recovery**:
  - Checkpoint: every 1000 URLs, snapshot frontier state to PostgreSQL
  - On crash: reload frontier from PostgreSQL checkpoint + already-crawled URLs
  - On resume: skip already-crawled URLs (check url_hash in DB)

  **Must NOT do**:
  - Don't add alerting/notification system
  - Don't add logging infrastructure (structlog configuration)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 8)
  - **Blocks**: Task 14
  - **Blocked By**: Task 2

  **References**:
  - `PLAN.md:130-145` — Feature 1.5 HTTP Response Handling (status codes, retries)
  - `PLAN.md:116-128` — Feature 1.4 JS Rendering (Playwright timeouts)
  - Research: retry with exponential backoff, circuit breaker pattern, dead letter queue

  **Acceptance Criteria**:
  - [ ] ≥ 7 error categories with strategy for each
  - [ ] Retry policy with specific values (attempts, delays)
  - [ ] Circuit breaker with threshold values and state transitions
  - [ ] Graceful degradation for 4+ failure scenarios
  - [ ] Crawl recovery/checkpoint mechanism

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Error handling section completeness
    Tool: Bash (grep)
    Steps:
      1. grep -c "retry\|Retry" PLAN.md → Expected: ≥ 5
      2. grep -c "circuit.breaker\|Circuit Breaker" PLAN.md → Expected: ≥ 2
      3. grep -c "dead.letter\|checkpoint\|recovery" PLAN.md → Expected: ≥ 3
      4. grep -c "graceful\|fallback\|degrad" PLAN.md → Expected: ≥ 3
    Expected Result: All error handling patterns documented
    Evidence: .sisyphus/evidence/task-9-errors.txt
  ```

  **Commit**: YES (grouped with Task 8)
  - Message: `docs(plan): add performance strategy and error handling`
  - Files: `PLAN.md`

---

### Wave 4 — Infrastructure (parallel: T10, T11)

- [ ] 10. Add Testing Strategy

  **What to do**:
  - Read current PLAN.md (especially Project Structure and API Specification)
  - Add a new section "## Testing Strategy" after Error Handling
  - Include:

  **10a. Test Pyramid**:
  | Level | Count Target | Tools | What to Test |
  |-------|-------------|-------|-------------|
  | Unit | 80% coverage | pytest, vitest | Algorithms (URL normalization, SimHash, Link Score), analyzers, parsers |
  | API | Every endpoint | pytest + httpx | Request validation, response schemas, error codes, pagination |
  | Integration | Critical paths | pytest + testcontainers | Crawl→Parse→Store pipeline, DB transactions, Redis pub/sub |
  | E2E | Key workflows | Playwright | Full crawl flow, data grid interaction, export |
  | Crawler | Mock HTTP | pytest + respx | Redirect chains, error handling, robots.txt respect |

  **10b. Backend Testing Patterns**:
  - Fixtures: async DB session with transaction rollback (no cleanup needed)
  - Mocking HTTP: `respx` library for aiohttp/httpx mock responses
  - Factory pattern: `CrawlFactory`, `UrlFactory` for test data generation
  - Test DB: testcontainers-python for ephemeral PostgreSQL

  **10c. Frontend Testing Patterns**:
  - Component tests: vitest + @testing-library/react
  - API mocking: MSW (Mock Service Worker) for intercepting fetch
  - E2E: Playwright with `data-testid` selectors

  **10d. Crawler-Specific Testing**:
  - Mock HTTP server with predefined responses (redirects, errors, large pages)
  - Bloom filter accuracy tests (insert N URLs, verify false positive rate)
  - Rate limiter timing tests
  - Parser extraction accuracy tests (known HTML → expected data)

  **10e. CI Pipeline** (high-level):
  - On PR: lint → type check → unit tests → API tests
  - On merge to main: integration tests → E2E tests → build Docker images

  **Must NOT do**:
  - Don't include actual test code (patterns and examples only)
  - Don't add CI/CD configuration files (GitHub Actions YAML)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 11)
  - **Blocks**: Task 14
  - **Blocked By**: Tasks 4, 7

  **References**:
  - Task 4 (Project Structure) — test directory structure to reference
  - Task 7 (API Specification) — endpoints to test
  - Research: pytest fixtures with transaction rollback, respx for crawler mocking, MSW for frontend

  **Acceptance Criteria**:
  - [ ] Test pyramid with 5 levels and count targets
  - [ ] Backend testing patterns with fixtures, mocking, factories
  - [ ] Frontend testing patterns with MSW
  - [ ] Crawler-specific testing approach
  - [ ] CI pipeline outline

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Testing strategy present
    Tool: Bash (grep)
    Steps:
      1. grep -c "pytest\|vitest\|Playwright" PLAN.md → Expected: ≥ 5
      2. grep -c "mock\|Mock\|MSW\|respx" PLAN.md → Expected: ≥ 3
      3. grep -c "coverage\|CI\|pipeline" PLAN.md → Expected: ≥ 3
    Expected Result: Testing tools and patterns specified
    Evidence: .sisyphus/evidence/task-10-testing.txt
  ```

  **Commit**: YES (grouped with Task 11)
  - Message: `docs(plan): add testing strategy and Docker Compose configuration`
  - Files: `PLAN.md`

---

- [ ] 11. Add Docker Compose Configuration

  **What to do**:
  - Read current PLAN.md
  - Replace/expand the "Quick Start" section (lines ~907-920) with a full "## Docker Compose & Deployment" section
  - Include:

  **11a. Complete docker-compose.yml** (documented YAML with comments):
  - **frontend**: Next.js, port 3000, depends on backend, environment vars
  - **backend**: FastAPI via gunicorn+uvicorn, port 8000, depends on db+redis, health check
  - **worker**: ARQ worker (same image as backend, different command), replicas: 2
  - **db**: postgres:16-alpine, health check, tuned settings (shared_buffers=256MB, work_mem=4MB), volume mount
  - **redis**: redis:7-alpine, maxmemory=512mb, appendonly=yes, health check, volume
  - **nginx**: reverse proxy, port 80, WebSocket upgrade config, routes /api→backend, /→frontend
  - **playwright**: headless Chromium service for JS rendering (optional, can be embedded in worker)
  - Volumes: postgres_data, redis_data
  - Network: app-network (bridge)

  **11b. Dockerfiles** (high-level, not full files):
  - Frontend: multi-stage (deps → builder → runner), standalone output, non-root user
  - Backend: python:3.12-slim, uv for package management, non-root user

  **11c. Environment Variables** (.env.example):
  ```
  POSTGRES_DB=seo_spider
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=changeme
  DATABASE_URL=postgresql+asyncpg://postgres:changeme@db:5432/seo_spider
  REDIS_URL=redis://redis:6379
  NEXT_PUBLIC_API_URL=http://localhost/api
  API_URL=http://backend:8000
  OPENAI_API_KEY=  # Optional: for AI features
  ```

  **11d. Health Checks** (per service):
  - backend: `curl -f http://localhost:8000/health`
  - db: `pg_isready -U postgres`
  - redis: `redis-cli ping`

  **11e. Development Setup**:
  - docker-compose.dev.yml override for hot reload
  - Volume mounts for source code
  - Port mappings for direct access

  **Must NOT do**:
  - Don't add Kubernetes manifests
  - Don't add TLS/SSL configuration
  - Don't add secrets management (Vault, etc.)
  - Don't add monitoring stack (Prometheus/Grafana)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 10)
  - **Blocks**: Task 14
  - **Blocked By**: Task 1

  **References**:
  - `PLAN.md:907-920` — Current Quick Start section to expand
  - Research: Docker Compose multi-service setup with health checks, Nginx reverse proxy, multi-stage Dockerfiles

  **Acceptance Criteria**:
  - [ ] Complete docker-compose.yml with ≥ 6 services
  - [ ] Health checks for backend, db, redis
  - [ ] Environment variables documented (.env.example)
  - [ ] Multi-stage Dockerfile descriptions for frontend and backend
  - [ ] Development override (docker-compose.dev.yml) mentioned

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Docker configuration present
    Tool: Bash (grep)
    Steps:
      1. grep -c "services:\|image:\|build:" PLAN.md → Expected: ≥ 6
      2. grep -c "healthcheck\|health_check" PLAN.md → Expected: ≥ 3
      3. grep -c "volumes:\|POSTGRES\|REDIS" PLAN.md → Expected: ≥ 5
      4. grep -c ".env\|environment:" PLAN.md → Expected: ≥ 3
    Expected Result: Docker setup fully specified
    Evidence: .sisyphus/evidence/task-11-docker.txt
  ```

  **Commit**: YES (grouped with Task 10)
  - Message: `docs(plan): add testing strategy and Docker Compose configuration`
  - Files: `PLAN.md`

---

### Wave 5 — Feature Updates (sequential: T12 → T13)

- [ ] 12. Update Existing Feature Descriptions with Tech Changes

  **What to do**:
  - Read current PLAN.md
  - Update ONLY the following in existing feature descriptions:
    1. Feature 1.1 (Spider Mode): Change "BeautifulSoup4 + lxml" → "selectolax (primary) + lxml (XPath fallback)"
    2. Feature 1.1: Change "Redis + Celery" pattern references → "Redis + ARQ"
    3. Feature 1.1: Add note about asyncpg for bulk inserts
    4. Feature 1.1: Add note about Bloom filter for URL deduplication
    5. Feature 1.4 (JS Rendering): No change needed (Playwright stays)
    6. Feature 2.12 (Duplicate Detection): Add "SimHash for near-duplicates" alongside MinHash
    7. Feature 3.9 (Spelling): Add "LanguageTool runs as separate Docker service"
    8. Feature 4.1 (Custom Extraction): Add "XPath queries use lxml backend; CSS queries use selectolax"
    9. Feature 6.5 (Collaboration): Add note "Deferred to V2 — V1 is single-user"
  - Add brief "**Implementation Note**" sub-section to Phase 1 features ONLY (not all 57)

  **Must NOT do**:
  - Don't rewrite Thai descriptions (preserve existing text)
  - Don't change feature scope or add sub-features
  - Don't add implementation notes to Phase 2-6 features (keep scope bounded)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (sequential with Task 13)
  - **Blocks**: Tasks 13, 14
  - **Blocked By**: Task 1

  **References**:
  - `PLAN.md:58-238` — Phase 1 features to update
  - `PLAN.md:340-357` — Feature 2.12 to update
  - `PLAN.md:500-513` — Feature 3.9 to update
  - `PLAN.md:535-547` — Feature 4.1 to update
  - `PLAN.md:772-779` — Feature 6.5 to update
  - `.sisyphus/drafts/plan-improvement.md` — Tech stack changes list

  **Acceptance Criteria**:
  - [ ] "selectolax" appears in Feature 1.1
  - [ ] "ARQ" appears in Feature 1.1 (replacing Celery references)
  - [ ] "lxml" mentioned alongside selectolax for XPath
  - [ ] Feature 6.5 marked as "Deferred to V2"
  - [ ] Existing Thai text preserved (only additions, no rewrites)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Tech references updated
    Tool: Bash (grep)
    Steps:
      1. grep -n "selectolax" PLAN.md → Expected: appears in Feature 1.1 area (lines 58-77)
      2. grep -n "ARQ" PLAN.md → Expected: appears in Feature 1.1 area
      3. grep -n "Deferred to V2\|V2" PLAN.md → Expected: appears near Feature 6.5 (lines 772-779)
      4. grep -c "BeautifulSoup4" PLAN.md → Expected: 0 (fully replaced)
      5. grep -c "Celery" PLAN.md → Expected: 0 (fully replaced)
    Expected Result: All tech references updated, old ones removed
    Evidence: .sisyphus/evidence/task-12-updates.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): update feature descriptions with new tech stack (selectolax, ARQ, asyncpg)`
  - Files: `PLAN.md`

---

- [ ] 13. Add 5 Missing Features

  **What to do**:
  - Read current PLAN.md
  - Add exactly 5 new features to Phase 3 (Advanced Analysis) section, AFTER existing Feature 3.10
  - Use the SAME format as existing features (Thai description + English technical details + reference URLs)
  - The 5 features to add:

  **Feature 3.11: PDF Audit**:
  - Extract text from PDFs (pdfplumber/PyMuPDF)
  - Detect links within PDFs
  - Check PDF metadata (title, author, keywords)
  - Check PDF file size
  - Reference: https://www.screamingfrog.co.uk/seo-spider/tutorials/how-to-audit-pdfs/

  **Feature 3.12: Cookie Audit**:
  - Detect cookies set by each URL (first-party + third-party)
  - Check Secure flag, HttpOnly flag, SameSite attribute
  - GDPR compliance indicators
  - Cookie size and count
  - Reference: https://www.screamingfrog.co.uk/seo-spider/tutorials/how-to-perform-a-cookie-audit/

  **Feature 3.13: Pagination Audit**:
  - Detect rel="next"/rel="prev" tags
  - Validate pagination sequences (no gaps, no loops)
  - Identify infinite scroll patterns (JS-loaded)
  - Cross-reference with canonicals
  - Reference: https://www.screamingfrog.co.uk/seo-spider/tutorials/how-to-audit-pagination/

  **Feature 3.14: Mobile Usability Check**:
  - Viewport meta tag detection
  - Touch target size validation (≥ 48x48 CSS pixels)
  - Font size validation (≥ 12px)
  - Content wider than viewport detection
  - Responsive design indicators
  - Reference: Related to PSI integration + Lighthouse mobile audit

  **Feature 3.15: Core Web Vitals Measurement**:
  - Measure LCP, CLS, INP directly using Playwright + PerformanceObserver
  - Not just PSI API data — actual measurement from headless browser
  - Compare field data (CrUX via PSI) vs lab data (Playwright measurement)
  - Filters: Poor CWV, Needs Improvement, Good
  - Reference: https://www.screamingfrog.co.uk/seo-spider/tutorials/how-to-audit-core-web-vitals/

  **Must NOT do**:
  - Don't add more than 5 features
  - Don't add features to other phases (only Phase 3)
  - Don't change existing feature numbering

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (sequential after Task 12)
  - **Blocks**: Task 14
  - **Blocked By**: Task 12

  **References**:
  - `PLAN.md:517-530` — Feature 3.10 (Crawl Comparison) — insertion point for new features
  - `PLAN.md:58-77` — Feature 1.1 format to follow (Thai desc + English tech + reference URL)
  - Screaming Frog tutorials for each feature (URLs listed above)

  **Acceptance Criteria**:
  - [ ] Exactly 5 new features added (3.11-3.15)
  - [ ] Each feature has: Thai description, English technical details, reference URL
  - [ ] Each feature follows existing format
  - [ ] No existing features renumbered

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Exactly 5 new features added
    Tool: Bash (grep)
    Steps:
      1. grep -c "Feature 3.11\|Feature 3.12\|Feature 3.13\|Feature 3.14\|Feature 3.15" PLAN.md → Expected: 5
      2. grep -c "### Feature" PLAN.md → Expected: original count + 5
      3. grep -c "PDF Audit\|Cookie Audit\|Pagination Audit\|Mobile Usability\|Core Web Vitals" PLAN.md → Expected: 5
    Expected Result: Exactly 5 features, no more
    Evidence: .sisyphus/evidence/task-13-features.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add 5 missing features (PDF, Cookie, Pagination, Mobile, CWV audits)`
  - Files: `PLAN.md`

---

### Wave 6 — Final Integration (sequential, depends on ALL)

- [ ] 14. Add Feature Dependency Graph + Cross-Reference Audit

  **What to do**:
  - Read current PLAN.md (full file — all new sections from Tasks 1-13)
  - Add a new section "## Feature Dependency Graph" as the LAST section before "URL References"
  - Then perform a cross-reference audit across all sections

  **14a. Feature Dependency DAG** (Mermaid graph):
  ```mermaid
  graph TD
    F1.1[1.1 Spider Mode] --> F2.1[2.1 Page Titles]
    F1.1 --> F2.2[2.2 Meta Desc]
    F1.1 --> F2.3[2.3 Headings]
    ...
    F1.3[1.3 URL Discovery] --> F2.10[2.10 Internal Links]
    F1.4[1.4 JS Rendering] --> F3.8[3.8 Accessibility]
    F2.10 --> F3.6[3.6 Link Score]
    F2.12[2.12 Duplicates] --> F3.10[3.10 Crawl Comparison]
    ...
  ```
  - Show ALL 62 features (57 original + 5 new) as nodes
  - Show dependency edges (Feature X requires Feature Y to be built first)
  - Highlight critical path
  - Color-code by phase (Phase 1=red, Phase 2=orange, etc.)
  - Include a legend

  **14b. Build Order Recommendation**:
  - List the recommended implementation order based on the DAG
  - Group into implementation sprints (not time-estimated, just logical groups)

  **14c. Cross-Reference Audit**:
  After adding the dependency graph, validate the ENTIRE PLAN.md:
  1. Every DB table name in Schema section appears in at least one API endpoint
  2. Every API endpoint path references a real DB entity
  3. Every file in Project Structure is referenced by at least one feature
  4. WebSocket message types match frontend component descriptions
  5. Docker service names match architecture diagram component names
  6. Performance targets reference correct components
  7. Error handling categories cover all components in architecture
  8. Testing strategy references correct tools and file paths
  - Fix any inconsistencies found

  **Must NOT do**:
  - Don't add time estimates or resource allocation
  - Don't create a Gantt chart
  - Don't add project management artifacts

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6 (solo, depends on ALL)
  - **Blocks**: F1-F4
  - **Blocked By**: ALL tasks (1-13)

  **References**:
  - PLAN.md (ALL sections — this task reads the entire file)
  - Task 3 (DB Schema) — table names to cross-reference
  - Task 7 (API Spec) — endpoint paths to cross-reference
  - Task 4 (Project Structure) — file paths to cross-reference

  **Acceptance Criteria**:
  - [ ] Mermaid dependency graph with ≥ 62 nodes
  - [ ] Critical path highlighted
  - [ ] Build order recommendation present
  - [ ] Cross-reference audit completed with 0 orphaned references
  - [ ] All inconsistencies fixed

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Dependency graph present and complete
    Tool: Bash (grep)
    Steps:
      1. grep -c "graph TD\|graph LR" PLAN.md → Expected: ≥ 1
      2. grep -c "F1\.\|F2\.\|F3\.\|F4\.\|F5\.\|F6\." PLAN.md → Expected: ≥ 30 (feature references in graph)
      3. grep -c "critical.path\|Critical Path" PLAN.md → Expected: ≥ 1
    Expected Result: Complete dependency graph with critical path
    Evidence: .sisyphus/evidence/task-14-graph.txt

  Scenario: Zero placeholder text in entire document
    Tool: Bash (grep)
    Steps:
      1. grep -ci "TBD\|TODO\|\[fill\]\|\[insert\]\|PLACEHOLDER" PLAN.md → Expected: 0
    Expected Result: No placeholder text anywhere in PLAN.md
    Evidence: .sisyphus/evidence/task-14-no-placeholders.txt

  Scenario: Cross-reference consistency
    Tool: Bash (grep)
    Steps:
      1. Count unique table names in DB section
      2. For each table name, verify it appears in API section
      3. Verify Docker service names match architecture diagram
    Expected Result: All cross-references valid
    Evidence: .sisyphus/evidence/task-14-crossref.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): add feature dependency graph and complete cross-reference audit`
  - Files: `PLAN.md`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read PLAN.md end-to-end. For each "Must Have" in this work plan: verify the section exists in PLAN.md with adequate depth. For each "Must NOT Have": search for forbidden patterns (working code files, multi-user auth, K8s). Check all 12 new sections are present. Compare deliverables against this plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Sections [12/12] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Content Quality Review** — `unspecified-high`
  Review every new section in PLAN.md for: placeholder text (TBD/TODO/[fill]), adequate depth (DB has columns+types+indexes, API has req/res schemas), consistent formatting, accurate technical content. Check selectolax/ARQ/asyncpg references are correct.
  Output: `Sections [N/N quality] | Placeholders [0/N found] | Tech Accuracy [N/N] | VERDICT`

- [ ] F3. **Cross-Reference Validation** — `unspecified-high`
  Verify internal consistency: every DB table name appears in API spec, every API endpoint path matches a router in Project Structure, WebSocket message types match frontend component descriptions, Docker service names match architecture diagram. List any orphaned references.
  Output: `DB↔API [N/N] | API↔Structure [N/N] | WS↔Frontend [N/N] | Orphans [0/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify: no features beyond the 5 explicitly listed missing features were added, existing Thai descriptions preserved (not rewritten), no Kubernetes/cloud deployment, no observability stack, no benchmark data, no time estimates in dependency graph. Flag any scope creep.
  Output: `New Features [5/5 only] | Preserved Content [Y/N] | Scope Creep [0/N items] | VERDICT`

---

## Commit Strategy

- After each wave: `docs(plan): add {section names} to PLAN.md`
- Final commit: `docs(plan): complete 10/10 specification upgrade`

---

## Success Criteria

### Verification Commands
```bash
# Database tables count (≥15)
grep -c "CREATE TABLE\|^|.*|.*|.*|.*|" PLAN.md

# API endpoints count (≥40)
grep -ci "GET\|POST\|PUT\|DELETE\|PATCH\|WebSocket" PLAN.md

# Zero placeholders
grep -ci "TBD\|TODO\|\[fill" PLAN.md  # Expected: 0

# File completeness
wc -l PLAN.md  # Expected: 3000-5000 lines
```

### Final Checklist
- [ ] All 12 new sections present in PLAN.md
- [ ] Tech stack table updated (selectolax, ARQ, asyncpg)
- [ ] Table of Contents with working anchor links
- [ ] Zero placeholder text
- [ ] Cross-references valid (DB↔API↔Structure)
- [ ] Existing Thai feature descriptions preserved
- [ ] 5 missing features added (not more)
- [ ] Feature dependency graph as Mermaid DAG
