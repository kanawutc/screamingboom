# SEO Spider — Screaming Frog Clone

A self-hosted, open-source SEO crawling and analysis tool modeled after Screaming Frog SEO Spider. Crawls websites, detects SEO issues, and provides real-time progress monitoring via WebSocket.

## Architecture

**5-layer stack** orchestrated by Docker Compose:

```
Browser (:80) → Nginx → Next.js 16 (frontend) → FastAPI (backend) → PostgreSQL 16 + Redis 7
                  ↘ /api/*  → backend:8000
                  ↘ /ws/*   → backend:8000 (WebSocket upgrade)
                  ↘ /*      → frontend:3000
```

**Services** (docker-compose.yml):

| Service   | Image / Build        | Purpose                                    |
|-----------|----------------------|--------------------------------------------|
| frontend  | `./frontend`         | Next.js 16 (React 19, TypeScript, Tailwind 4) |
| backend   | `./backend`          | FastAPI with async SQLAlchemy, Pydantic v2  |
| worker    | `./backend` (arq)    | Background crawl jobs via async Redis queue |
| migrate   | `./backend` (alembic)| Database migrations on startup              |
| db        | `postgres:16-alpine` | Primary data store, hash-partitioned tables |
| redis     | `redis:7-alpine`     | Frontier queue, pub/sub, caching            |
| nginx     | `nginx:alpine`       | Reverse proxy, WebSocket upgrade, gzip      |

## Tech Stack

### Backend (Python 3.12+)
- **Framework**: FastAPI + Uvicorn/Gunicorn
- **ORM**: SQLAlchemy 2.0 (async) + Alembic migrations
- **Task Queue**: arq (async Redis-based worker)
- **HTML Parser**: selectolax (35x faster than BeautifulSoup)
- **HTTP Client**: aiohttp with connection pooling
- **Logging**: structlog (structured JSON logging)
- **Dedup**: pybloom-live (Bloom filter, 100k capacity, 0.1% FP rate)

### Frontend (Node.js)
- **Framework**: Next.js 16 (App Router, standalone output)
- **UI**: shadcn/ui (Radix UI) + Tailwind CSS 4
- **State**: Zustand 5 (client) + TanStack React Query 5 (server)
- **Real-time**: WebSocket hook with auto-reconnect + exponential backoff
- **Icons**: Lucide React

### Infrastructure
- **Database**: PostgreSQL 16 with pg_trgm, hash partitioning (4 partitions on crawled_urls, url_issues)
- **Cache/Queue**: Redis 7 with AOF persistence, 512MB max, volatile-lru eviction
- **Proxy**: Nginx with gzip, security headers, WebSocket upgrade support

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory + lifespan
│   │   ├── core/                      # Config (pydantic-settings), logging, exceptions
│   │   ├── api/v1/                    # REST endpoints (projects, crawls, urls, issues, comparison, extraction_rules)
│   │   ├── crawler/                   # Crawl engine pipeline
│   │   │   ├── engine.py              # BFS crawl orchestrator
│   │   │   ├── frontier.py            # Redis sorted set + Bloom filter URL queue
│   │   │   ├── fetcher.py             # aiohttp pool with retry/redirect handling
│   │   │   ├── parser.py              # selectolax HTML parser + custom extractions
│   │   │   ├── inserter.py            # asyncpg COPY batch inserter (50k rows/sec)
│   │   │   ├── robots.py              # robots.txt fetcher + Redis cache (1h TTL)
│   │   │   └── utils.py               # URL normalization, domain extraction
│   │   ├── analysis/                  # SEO analysis engine
│   │   │   ├── analyzer.py            # Two-phase: inline (per-URL) + post-crawl (SQL)
│   │   │   ├── issue_registry.py      # Central registry of all issue types
│   │   │   ├── pixel_width.py         # Title pixel width calculator
│   │   │   └── rules/                 # Analysis rule modules (titles, meta, headings, images, canonicals, directives, security, url_quality)
│   │   ├── models/                    # SQLAlchemy ORM (Project, Crawl, CrawledUrl, PageLink, UrlIssue, Redirect, ExtractionRule)
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── repositories/             # Database access layer (base, project, crawl, url, issue repos)
│   │   ├── services/                  # Business logic (crawl_service, project_service)
│   │   ├── websocket/manager.py       # Redis pub/sub → WebSocket fan-out broadcaster
│   │   ├── worker/                    # arq worker settings + crawl task
│   │   └── db/                        # Session management, migrations, init.sql
│   ├── tests/                         # pytest-asyncio test suite
│   ├── pyproject.toml                 # Dependencies + tool config (ruff, mypy, pytest)
│   ├── alembic.ini                    # Migration config
│   └── Dockerfile
├── frontend/                          # Git submodule (Next.js 16)
│   ├── app/(dashboard)/               # Route group: dashboard, crawls list, crawl detail, compare, settings, new crawl
│   ├── components/                    # Layout (Sidebar, Topbar) + UI (shadcn) + crawl components
│   ├── lib/api-client.ts              # Typed API client for all backend endpoints
│   ├── hooks/use-crawl-websocket.ts   # WebSocket hook with reconnect logic
│   ├── stores/crawl-store.ts          # Zustand store for active crawl state
│   ├── types/index.ts                 # TypeScript type definitions
│   └── Dockerfile
├── nginx/nginx.conf                   # Reverse proxy config
├── docker-compose.yml                 # Production compose (6 services)
├── docker-compose.dev.yml             # Development overrides
├── .env.example                       # Environment variables template
├── PLAN.md                            # Full implementation plan (57 features, 6 phases)
└── test_*.py                          # Integration/E2E test files
```

## Database Schema

3 migrations in `backend/app/db/migrations/versions/`:

### Core Tables (001)
- **projects** — id (UUID), name, domain, settings (JSONB)
- **crawls** — id (UUID), project_id (FK), status (enum: idle/configuring/queued/crawling/paused/completing/completed/failed/cancelled), mode (spider/list), config (JSONB), URL counts
- **crawled_urls** — (id, crawl_id) composite PK, hash-partitioned ×4. Stores: URL, status_code, content_type, response_time, title, meta_description, h1/h2 arrays, canonical, robots_meta, is_indexable, word_count, content_hash, crawl_depth, seo_data (JSONB: og, json_ld, hreflang, images, security_headers, custom_extractions). Full-text search via tsvector + GIN, trigram index for ILIKE
- **page_links** — source_url_id → target_url, link_type (internal/external/resource), anchor_text, rel_attrs, is_javascript
- **url_issues** — (id, crawl_id) composite PK, hash-partitioned ×4. issue_type, severity (critical/warning/info/opportunity), category, details (JSONB)
- **redirects** — chain_id, source_url → target_url, status_code, hop_number

### Additional Migrations
- **002** — Performance indexes (trigram, category, canonical)
- **003** — extraction_rules table (project-scoped CSS/XPath selectors with text/html/attribute/count extraction)

## Crawler Engine

**BFS pipeline**: Frontier → Fetcher → Parser → Inserter → Analyzer

```
1. Seed start URL(s) into Redis sorted set (score = depth for BFS)
2. Pop URL from frontier (Bloom filter dedup)
3. Check robots.txt (cached in Redis, 1h TTL)
4. Fetch with aiohttp (30s timeout, 3 retries, exponential backoff)
   - Manual redirect following (max 10 hops, loop detection)
   - 429 handling with Retry-After (30/60/120s backoff)
5. Parse HTML with selectolax (if content-type is HTML and ≤10MB)
   - Extract: title, meta, headings, links, images, hreflang, JSON-LD, OG tags, word count, content hash
   - Apply custom CSS/XPath extraction rules
6. Run inline SEO analysis (per-URL issue detection)
7. Batch insert via asyncpg COPY (URLs, links, redirects, issues)
   - Flush at 500 items or every 2 seconds
8. Add discovered internal links to frontier
9. Publish progress to Redis pub/sub (every 10 URLs or 0.5s)
```

**Crawl modes**: `spider` (follow links from start URL) or `list` (crawl specific URL list)

**Crawl control**: Pause/resume/stop via Redis pub/sub commands during execution

**Failure handling**: Aborts after 10 consecutive domain failures; treats unreachable start URL as fatal

## SEO Analysis

Two-phase system in `backend/app/analysis/`:

### Inline Analysis (per-URL, during crawl)
| Category | Issues Detected |
|----------|----------------|
| Titles | Missing, multiple, too long (>60), too short (<30), pixel width (>580px), same as H1 |
| Meta Descriptions | Missing, multiple, too long (>155), too short (<70) |
| Headings | Missing H1, multiple H1, H1 too long (>70), non-sequential hierarchy |
| Images | Missing alt text, empty alt, missing srcset |
| Canonicals | Missing, multiple, self-referential |
| Directives | noindex, nofollow, both, multiple robots meta |
| URL Quality | Reserved characters, excessive query params, HTTP vs HTTPS |
| Security | Missing HSTS/CSP/X-Frame-Options/X-Content-Type-Options, mixed content |

### Post-Crawl Analysis (SQL-based, after crawl completes)
- Duplicate titles, meta descriptions, H1s (GROUP BY + HAVING COUNT > 1)
- Broken internal links (target not in crawled URLs)
- Invalid canonical targets (canonical URL not crawled)

## API Endpoints

All under `/api/v1`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Database + Redis health check |
| POST | `/projects` | Create project |
| GET | `/projects` | List projects (cursor pagination) |
| GET/PUT/DELETE | `/projects/{id}` | Project CRUD |
| POST | `/projects/{id}/crawls` | Start new crawl (enqueues arq job) |
| GET | `/projects/{id}/crawls` | List project crawls |
| GET | `/crawls` | List all crawls |
| GET | `/crawls/{id}` | Get crawl details |
| POST | `/crawls/{id}/pause\|resume\|stop` | Crawl control |
| DELETE | `/crawls/{id}` | Delete crawl |
| WS | `/crawls/{id}/ws` | Real-time progress (30s heartbeat) |
| GET | `/crawls/{id}/urls` | List crawled URLs (filters: status_code, content_type, is_indexable, search, has_issue) |
| GET | `/crawls/{id}/urls/{url_id}` | URL detail |
| GET | `/crawls/{id}/urls/{url_id}/inlinks\|outlinks` | Link graph |
| GET | `/crawls/{id}/external-links` | External links list |
| GET | `/crawls/{id}/sitemap.xml` | Generate XML sitemap |
| GET | `/crawls/{id}/export` | Export as CSV |
| GET | `/crawls/{id}/export-xlsx` | Export as XLSX |
| GET | `/crawls/{id}/structured-data` | JSON-LD structured data |
| GET | `/crawls/{id}/custom-extractions` | Custom extraction results |
| GET | `/crawls/{id}/issues` | List SEO issues (filters: severity, category, issue_type) |
| GET | `/crawls/{id}/issues/summary` | Aggregated issue counts |
| GET | `/crawls/compare` | Compare two crawls (change_type: added/removed/changed/unchanged) |
| CRUD | `/projects/{id}/extraction-rules` | Custom extraction rules (CSS/XPath) |

## WebSocket Protocol

Channel: `crawl:{crawl_id}:events` via Redis pub/sub

**Message types**:
- `progress` — crawled_count, error_count, elapsed_seconds, paused
- `status_change` — status, crawled_count, error_count, elapsed_seconds, error message
- `ping` — 30s heartbeat

Architecture: One Redis subscription per crawl → fan-out to N client queues (maxsize=100, drops oldest on backpressure)

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env if needed

# 2. Start all services
docker compose up --build

# 3. Access
# Web UI:  http://localhost
# API:     http://localhost/api/v1
# Docs:    http://localhost/api/docs
```

## Development

```bash
# Dev mode with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run tests
python -m pytest backend/tests/

# Lint
cd backend && ruff check . && mypy .
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:changeme@db:5432/seo_spider` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379` | Redis connection |
| `NEXT_PUBLIC_API_URL` | `http://localhost/api/v1` | Frontend API base URL |
| `OPENAI_API_KEY` | — | Optional: AI features (Phase 4+) |

## Plan & Roadmap

See [PLAN.md](PLAN.md) for the full implementation plan covering 57 features across 6 phases:

1. **Phase 1**: Core Crawl Engine (12 features) — implemented
2. **Phase 2**: SEO Analysis & Audit (15 features) — in progress
3. **Phase 3**: Advanced Analysis (10 features)
4. **Phase 4**: Integrations & AI (8 features)
5. **Phase 5**: Reports & Automation (7 features)
6. **Phase 6**: Bonus Features (6 features)
