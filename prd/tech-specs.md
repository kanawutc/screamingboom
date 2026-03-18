# SEO Spider — Technical Specification

## Stack Versions

### Backend
| Component | Package | Version | Purpose |
|-----------|---------|---------|---------|
| Runtime | Python | >= 3.12 | Language runtime |
| Framework | FastAPI | >= 0.115.0 | REST API + WebSocket |
| ASGI Server | Uvicorn | >= 0.30.0 | Dev server (uvloop + httptools) |
| WSGI Server | Gunicorn | >= 22.0.0 | Production server |
| Validation | Pydantic | >= 2.8.0 | Request/response schemas |
| Settings | pydantic-settings | >= 2.4.0 | Env-based configuration |
| ORM | SQLAlchemy | >= 2.0.36 | Async ORM (asyncio mode) |
| Migrations | Alembic | >= 1.13.0 | Schema migrations |
| DB Driver (async) | asyncpg | >= 0.30.0 | PostgreSQL async driver |
| DB Driver (sync) | psycopg2-binary | >= 2.9.10 | Alembic migrations only |
| HTTP Client | aiohttp | >= 3.10.0 | Crawler fetcher |
| HTML Parser | selectolax | >= 0.3.21 | Primary (35x faster than BS4) |
| XPath Parser | lxml | >= 5.3.0 | Custom extraction fallback |
| Task Queue | arq | >= 0.26.0 | Async Redis-based worker |
| Redis Client | redis-py | >= 5.1.0 | Cache, queue, pub/sub |
| Logging | structlog | >= 24.4.0 | Structured JSON logging |
| Bloom Filter | pybloom-live | >= 3.0.0 | URL deduplication |
| Excel Export | openpyxl | >= 3.1.0 | XLSX generation |

### Frontend
| Component | Package | Version | Purpose |
|-----------|---------|---------|---------|
| Framework | Next.js | 16.1.6 | App Router, standalone output |
| UI Library | React | 19.2.3 | Component framework |
| Language | TypeScript | ^5 | Type safety |
| CSS | Tailwind CSS | ^4 | Utility-first styling |
| UI Components | shadcn/ui + Radix | 4.0.5 / 1.4.3 | Accessible component primitives |
| State (client) | Zustand | ^5.0.11 | Global state management |
| State (server) | TanStack React Query | ^5.90.21 | Data fetching + caching |
| Icons | Lucide React | ^0.577.0 | Icon library |
| Toast | Sonner | ^2.0.7 | Toast notifications |
| Theme | next-themes | ^0.4.6 | Dark mode (installed, unused) |

### Infrastructure
| Component | Image/Version | Purpose |
|-----------|--------------|---------|
| Database | PostgreSQL 16 Alpine | Primary data store |
| Cache/Queue | Redis 7 Alpine | Frontier, pub/sub, arq queue |
| Proxy | Nginx Alpine | Reverse proxy, WS upgrade, gzip |
| Runtime | Node.js 22 | Frontend runtime |
| Package Manager | npm 10 | Frontend dependencies |

## Database

### Extensions Required
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### Tables (3 Alembic migrations)

#### projects
```sql
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    domain      VARCHAR(255) NOT NULL,
    settings    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_projects_domain ON projects (domain);
```
- Constraints: name NOT NULL, domain NOT NULL
- Relationships: one-to-many -> crawls, extraction_rules

#### crawls
```sql
CREATE TABLE crawls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'idle'
                    CHECK (status IN ('idle','configuring','queued','crawling','paused',
                                      'completing','completed','failed','cancelled')),
    mode            VARCHAR(10) NOT NULL DEFAULT 'spider'
                    CHECK (mode IN ('spider','list')),
    config          JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    total_urls      INTEGER NOT NULL DEFAULT 0,
    crawled_urls_count INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_crawls_project_id ON crawls (project_id);
CREATE INDEX idx_crawls_status ON crawls (status)
    WHERE status IN ('crawling', 'paused', 'queued');
```
- Constraints: status CHECK (9 values), mode CHECK (spider/list), project_id FK CASCADE
- Relationships: many-to-one -> projects. one-to-many -> crawled_urls, page_links, url_issues, redirects

#### crawled_urls — HASH PARTITIONED x4 by crawl_id
```sql
CREATE TABLE crawled_urls (
    id                  BIGSERIAL,
    crawl_id            UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url                 TEXT NOT NULL,
    url_hash            BYTEA NOT NULL,
    status_code         SMALLINT,
    content_type        VARCHAR(100),
    response_time_ms    INTEGER,
    title               TEXT,
    title_length        SMALLINT,
    title_pixel_width   SMALLINT,
    meta_description    TEXT,
    meta_desc_length    SMALLINT,
    h1                  TEXT[],
    h2                  TEXT[],
    canonical_url       TEXT,
    robots_meta         TEXT[],
    is_indexable        BOOLEAN NOT NULL DEFAULT true,
    indexability_reason VARCHAR(100),
    word_count          INTEGER,
    content_hash        BYTEA,
    crawl_depth         SMALLINT NOT NULL DEFAULT 0,
    seo_data            JSONB NOT NULL DEFAULT '{}',
    search_vector       TSVECTOR,
    crawled_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, crawl_id)
) PARTITION BY HASH (crawl_id);
-- 4 partitions: crawled_urls_p0 through crawled_urls_p3
```
- RESTRICTION: ALL queries MUST include crawl_id in WHERE clause (partition key)
- Indexes: crawl_id+url_hash, crawl_id+status_code, GIN on search_vector, GIN on seo_data, trigram on url
- seo_data JSONB fields: og_tags, json_ld, hreflang, images, heading_sequence, security_headers, pagination, custom_extractions

#### page_links
```sql
CREATE TABLE page_links (
    id              BIGSERIAL PRIMARY KEY,
    crawl_id        UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    source_url_id   BIGINT NOT NULL,
    target_url      TEXT NOT NULL,
    target_url_hash BYTEA NOT NULL,
    anchor_text     TEXT,
    link_type       VARCHAR(20) NOT NULL DEFAULT 'internal'
                    CHECK (link_type IN ('internal','external','resource')),
    rel_attrs       TEXT[],
    is_javascript   BOOLEAN NOT NULL DEFAULT false
);
```
- Constraints: link_type CHECK (internal/external/resource)

#### url_issues — HASH PARTITIONED x4 by crawl_id
```sql
CREATE TABLE url_issues (
    id          BIGSERIAL,
    crawl_id    UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url_id      BIGINT NOT NULL,
    issue_type  VARCHAR(100) NOT NULL,
    severity    VARCHAR(20) NOT NULL DEFAULT 'warning'
                CHECK (severity IN ('critical','warning','info','opportunity')),
    category    VARCHAR(50) NOT NULL,
    details     JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (id, crawl_id)
) PARTITION BY HASH (crawl_id);
```
- RESTRICTION: ALL queries MUST include crawl_id in WHERE clause
- Constraints: severity CHECK (critical/warning/info/opportunity)

#### redirects
```sql
CREATE TABLE redirects (
    id          BIGSERIAL PRIMARY KEY,
    crawl_id    UUID NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    chain_id    UUID NOT NULL DEFAULT gen_random_uuid(),
    source_url  TEXT NOT NULL,
    target_url  TEXT NOT NULL,
    status_code SMALLINT NOT NULL,
    hop_number  SMALLINT NOT NULL DEFAULT 1
);
```

#### extraction_rules
```sql
CREATE TABLE extraction_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    selector        TEXT NOT NULL,
    selector_type   VARCHAR(10) NOT NULL CHECK (selector_type IN ('css','xpath')),
    extract_type    VARCHAR(20) NOT NULL DEFAULT 'text'
                    CHECK (extract_type IN ('text','html','attribute','count')),
    attribute_name  VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Environment Variables
| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| DATABASE_URL | postgresql+asyncpg://postgres:changeme@localhost:5432/seo_spider | Yes | PostgreSQL (async) |
| REDIS_URL | redis://localhost:6379 | Yes | Redis connection |
| NEXT_PUBLIC_API_URL | http://localhost/api/v1 | Yes | Frontend API base |
| OPENAI_API_KEY | — | No | AI features (Phase 4+) |

## Docker Compose Services (7)
| Service | Image | Port | Depends On |
|---------|-------|------|------------|
| frontend | ./frontend | 3000 | backend |
| backend | ./backend | 8000 | migrate, redis |
| worker | ./backend (arq) | — | migrate, redis |
| migrate | ./backend (alembic) | — | db |
| db | postgres:16-alpine | 5432 | — |
| redis | redis:7-alpine (512MB, volatile-lru, AOF) | 6379 | — |
| nginx | nginx:alpine | 80 | frontend, backend |
