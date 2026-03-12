# Sprint 1: Foundation — Core Crawler Engine + Infrastructure

## TL;DR

> **Quick Summary**: Build the entire project infrastructure (Docker Compose, PostgreSQL, Redis, Next.js 15, FastAPI) and implement the core crawl pipeline — enter a URL, BFS crawl the site, store results, view them in a web UI with real-time WebSocket progress.
> 
> **Deliverables**:
> - Docker Compose stack (7 services: frontend, backend, worker, db, redis, nginx, migrate)
> - PostgreSQL schema (6 core tables with HASH partitioning via Alembic)
> - FastAPI backend with Router→Service→Repository pattern (16 API endpoints)
> - Async crawl engine: URL Frontier (Redis sorted sets) → FetcherPool (aiohttp) → ParserPool (selectolax) → BatchInserter (asyncpg COPY)
> - Next.js 15 frontend: crawl creation form, real-time progress, basic results table
> - WebSocket real-time updates via Redis pub/sub
> - Spider Mode (F1.1), List Mode (F1.2), URL Discovery (F1.3), HTTP Response Handling (F1.5), Robots.txt (F1.6), User Agent Config (F1.7), Crawl Limits (F1.8)
> 
> **Estimated Effort**: Large (24-31 tasks across 3 waves)
> **Parallel Execution**: YES — 7 waves with heavy parallelism
> **Critical Path**: Docker/DB setup → Backend skeleton → Crawler engine → API integration → Frontend UI

---

## Context

### Original Request
User wants a self-hosted Screaming Frog SEO Spider clone as a web application, running locally via Docker Compose. The complete engineering specification is in `PLAN.md` (3,016 lines, rated 10/10). Phase A (specification writing) is complete. This plan covers Phase B Sprint 1: Foundation.

### Interview Summary
**Key Discussions**:
- All tech stack decisions finalized: Next.js 15 + FastAPI + selectolax + lxml + ARQ + asyncpg + pybloom-live + Redis + PostgreSQL
- V1 is single-user (no auth system)
- User said "can add beneficial features" but Sprint 1 focuses on foundation
- No git repo — no git operations planned
- F1.4 (JS Rendering / Playwright) intentionally excluded from Sprint 1

**Research Findings**:
- `pybloom-live` last released 2021 — Python 3.12 compatibility uncertain, needs verification. Fallback: RedisBloom or Python `set()`
- `BIGSERIAL` on HASH-partitioned tables causes sequence contention → use UUID `gen_random_uuid()` instead
- ARQ default `job_timeout=300s` silently kills crawls > 5 minutes → must set `job_timeout=7200`
- asyncpg COPY on partitioned tables is all-or-nothing per batch → need error isolation strategy
- Docker macOS requires VirtioFS + polling watchers for hot reload
- Nginx WebSocket needs `proxy_read_timeout 3600s` (default 60s kills connections)
- Redis frontier should use crawl depth as sorted set score for BFS ordering
- Alembic cannot auto-generate HASH partition DDL → use raw `op.execute()`

### Metis Review
**Identified Gaps** (addressed):
- Frontend scope undefined → Locked: 4 pages max (dashboard, crawl list, new crawl form, crawl detail)
- SEO analyzer scope ambiguous → Locked: parser extracts raw data fields only, NO Issue records in Sprint 1
- SQLAlchemy vs asyncpg for repos → Locked: SQLAlchemy Core for reads, asyncpg COPY for bulk writes
- Concurrent crawls undefined → Locked: single crawl at a time (ARQ `max_jobs=1`)
- Alembic driver mismatch → Locked: use `psycopg2` sync driver in Alembic env.py, `asyncpg` for app

---

## Work Objectives

### Core Objective
Deliver a working end-to-end crawl pipeline: user enters a URL in the web UI → crawler BFS-discovers all internal pages → stores results in PostgreSQL → user sees results in real-time via WebSocket and browses them in a paginated table.

### Concrete Deliverables
- `docker-compose.yml` + `docker-compose.dev.yml` — start entire stack with one command
- `nginx/nginx.conf` — reverse proxy with WebSocket support
- `.env.example` — environment variable template
- `backend/` — FastAPI app with 16 API endpoints, crawler engine, ARQ worker
- `frontend/` — Next.js 15 app with 4 pages (dashboard, crawl list, new crawl, crawl detail)
- PostgreSQL schema — 6 tables: projects, crawls, crawled_urls (partitioned), page_links, url_issues (partitioned), redirects
- Working crawl of `https://books.toscrape.com` as proof-of-life

### Definition of Done
- [ ] `docker compose up -d` starts all services successfully
- [ ] `docker compose exec backend alembic upgrade head` creates all tables
- [ ] `curl http://localhost/api/v1/health` returns `{"status":"healthy"}`
- [ ] Can create a project, start a spider crawl of `https://books.toscrape.com` (max 50 URLs), see progress via WebSocket, view results in UI
- [ ] Crawl respects robots.txt, max_urls limit, and rate limiting
- [ ] Pause/Resume/Stop controls work
- [ ] List Mode: paste URLs, crawl only those URLs at depth=0

### Must Have
- Docker Compose stack starts and all services communicate
- BFS spider crawl with URL deduplication
- Real-time WebSocket progress updates
- Paginated URL results browsable in web UI
- Robots.txt respect mode
- Crawl limits (max_urls, max_depth, max concurrent threads)
- Redirect chain tracking
- Pause/Resume/Stop crawl controls
- URL normalization (lowercase, strip fragments, decode percent-encoding)

### Must NOT Have (Guardrails)
- ❌ NO SEO analyzer modules (TitleAnalyzer, MetaAnalyzer, HeadingAnalyzer, etc.) — parser extracts raw fields only
- ❌ NO Issue record generation (url_issues table remains empty until Sprint 2)
- ❌ NO post-crawl analysis (PageRank, MinHash, orphan detection)
- ❌ NO circuit breaker pattern
- ❌ NO checkpoint/resume crash recovery
- ❌ NO Bloom filter persistence to Redis (in-memory only, DB url_hash as fallback)
- ❌ NO per-domain back queues (use simple per-domain rate limiting via Redis TTL key)
- ❌ NO TanStack Table or react-virtual (use basic server-paginated shadcn/ui table)
- ❌ NO worker replicas > 1 in Docker Compose
- ❌ NO saved configuration profiles (crawl_configs CRUD)
- ❌ NO XML Sitemap download in List Mode (paste/upload only)
- ❌ NO custom user-agent editor UI (preset UAs in crawl config JSON)
- ❌ NO more than 16 API endpoints
- ❌ NO auth/login system
- ❌ NO git operations (no git repo exists)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (project is empty)
- **Automated tests**: YES (Tests-after) — basic smoke tests after each wave, no TDD
- **Framework**: pytest (backend), no frontend tests in Sprint 1
- **Rationale**: Sprint 1 priority is getting the crawler working end-to-end. Full TDD would slow the foundation sprint. Sprint 2 adds comprehensive test suites.

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/s1-task-{N}-{scenario-slug}.{ext}`.

- **Backend/API**: Use Bash (curl) — Send requests, assert status + response fields
- **Infrastructure**: Use Bash (docker compose) — Verify services, check logs
- **Crawler**: Use Bash (curl + psql) — Start crawl, verify DB records
- **Frontend/UI**: Use Playwright (playwright skill) — Navigate, interact, assert DOM, screenshot
- **WebSocket**: Use Bash (websocat or Python script) — Connect, receive messages, assert format

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — infrastructure scaffolding, MAX PARALLEL):
├── Task 1: Library compatibility verification [quick]
├── Task 2: Docker Compose + Nginx + .env [quick]
├── Task 3: Backend project initialization (FastAPI skeleton) [unspecified-high]
├── Task 4: Frontend project initialization (Next.js 15 skeleton) [visual-engineering]
├── Task 5: PostgreSQL schema + Alembic migrations [unspecified-high]

Wave 2 (After Wave 1 — core backend modules, MAX PARALLEL):
├── Task 6: Backend config, DB session, Redis client, health endpoint [quick]
├── Task 7: SQLAlchemy models + Pydantic schemas [unspecified-high]
├── Task 8: Repository layer (projects, crawls, urls CRUD) [unspecified-high]
├── Task 9: URL Frontier (Redis sorted sets + Bloom filter) [deep]
├── Task 10: Fetcher Pool (aiohttp + rate limiter + redirect tracking) [deep]

Wave 3 (After Wave 2 — crawler pipeline):
├── Task 11: Parser Pool (selectolax extraction pipeline) [deep]
├── Task 12: Batch Inserter (asyncpg COPY with error isolation) [deep]
├── Task 13: Robots.txt parser + per-domain cache [unspecified-high]

Wave 4 (After Wave 3 — engine coordination + API):
├── Task 14: Crawl Engine coordinator (orchestrates frontier→fetcher→parser→inserter) [deep]
├── Task 15: ARQ worker setup + crawl task [unspecified-high]
├── Task 16: Service layer (CrawlService, ProjectService) [unspecified-high]
├── Task 17: API routes — projects + crawls + urls + health [unspecified-high]

Wave 5 (After Wave 4 — real-time + controls):
├── Task 18: WebSocket manager (Redis pub/sub → client fan-out) [deep]
├── Task 19: Crawl control (Pause/Resume/Stop state machine) [deep]
├── Task 20: Crawl limits + User Agent configuration [unspecified-high]

Wave 6 (After Task 17 — frontend UI, parallel with Wave 5):
├── Task 21: Frontend layout shell + routing + API client [visual-engineering]
├── Task 22: Dashboard + crawl list pages [visual-engineering]
├── Task 23: New crawl form (Spider + List mode) [visual-engineering]
├── Task 24: Crawl detail page (progress + results table) [visual-engineering]

Wave 7 (After Waves 5+6 — integration):
├── Task 25: WebSocket integration in frontend (real-time progress) [visual-engineering]
├── Task 26: List Mode implementation [unspecified-high]
├── Task 27: End-to-end smoke test (books.toscrape.com) [deep]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit [deep]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Real QA — full Playwright + curl verification [unspecified-high]
├── Task F4: Scope fidelity check [deep]

Critical Path: T2 → T3 → T6 → T8 → T9 → T10 → T11 → T14 → T15 → T17 → T19 → T27
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 5 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| T1 | — | T3, T5, T9, T10, T11, T12 | 1 |
| T2 | — | T3, T4, T5, T6 | 1 |
| T3 | T2 | T6, T7, T8, T9-T20 | 1 |
| T4 | T2 | T21-T25 | 1 |
| T5 | T1, T2 | T6, T7, T8 | 1 |
| T6 | T3, T5 | T7, T8, T9-T20 | 2 |
| T7 | T5, T6 | T8, T9-T20 | 2 |
| T8 | T7 | T16, T17 | 2 |
| T9 | T6, T7 | T14 | 2 |
| T10 | T6 | T14 | 2 |
| T11 | T7, T10 | T14 | 3 |
| T12 | T7, T6 | T14 | 3 |
| T13 | T6 | T14 | 3 |
| T14 | T9, T10, T11, T12, T13 | T15, T19 | 4 |
| T15 | T14 | T17, T18 | 4 |
| T16 | T8, T14 | T17 | 4 |
| T17 | T8, T15, T16 | T21, T22, T23, T24, T26, T27 | 4 |
| T18 | T15, T6 | T19, T25 | 5 |
| T19 | T14, T18 | T25, T27 | 5 |
| T20 | T14 | T27 | 5 |
| T21 | T4, T17 | T22, T23, T24 | 6 |
| T22 | T21 | T25 | 6 |
| T23 | T21 | T25, T26 | 6 |
| T24 | T21 | T25, T27 | 6 |
| T25 | T18, T22, T24 | T27 | 7 |
| T26 | T17, T23 | T27 | 7 |
| T27 | T19, T20, T25, T26 | F1-F4 | 7 |
| F1-F4 | T27 | — | FINAL |

### Agent Dispatch Summary

| Wave | Tasks | Categories |
|------|-------|------------|
| 1 | 5 | T1→`quick`, T2→`quick`, T3→`unspecified-high`, T4→`visual-engineering`, T5→`unspecified-high` |
| 2 | 5 | T6→`quick`, T7→`unspecified-high`, T8→`unspecified-high`, T9→`deep`, T10→`deep` |
| 3 | 3 | T11→`deep`, T12→`deep`, T13→`unspecified-high` |
| 4 | 4 | T14→`deep`, T15→`unspecified-high`, T16→`unspecified-high`, T17→`unspecified-high` |
| 5 | 3 | T18→`deep`, T19→`deep`, T20→`unspecified-high` |
| 6 | 4 | T21-T24→`visual-engineering` |
| 7 | 3 | T25→`visual-engineering`, T26→`unspecified-high`, T27→`deep` |
| FINAL | 4 | F1→`deep`, F2→`unspecified-high`, F3→`unspecified-high`, F4→`deep` |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [x] 1. Library Compatibility Verification

  **What to do**:
  - Create a minimal Python 3.12-slim Docker test image
  - Install ALL Python dependencies: `selectolax`, `lxml`, `aiohttp`, `asyncpg`, `arq`, `pybloom-live`, `pydantic[settings]`, `fastapi`, `uvicorn`, `gunicorn`, `alembic`, `sqlalchemy[asyncio]`, `psycopg2-binary`, `structlog`, `httptools`, `uvloop`
  - Verify each package imports successfully: `python -c "import selectolax; import lxml; import aiohttp; import asyncpg; import arq; import pybloom_live; ..."`
  - If `pybloom-live` fails: test `rbloom` (Rust-based) as fallback. If both fail: document that Python `set()` will be used for Sprint 1
  - Create `backend/pyproject.toml` with all verified dependencies
  - Test `uv` package manager installation in Docker image

  **Must NOT do**:
  - Don't build any application code — just verify dependencies
  - Don't commit to a Bloom filter library if pybloom-live fails — document the fallback

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-concern task, verification only, no complex logic
  - **Skills**: []
    - No specialized skills needed — basic bash/Docker operations

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5)
  - **Blocks**: Tasks 3, 5, 9, 10, 11, 12 (all backend tasks depend on verified deps)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `PLAN.md:2519-2542` — Tech Stack table with all library choices and rationale

  **External References**:
  - pybloom-live PyPI: `https://pypi.org/project/pybloom-live/` — Check Python 3.12 wheel availability
  - rbloom PyPI: `https://pypi.org/project/rbloom/` — Rust-based Bloom filter alternative
  - selectolax: `https://pypi.org/project/selectolax/` — Verify C extension builds on slim
  - uv installer: `https://docs.astral.sh/uv/` — Fast pip replacement for Docker builds

  **WHY Each Reference Matters**:
  - Tech Stack table gives the complete dependency list to verify
  - pybloom-live is the highest-risk dependency (2021 last release, C extension)
  - selectolax has native C extension that may need build tools on slim image

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All Python dependencies install and import successfully
    Tool: Bash
    Preconditions: Docker available on host
    Steps:
      1. Run: docker run --rm python:3.12-slim sh -c "pip install selectolax lxml aiohttp asyncpg arq pybloom-live pydantic fastapi uvicorn gunicorn alembic 'sqlalchemy[asyncio]' psycopg2-binary structlog httptools uvloop && python -c 'import selectolax; import lxml; import aiohttp; import asyncpg; import arq; print(\"ALL IMPORTS OK\")'"
      2. Check exit code is 0
      3. Check output contains "ALL IMPORTS OK"
    Expected Result: Exit code 0, all packages install and import without errors
    Failure Indicators: pip install failure, ImportError, C extension build failure
    Evidence: .sisyphus/evidence/s1-task-1-deps-verify.txt

  Scenario: pybloom-live specific verification (or fallback)
    Tool: Bash
    Preconditions: Python 3.12-slim Docker image
    Steps:
      1. Run: docker run --rm python:3.12-slim sh -c "pip install pybloom-live && python -c 'from pybloom_live import ScalableBloomFilter; bf = ScalableBloomFilter(initial_capacity=1000, error_rate=0.001); bf.add(\"test\"); assert \"test\" in bf; print(\"BLOOM OK\")'"
      2. If fails, test rbloom: docker run --rm python:3.12-slim sh -c "pip install rbloom && python -c 'from rbloom import Bloom; bf = Bloom(1000, 0.001); bf.add(\"test\"); assert \"test\" in bf; print(\"RBLOOM OK\")'"
      3. Document which library works (or if both fail, document set() fallback)
    Expected Result: One of the Bloom filter libraries works, or fallback documented
    Failure Indicators: Both pybloom-live and rbloom fail to install/import
    Evidence: .sisyphus/evidence/s1-task-1-bloom-verify.txt

  Scenario: uv package manager works in Docker
    Tool: Bash
    Preconditions: Python 3.12-slim Docker image
    Steps:
      1. Run: docker run --rm python:3.12-slim sh -c "pip install uv && uv --version"
      2. Verify uv version is printed
    Expected Result: uv installs and runs successfully
    Failure Indicators: Installation failure or command not found
    Evidence: .sisyphus/evidence/s1-task-1-uv-verify.txt
  ```

  **Evidence to Capture:**
  - [ ] s1-task-1-deps-verify.txt — full pip install + import test output
  - [ ] s1-task-1-bloom-verify.txt — Bloom filter library test result
  - [ ] s1-task-1-uv-verify.txt — uv installation test
  - [ ] Output file: `backend/pyproject.toml` with verified dependency list

  **Commit**: NO (no git repo)

---

- [x] 2. Docker Compose + Nginx + Environment Configuration

  **What to do**:
  - Create `docker-compose.yml` with 7 services based on PLAN.md spec:
    - `frontend`: Next.js 15 (port 3000), depends on backend
    - `backend`: FastAPI (port 8000), depends on db + redis, health check via curl
    - `worker`: ARQ worker (same Dockerfile as backend, different command), depends on db + redis, `replicas: 1`
    - `migrate`: Alembic migration runner (runs once, exits), `service_completed_successfully` condition
    - `db`: PostgreSQL 16-alpine, `shared_buffers=256MB`, `work_mem=4MB`, health check via pg_isready
    - `redis`: Redis 7-alpine, `maxmemory 512mb`, `allkeys-lru`, `appendonly yes`, health check via redis-cli ping
    - `nginx`: Nginx alpine (port 80), depends on frontend + backend
  - Create `docker-compose.dev.yml` with development overrides:
    - Frontend: volume mount `./frontend:/app` (exclude node_modules via anonymous volume `/app/node_modules` and `/app/.next`), `npm run dev`, `WATCHPACK_POLLING=true`
    - Backend: volume mount `./backend:/app` (exclude `__pycache__`), `uvicorn app.main:app --reload --host 0.0.0.0`, `WATCHFILES_FORCE_POLLING=true`
    - DB: expose port 5432 to host
    - Redis: expose port 6379 to host
    - Worker: volume mount same as backend, auto-restart on code change
  - Create `nginx/nginx.conf`:
    - `/api/` → `http://backend:8000` (proxy_pass, strip `/api` prefix if needed)
    - `/api/v1/crawls/*/ws` → WebSocket upgrade (`map $http_upgrade`, `proxy_http_version 1.1`, `Upgrade`, `Connection` headers, `proxy_read_timeout 3600s`)
    - `/` → `http://frontend:3000`
    - Worker process: auto, worker connections: 1024
  - Create `.env.example` with all environment variables from PLAN.md
  - Create `backend/Dockerfile`:
    - Base: `python:3.12-slim`
    - Install `uv` via pip
    - Copy `pyproject.toml`, install deps with `uv pip install`
    - Copy app code
    - Non-root user: `appuser`
    - Entrypoint: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000`
  - Create `frontend/Dockerfile` (multi-stage):
    - `deps` stage: `node:20-alpine`, `npm ci`
    - `builder` stage: `npm run build` with `NEXT_TELEMETRY_DISABLED=1`, `output: 'standalone'`
    - `runner` stage: `node:20-alpine`, copy `.next/standalone` + `.next/static` + `public`, non-root user `nextjs`, `HOSTNAME=0.0.0.0`

  **Must NOT do**:
  - Don't add Prometheus/Grafana or any observability
  - Don't set worker replicas > 1
  - Don't add production hardening (resource limits, logging drivers)
  - Don't add Playwright service yet (Sprint 1 excludes JS rendering)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuration files following well-documented patterns from PLAN.md
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5)
  - **Blocks**: Tasks 3, 4, 5, 6 (all services need Docker Compose)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `PLAN.md:2562-2677` — Complete docker-compose.yml with all service definitions
  - `PLAN.md:2679-2697` — Nginx configuration and Dockerfile descriptions
  - `PLAN.md:2699-2721` — .env.example with all environment variables
  - `PLAN.md:2723-2745` — docker-compose.dev.yml development overrides

  **External References**:
  - Docker Compose spec: service dependencies with `service_completed_successfully` for migrate service
  - Nginx WebSocket proxy: `map $http_upgrade` + `proxy_read_timeout 3600s`

  **WHY Each Reference Matters**:
  - PLAN.md Docker section has the complete YAML — copy and adapt (reduce replicas, add migrate service)
  - Nginx must explicitly handle WebSocket upgrade headers or connections drop after 60s
  - Dev overrides need VirtioFS + polling for macOS Docker Desktop hot reload

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Docker Compose configuration is valid
    Tool: Bash
    Preconditions: Docker and Docker Compose installed on host
    Steps:
      1. Run: docker compose config --quiet
      2. Check exit code is 0 (no syntax errors)
      3. Run: docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet
      4. Check exit code is 0
    Expected Result: Both compose files parse without errors
    Failure Indicators: YAML syntax error, invalid service reference, undefined variable
    Evidence: .sisyphus/evidence/s1-task-2-compose-valid.txt

  Scenario: All required files exist with correct structure
    Tool: Bash
    Preconditions: Task 2 completed
    Steps:
      1. Verify files exist: docker-compose.yml, docker-compose.dev.yml, nginx/nginx.conf, .env.example, backend/Dockerfile, frontend/Dockerfile
      2. Grep docker-compose.yml for all 7 services: frontend, backend, worker, migrate, db, redis, nginx
      3. Grep nginx.conf for "proxy_read_timeout 3600" (WebSocket timeout)
      4. Grep nginx.conf for "map $http_upgrade" (WebSocket upgrade)
      5. Grep docker-compose.dev.yml for "WATCHPACK_POLLING" and "WATCHFILES_FORCE_POLLING"
    Expected Result: All files exist, all critical config directives present
    Failure Indicators: Missing file, missing service definition, missing WebSocket config
    Evidence: .sisyphus/evidence/s1-task-2-files-check.txt

  Scenario: Nginx config has correct routing rules
    Tool: Bash
    Preconditions: nginx/nginx.conf exists
    Steps:
      1. Grep for "location /api/" with proxy_pass to backend:8000
      2. Grep for WebSocket location with upgrade headers
      3. Grep for "location /" with proxy_pass to frontend:3000
      4. Verify backend is upstream (no trailing slash issues)
    Expected Result: Three routing rules correctly configured
    Failure Indicators: Missing route, wrong upstream, missing WebSocket headers
    Evidence: .sisyphus/evidence/s1-task-2-nginx-routes.txt
  ```

  **Evidence to Capture:**
  - [ ] s1-task-2-compose-valid.txt — compose config validation output
  - [ ] s1-task-2-files-check.txt — file existence and content verification
  - [ ] s1-task-2-nginx-routes.txt — nginx routing verification
  - [ ] Output files: docker-compose.yml, docker-compose.dev.yml, nginx/nginx.conf, .env.example, backend/Dockerfile, frontend/Dockerfile

  **Commit**: NO (no git repo)

- [x] 3. Backend Project Initialization (FastAPI Skeleton)

  **What to do**:
  - Create `backend/` directory structure matching PLAN.md:
    ```
    backend/app/__init__.py
    backend/app/main.py           — FastAPI app factory with lifespan events
    backend/app/api/__init__.py
    backend/app/api/deps.py       — Shared dependencies (DB session, Redis client)
    backend/app/api/v1/__init__.py
    backend/app/api/v1/router.py  — Aggregates all v1 routers
    backend/app/core/__init__.py
    backend/app/core/config.py    — Pydantic Settings (DATABASE_URL, REDIS_URL, etc.)
    backend/app/core/exceptions.py — Custom exception handlers
    backend/app/core/logging.py   — structlog configuration
    backend/app/crawler/__init__.py  — Empty, populated in Wave 2-3
    backend/app/analysis/__init__.py — Empty, populated in Sprint 2
    backend/app/models/__init__.py   — Empty, populated in Task 7
    backend/app/schemas/__init__.py  — Empty, populated in Task 7
    backend/app/repositories/__init__.py — Empty, populated in Task 8
    backend/app/services/__init__.py    — Empty, populated in Task 16
    backend/app/db/__init__.py
    backend/app/db/session.py     — asyncpg pool + SQLAlchemy async engine
    backend/app/worker/__init__.py — Empty, populated in Task 15
    backend/app/websocket/__init__.py — Empty, populated in Task 18
    backend/tests/__init__.py
    backend/tests/conftest.py     — Minimal fixtures
    ```
  - `main.py`: FastAPI app with `lifespan` context manager (startup: create DB pool + Redis connection, shutdown: close both)
  - `config.py`: Pydantic `BaseSettings` with `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `LOG_LEVEL`, `model_config = SettingsConfigDict(env_file=".env")`
  - `session.py`: `create_async_engine()` with asyncpg, `async_sessionmaker`, connection pool settings
  - `deps.py`: `get_db()` dependency (yields async session), `get_redis()` dependency
  - `exceptions.py`: Custom exception handlers for 404, 422, 500 returning JSON
  - `logging.py`: structlog with JSON output, request_id in context
  - `pyproject.toml`: Complete with all verified dependencies from Task 1 + dev deps (pytest, pytest-asyncio, httpx, ruff, mypy)

  **Must NOT do**:
  - Don't implement any API endpoints yet (Task 17)
  - Don't implement any crawler code yet (Tasks 9-14)
  - Don't configure CORS beyond basic `allow_origins=["*"]` for dev

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple files with interconnected imports, needs careful Python project setup
  - **Skills**: [`modern-python`]
    - `modern-python`: Configures Python projects with modern tooling (uv, ruff) — matches our tooling choices

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T4, T5)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 6-20 (all backend tasks)
  - **Blocked By**: Task 2 (needs Dockerfile)

  **References**:

  **Pattern References**:
  - `PLAN.md:300-382` — Complete backend directory structure with file descriptions
  - `PLAN.md:305-306` — main.py: "App factory, lifespan events, middleware setup"
  - `PLAN.md:320-322` — core/: config.py, exceptions.py, logging.py descriptions
  - `PLAN.md:364-366` — db/: session.py, migrations/, init.sql descriptions

  **External References**:
  - FastAPI lifespan events: `https://fastapi.tiangolo.com/advanced/events/`
  - Pydantic Settings v2: `https://docs.pydantic.dev/latest/concepts/pydantic_settings/`
  - structlog JSON: `https://www.structlog.org/en/stable/`

  **WHY Each Reference Matters**:
  - Directory structure from PLAN.md must be followed exactly — it defines the import paths
  - FastAPI lifespan is the correct pattern for managing DB/Redis connections (not on_event deprecated)
  - Pydantic Settings v2 syntax differs from v1 — use `model_config` not `class Config`

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Backend directory structure matches PLAN.md
    Tool: Bash
    Preconditions: Task 3 completed
    Steps:
      1. Run: find backend/app -name "*.py" | sort
      2. Verify all expected __init__.py files exist
      3. Verify main.py, config.py, session.py, deps.py, exceptions.py, logging.py exist
      4. Verify pyproject.toml exists with all dependencies
    Expected Result: All files present matching PLAN.md structure
    Failure Indicators: Missing files, wrong directory nesting
    Evidence: .sisyphus/evidence/s1-task-3-structure.txt

  Scenario: FastAPI app starts without errors
    Tool: Bash
    Preconditions: Backend directory created, Docker Compose available
    Steps:
      1. Run: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d backend db redis
      2. Wait 15s for startup
      3. Run: docker compose logs backend | tail -20
      4. Check for "Application startup complete" or similar uvicorn message
      5. Check for no ERROR or CRITICAL in logs
    Expected Result: Backend starts, no import errors, no configuration errors
    Failure Indicators: ImportError, ModuleNotFoundError, configuration validation failure
    Evidence: .sisyphus/evidence/s1-task-3-startup.txt
  ```

  **Evidence to Capture:**
  - [ ] s1-task-3-structure.txt — directory listing verification
  - [ ] s1-task-3-startup.txt — backend startup log output

  **Commit**: NO (no git repo)

---

- [ ] 4. Frontend Project Initialization (Next.js 15 Skeleton)

  **What to do**:
  - Initialize Next.js 15 project in `frontend/` with App Router:
    - `npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=no --import-alias="@/*"`
  - Install additional dependencies:
    - `shadcn/ui`: `npx shadcn@latest init` (New York style, slate color, CSS variables)
    - `@tanstack/react-query` + `@tanstack/react-query-devtools`
    - `zustand`
    - `lucide-react` (icons)
    - `recharts` (charts — needed for progress visualization)
  - Create directory structure matching PLAN.md:
    ```
    frontend/app/layout.tsx                    — Root layout (ThemeProvider, QueryClientProvider)
    frontend/app/page.tsx                      — Redirect to /crawls
    frontend/app/(dashboard)/layout.tsx        — Dashboard shell (placeholder sidebar + topbar)
    frontend/app/(dashboard)/page.tsx          — Dashboard page (placeholder)
    frontend/app/(dashboard)/crawls/page.tsx   — Crawl list (placeholder)
    frontend/app/(dashboard)/crawls/new/page.tsx — New crawl form (placeholder)
    frontend/app/(dashboard)/crawls/[crawlId]/page.tsx — Crawl detail (placeholder)
    frontend/components/ui/                    — shadcn/ui primitives (button, card, input, table, badge, dialog, select, toast)
    frontend/components/layout/Sidebar.tsx     — Navigation sidebar (placeholder)
    frontend/components/layout/Topbar.tsx      — Top navigation bar (placeholder)
    frontend/hooks/                            — Empty, populated in Tasks 21-25
    frontend/lib/api-client.ts                 — Typed fetch wrapper (placeholder)
    frontend/lib/query-client.ts               — TanStack Query config
    frontend/lib/utils.ts                      — cn() utility
    frontend/stores/                           — Empty, populated in Tasks 21-25
    frontend/types/index.ts                    — TypeScript type stubs (CrawlStatus, Project, Crawl, CrawledUrl)
    ```
  - Configure `next.config.ts`: `output: 'standalone'` for Docker, rewrites for API proxy in dev
  - Install shadcn/ui components: `button`, `card`, `input`, `table`, `badge`, `dialog`, `select`, `toast`, `progress`, `tabs`, `separator`, `dropdown-menu`

  **Must NOT do**:
  - Don't build any functional UI yet (Tasks 21-25)
  - Don't add TanStack Table or react-virtual
  - Don't implement WebSocket hooks yet (Task 25)
  - Don't add D3.js or Three.js (Sprint 3+)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Frontend project setup with UI component library, styling system
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Expert guidance for shadcn/ui integration and component installation

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T5)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 21-25 (all frontend tasks)
  - **Blocked By**: Task 2 (needs Dockerfile)

  **References**:

  **Pattern References**:
  - `PLAN.md:244-297` — Complete frontend directory structure
  - `PLAN.md:249-251` — Root layout description
  - `PLAN.md:280-283` — Component organization
  - `PLAN.md:296-297` — next.config.ts and package.json

  **External References**:
  - Next.js 15 App Router: `https://nextjs.org/docs/app`
  - shadcn/ui installation: `https://ui.shadcn.com/docs/installation/next`
  - TanStack Query: `https://tanstack.com/query/latest/docs/framework/react/overview`

  **WHY Each Reference Matters**:
  - Frontend structure from PLAN.md defines the exact route layout the app needs
  - shadcn/ui must be initialized with correct style/color or components look wrong
  - TanStack Query global config (staleTime, retry) should be set up early

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Next.js development server starts
    Tool: Bash
    Preconditions: Frontend directory created
    Steps:
      1. Run: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d frontend
      2. Wait 20s for Next.js compilation
      3. Run: curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
      4. Check status code is 200
    Expected Result: Frontend serves pages on port 3000
    Failure Indicators: Compilation error, module not found, TypeScript error
    Evidence: .sisyphus/evidence/s1-task-4-frontend-start.txt

  Scenario: Directory structure matches PLAN.md
    Tool: Bash
    Preconditions: Frontend initialized
    Steps:
      1. Run: find frontend/app -name "*.tsx" | sort
      2. Verify layout.tsx, page.tsx exist in app/
      3. Verify (dashboard)/layout.tsx exists
      4. Verify crawls/page.tsx, crawls/new/page.tsx, crawls/[crawlId]/page.tsx exist
      5. Verify components/ui/ directory has shadcn components
    Expected Result: All routes and component directories present
    Failure Indicators: Missing route files, no shadcn components
    Evidence: .sisyphus/evidence/s1-task-4-structure.txt
  ```

  **Evidence to Capture:**
  - [ ] s1-task-4-frontend-start.txt — dev server startup verification
  - [ ] s1-task-4-structure.txt — directory structure listing

  **Commit**: NO (no git repo)

---

- [ ] 5. PostgreSQL Schema + Alembic Migrations

  **What to do**:
  - Create `backend/app/db/init.sql` — PostgreSQL extension setup:
    ```sql
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";
    -- pgvector deferred to Sprint 4 (AI features)
    ```
  - Configure Alembic in `backend/`:
    - `alembic init app/db/migrations`
    - Edit `alembic.ini`: set sqlalchemy.url placeholder
    - Edit `app/db/migrations/env.py`: use **synchronous psycopg2** driver for migrations (NOT asyncpg), read DATABASE_URL from env and swap `asyncpg` → `psycopg2`
  - Create initial migration with these 6 tables (using raw `op.execute()` for partitioned tables):
    - `projects` — exactly as PLAN.md:1261-1272
    - `crawls` — exactly as PLAN.md:1276-1294
    - `crawled_urls` — PLAN.md:1309-1350 BUT with these changes:
      - `id` column: `UUID DEFAULT gen_random_uuid()` instead of BIGSERIAL (avoids sequence contention)
      - **4 partitions** instead of 16 (simpler for Sprint 1, can expand later)
      - Use `op.execute()` for CREATE TABLE ... PARTITION BY HASH and CREATE TABLE partitions
    - `page_links` — PLAN.md:1372-1389, change `source_url_id BIGINT` to `source_url_id UUID`
    - `url_issues` — PLAN.md:1394-1408, change `id` to UUID, **4 partitions** instead of 16
    - `redirects` — PLAN.md:1413-1425
  - Create TSVECTOR trigger for crawled_urls (PLAN.md:1352-1369)
  - Add `init.sql` to docker-compose db service via volume mount: `./backend/app/db/init.sql:/docker-entrypoint-initdb.d/init.sql`
  - Verify migration runs: `alembic upgrade head` in Docker container

  **Must NOT do**:
  - Don't create crawl_configs table (saved profiles deferred)
  - Don't create images, structured_data, hreflang_tags, sitemaps, etc. (Sprint 2+)
  - Don't create embeddings or ai_results tables (Sprint 4+)
  - Don't use 16 partitions — use 4 for Sprint 1 simplicity
  - Don't use BIGSERIAL for partitioned table IDs — use UUID gen_random_uuid()

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex SQL with partitioning, Alembic configuration, multiple interconnected DDL statements
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T4)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 6, 7, 8 (all DB-dependent tasks)
  - **Blocked By**: Task 1 (needs verified deps), Task 2 (needs Docker Compose)

  **References**:

  **Pattern References**:
  - `PLAN.md:1228-1270` — Schema overview + projects table
  - `PLAN.md:1274-1294` — crawls table
  - `PLAN.md:1307-1369` — crawled_urls (HASH partitioned) + TSVECTOR trigger
  - `PLAN.md:1371-1389` — page_links table
  - `PLAN.md:1392-1408` — url_issues (HASH partitioned)
  - `PLAN.md:1411-1425` — redirects table
  - `PLAN.md:1639-1669` — ER Diagram showing relationships

  **External References**:
  - Alembic with asyncpg: Must use sync driver in env.py — `https://alembic.sqlalchemy.org/en/latest/cookbook.html`
  - PostgreSQL HASH partitioning: `https://www.postgresql.org/docs/16/ddl-partitioning.html`

  **WHY Each Reference Matters**:
  - PLAN.md has the exact CREATE TABLE statements — copy them with UUID modification
  - HASH partition DDL must use raw op.execute() — Alembic autogenerate doesn't understand partitions
  - Alembic env.py must swap asyncpg→psycopg2 or migrations will fail with async driver errors
  - TSVECTOR trigger must be created in same migration as crawled_urls table

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Alembic migration creates all tables
    Tool: Bash
    Preconditions: Docker Compose db service running
    Steps:
      1. Run: docker compose up -d db
      2. Wait 10s for PostgreSQL startup
      3. Run: docker compose run --rm backend alembic upgrade head
      4. Check exit code is 0
      5. Run: docker compose exec db psql -U postgres -d seo_spider -c "\dt" | grep -c "projects\|crawls\|crawled_urls\|page_links\|url_issues\|redirects"
      6. Assert count >= 6
    Expected Result: All 6 tables created (plus partition tables)
    Failure Indicators: Migration error, missing table, partition creation failure
    Evidence: .sisyphus/evidence/s1-task-5-migration.txt

  Scenario: HASH partitions exist for crawled_urls
    Tool: Bash
    Preconditions: Migration completed
    Steps:
      1. Run: docker compose exec db psql -U postgres -d seo_spider -c "SELECT tablename FROM pg_tables WHERE tablename LIKE 'crawled_urls_%' ORDER BY tablename"
      2. Assert 4 partition tables exist (crawled_urls_0 through crawled_urls_3)
      3. Run same for url_issues partitions
    Expected Result: 4 partitions each for crawled_urls and url_issues
    Failure Indicators: No partitions, wrong number of partitions
    Evidence: .sisyphus/evidence/s1-task-5-partitions.txt

  Scenario: UUID primary keys work on partitioned tables
    Tool: Bash
    Preconditions: Migration completed
    Steps:
      1. Run: docker compose exec db psql -U postgres -d seo_spider -c "INSERT INTO projects (name, domain) VALUES ('test', 'example.com') RETURNING id"
      2. Capture project_id
      3. Run: INSERT INTO crawls with project_id, capture crawl_id
      4. Run: INSERT INTO crawled_urls with crawl_id, verify UUID generated and routed to correct partition
    Expected Result: Inserts succeed, UUIDs generated, data routed to partitions
    Failure Indicators: Insert failure, partition routing error, UUID generation error
    Evidence: .sisyphus/evidence/s1-task-5-uuid-test.txt
  ```

  **Evidence to Capture:**
  - [ ] s1-task-5-migration.txt — alembic upgrade head output + table listing
  - [ ] s1-task-5-partitions.txt — partition table verification
  - [ ] s1-task-5-uuid-test.txt — UUID insert test on partitioned tables

  **Commit**: NO (no git repo)

- [ ] 6. Backend Config, DB Session, Redis Client, Health Endpoint

  **What to do**:
  - Implement `app/core/config.py`: Pydantic `Settings` class with all env vars (DATABASE_URL, REDIS_URL, CORS_ORIGINS, LOG_LEVEL, MAX_CRAWL_URLS, MAX_CRAWL_DEPTH, MAX_THREADS, RATE_LIMIT_RPS)
  - Implement `app/db/session.py`:
    - `create_async_engine(DATABASE_URL)` with pool settings: `pool_size=20, max_overflow=10, pool_timeout=30, pool_recycle=1800`
    - `async_sessionmaker` with `expire_on_commit=False`
    - Raw asyncpg pool creation for COPY operations: `asyncpg.create_pool(DSN, min_size=5, max_size=20)`
  - Implement `app/api/deps.py`:
    - `get_db()` — async generator yielding SQLAlchemy session
    - `get_redis()` — returns Redis client from `redis.asyncio`
    - `get_asyncpg_pool()` — returns raw asyncpg pool for bulk operations
  - Implement `app/api/v1/router.py`: Aggregate router (empty for now, populated in Task 17)
  - Implement health endpoint in `main.py` or `app/api/v1/health.py`:
    - `GET /api/v1/health` → checks DB connection (execute `SELECT 1`) + Redis PING
    - Returns `{"status": "healthy", "services": {"database": "ok", "redis": "ok"}}`
  - Wire up CORS middleware in `main.py`
  - Wire up custom exception handlers from `exceptions.py`

  **Must NOT do**:
  - Don't implement any business logic endpoints
  - Don't implement WebSocket manager yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward wiring of already-designed components
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7, T8, T9, T10)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 7-20 (everything needs DB session and Redis)
  - **Blocked By**: Tasks 3, 5

  **References**:

  **Pattern References**:
  - `PLAN.md:320-322` — core/ module descriptions
  - `PLAN.md:307-308` — deps.py description
  - `PLAN.md:364` — db/session.py description

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Health endpoint returns healthy status
    Tool: Bash
    Preconditions: Docker Compose stack running
    Steps:
      1. Run: docker compose up -d backend db redis
      2. Wait 15s
      3. Run: curl -s http://localhost:8000/api/v1/health
      4. Assert response contains "healthy" and both services "ok"
    Expected Result: {"status":"healthy","services":{"database":"ok","redis":"ok"}}
    Failure Indicators: Connection refused, database/redis connection error
    Evidence: .sisyphus/evidence/s1-task-6-health.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 7. SQLAlchemy Models + Pydantic Schemas

  **What to do**:
  - Create SQLAlchemy ORM models in `backend/app/models/`:
    - `base.py`: DeclarativeBase with common columns (created_at, updated_at)
    - `project.py`: Project model mapping to `projects` table
    - `crawl.py`: Crawl model mapping to `crawls` table (status enum, config JSONB)
    - `url.py`: CrawledUrl model mapping to `crawled_urls` table (all columns from schema)
    - `link.py`: PageLink model mapping to `page_links` table
    - `issue.py`: UrlIssue model mapping to `url_issues` table
    - `redirect.py`: Redirect model mapping to `redirects` table
  - Create Pydantic schemas in `backend/app/schemas/`:
    - `project.py`: ProjectCreate, ProjectUpdate, ProjectResponse
    - `crawl.py`: CrawlCreate (start_url, mode, config), CrawlResponse, CrawlSummary, CrawlConfig (max_urls, max_depth, threads, rate_limit, user_agent, robots_mode, include_patterns, exclude_patterns)
    - `url.py`: CrawledUrlResponse, UrlDetail (all fields)
    - `pagination.py`: PaginationParams (cursor, limit), CursorPage[T] generic response
    - `common.py`: HealthResponse, ErrorResponse
  - Ensure UUID fields use `uuid.UUID` in both SQLAlchemy models and Pydantic schemas
  - Map CrawlStatus enum: `idle`, `configuring`, `queued`, `crawling`, `paused`, `completing`, `completed`, `failed`, `cancelled`

  **Must NOT do**:
  - Don't create models for Sprint 2+ tables (images, structured_data, etc.)
  - Don't add validation logic beyond basic field constraints

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple interconnected model/schema files with strict type alignment
  - **Skills**: [`pydantic-models-py`]
    - `pydantic-models-py`: Create Pydantic models following Base/Create/Update/Response pattern

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6, T9, T10)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 8, 11, 12, 14, 16, 17
  - **Blocked By**: Tasks 5, 6

  **References**:

  **Pattern References**:
  - `PLAN.md:1261-1425` — All 6 table definitions with exact column specs, types, defaults, constraints
  - `PLAN.md:342-352` — models/ and schemas/ directory structure
  - `PLAN.md:1280` — CrawlStatus enum values
  - `PLAN.md:1333` — seo_data JSONB field for flexible overflow

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All models import without errors
    Tool: Bash
    Preconditions: Backend directory with models
    Steps:
      1. Run: docker compose exec backend python -c "from app.models.project import Project; from app.models.crawl import Crawl; from app.models.url import CrawledUrl; from app.models.link import PageLink; from app.models.issue import UrlIssue; from app.models.redirect import Redirect; print('ALL MODELS OK')"
      2. Assert output contains "ALL MODELS OK"
    Expected Result: All models import cleanly
    Failure Indicators: ImportError, column type mismatch
    Evidence: .sisyphus/evidence/s1-task-7-models.txt

  Scenario: Pydantic schemas validate correctly
    Tool: Bash
    Preconditions: Schemas created
    Steps:
      1. Run: docker compose exec backend python -c "from app.schemas.crawl import CrawlCreate; c = CrawlCreate(start_url='https://example.com', mode='spider', config={'max_urls': 100}); print(c.model_dump_json())"
      2. Assert valid JSON output with all fields
    Expected Result: Schema validates and serializes correctly
    Failure Indicators: ValidationError, missing field, type error
    Evidence: .sisyphus/evidence/s1-task-7-schemas.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 8. Repository Layer (Projects, Crawls, URLs CRUD)

  **What to do**:
  - Create `backend/app/repositories/base.py`:
    - Generic CRUD base with keyset/cursor pagination (NOT OFFSET)
    - `list_paginated(cursor, limit, filters)` → `CursorPage[T]`
    - Cursor = last seen `id` (UUID), `WHERE id > cursor ORDER BY id LIMIT N+1`
  - Create `backend/app/repositories/project_repo.py`:
    - `create(data)`, `get_by_id(id)`, `list_all(cursor, limit)`, `update(id, data)`, `delete(id)`
  - Create `backend/app/repositories/crawl_repo.py`:
    - `create(project_id, data)`, `get_by_id(id)`, `list_by_project(project_id, cursor, limit)`, `update_status(id, status)`, `delete(id)`
    - `increment_crawled_count(id)`, `set_error_count(id, count)`
  - Create `backend/app/repositories/url_repo.py`:
    - `list_by_crawl(crawl_id, cursor, limit, filters)`, `get_by_id(id)`, `get_by_url_hash(crawl_id, url_hash)`
    - Uses SQLAlchemy Core queries (not ORM) for performance on large datasets
  - All repositories use injected `AsyncSession` from deps

  **Must NOT do**:
  - Don't implement bulk insert (Task 12 handles asyncpg COPY)
  - Don't implement complex filter logic (Sprint 2+)
  - Don't use OFFSET pagination — use keyset/cursor only

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple repository files with shared base class, cursor pagination logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T9, T10)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 16, 17
  - **Blocked By**: Task 7

  **References**:

  **Pattern References**:
  - `PLAN.md:353-357` — repositories/ directory structure
  - `PLAN.md:354` — "Generic keyset-paginated CRUD base"
  - `PLAN.md:2108-2133` — API pagination spec (cursor-based)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Repository CRUD operations work
    Tool: Bash
    Preconditions: Database migrated, backend running
    Steps:
      1. Run Python script via docker exec that:
         a. Creates a project via project_repo.create()
         b. Retrieves it via project_repo.get_by_id()
         c. Lists all projects via project_repo.list_all()
         d. Updates name via project_repo.update()
         e. Deletes via project_repo.delete()
      2. Assert each operation returns expected data
    Expected Result: Full CRUD lifecycle works
    Failure Indicators: SQL error, missing column, UUID handling error
    Evidence: .sisyphus/evidence/s1-task-8-crud.txt

  Scenario: Cursor pagination returns correct pages
    Tool: Bash
    Preconditions: Multiple records in database
    Steps:
      1. Insert 10 projects
      2. Fetch page 1: list_all(cursor=None, limit=3)
      3. Assert 3 items + has_more=true + next_cursor set
      4. Fetch page 2: list_all(cursor=next_cursor, limit=3)
      5. Assert 3 different items
    Expected Result: Correct pagination without duplicates or gaps
    Failure Indicators: Wrong page size, duplicates, missing next_cursor
    Evidence: .sisyphus/evidence/s1-task-8-pagination.txt
  ```

  **Commit**: NO (no git repo)

- [ ] 9. URL Frontier (Redis Sorted Sets + Bloom Filter)

  **What to do**:
  - Create `backend/app/crawler/frontier.py`:
    - Class `URLFrontier` with Redis connection
    - **Priority sorted set**: `ZADD crawl:{crawl_id}:frontier {depth} {url}` (depth as score for BFS)
    - `add(url, depth)` — normalize URL, check Bloom filter, ZADD NX (no re-add)
    - `add_batch(urls_with_depths)` — batch add via pipeline
    - `pop()` — `ZPOPMIN crawl:{crawl_id}:frontier` → returns (url, depth)
    - `size()` — `ZCARD crawl:{crawl_id}:frontier`
    - `is_empty()` — check size == 0
    - `clear()` — delete frontier key
  - **URL Normalization** function (standalone utility in `crawler/utils.py`):
    1. Lowercase scheme and host
    2. Decode percent-encoding (except reserved)
    3. Remove fragment (#anchor)
    4. Normalize trailing slash (add if path is directory-like)
    5. Reject: `data:`, `javascript:`, `mailto:`, `tel:` URIs
    6. Resolve relative URLs against base URL
    7. Generate MD5 hash of normalized URL → `url_hash` field
  - **Bloom Filter** for fast URL dedup:
    - If pybloom-live works (from Task 1): use `ScalableBloomFilter(initial_capacity=100_000, error_rate=0.001)`
    - If not: use RedisBloom (`BF.ADD`/`BF.EXISTS`) or Python `set()`
    - `check_and_add(url_hash)` → returns True if new (not seen), False if duplicate
    - In-memory only — no persistence (Sprint 1 guardrail)
  - **Per-domain rate limiting** (simple version):
    - Redis key `crawl:{crawl_id}:domain_cooldown:{domain}` with TTL = rate_limit_seconds
    - `can_fetch(domain)` → check if key exists (if exists: wait, if not: set key with TTL)
    - No per-domain back queues (Sprint 1 guardrail)

  **Must NOT do**:
  - Don't implement per-domain back queues (FIFO per domain)
  - Don't persist Bloom filter to Redis
  - Don't implement IDN/punycode URL normalization (edge case deferred)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core algorithmic component with Redis data structures, concurrency considerations
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7, T8, T10)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 14 (CrawlEngine)
  - **Blocked By**: Tasks 6 (Redis client)

  **References**:

  **Pattern References**:
  - `PLAN.md:1675-1707` — URL Frontier Architecture (front queues, dedup, normalization)
  - `PLAN.md:325` — frontier.py description
  - `PLAN.md:408` — Bloom filter specs (ScalableBloomFilter, ~12MB per 1M URLs)

  **External References**:
  - Redis Sorted Sets: `ZADD`, `ZPOPMIN`, `ZCARD`
  - pybloom-live: `ScalableBloomFilter` API

  **WHY Each Reference Matters**:
  - Frontier architecture defines BFS ordering via depth-as-score — CRITICAL for correct crawl behavior
  - URL normalization algorithm must match exactly or duplicate URLs won't be caught
  - Bloom filter choice affects memory usage at scale

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Frontier maintains BFS order (depth-first dequeue)
    Tool: Bash
    Preconditions: Redis running
    Steps:
      1. Create frontier instance
      2. Add URLs at depth 0, 1, 2 in random order
      3. Pop all URLs
      4. Assert they come out in depth order (0, 0, 1, 1, 2, 2)
    Expected Result: BFS ordering maintained via sorted set scores
    Failure Indicators: Wrong order, missing URLs
    Evidence: .sisyphus/evidence/s1-task-9-bfs-order.txt

  Scenario: Bloom filter prevents duplicate URLs
    Tool: Bash
    Preconditions: Frontier with Bloom filter
    Steps:
      1. Add URL "https://example.com/page1"
      2. Try to add same URL again
      3. Assert second add returns False (duplicate)
      4. Add URL "https://example.com/page2"
      5. Assert it returns True (new)
    Expected Result: Duplicates rejected, new URLs accepted
    Failure Indicators: Duplicate accepted, new URL rejected
    Evidence: .sisyphus/evidence/s1-task-9-dedup.txt

  Scenario: URL normalization handles edge cases
    Tool: Bash
    Preconditions: Utils module available
    Steps:
      1. Test: "HTTP://Example.COM/Page" → "http://example.com/Page"
      2. Test: "http://example.com/page#section" → "http://example.com/page"
      3. Test: "javascript:void(0)" → rejected
      4. Test: relative URL "./about" with base "http://example.com/blog/" → "http://example.com/blog/about"
    Expected Result: All normalization rules applied correctly
    Failure Indicators: Wrong scheme, fragment not stripped, relative not resolved
    Evidence: .sisyphus/evidence/s1-task-9-normalize.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 10. Fetcher Pool (aiohttp + Rate Limiter + Redirect Tracking)

  **What to do**:
  - Create `backend/app/crawler/fetcher.py`:
    - Class `FetcherPool` managing HTTP requests
    - **aiohttp Session Configuration**:
      - ONE `ClientSession` per crawl (created in constructor, closed in cleanup)
      - `TCPConnector(limit=0, limit_per_host=2, ttl_dns_cache=300, enable_cleanup_closed=True)`
      - Control concurrency via `asyncio.Semaphore(max_threads)` at engine level
    - **Timeout configuration**: `ClientTimeout(total=30, connect=10, sock_read=20)`
    - **fetch(url)** method:
      - Acquire semaphore slot
      - Send GET request with configured User-Agent
      - Manual redirect following (`allow_redirects=False`)
      - Track each redirect hop → build redirect chain list of `{url, status_code}`
      - Detect redirect loops (URL seen in current chain)
      - Max 10 redirect hops
      - ALWAYS consume response body (even on error paths) to prevent connection leaks
      - Return `FetchResult(url, final_url, status_code, headers, body, redirect_chain, response_time_ms, content_type, error)`
    - **Retry with exponential backoff**:
      - `delay = min(2^attempt, 60)` seconds
      - Max 3 retries per URL
      - Retry on: connection errors, timeouts, 5XX (except 501)
      - No retry on: 4XX (except 429)
      - HTTP 429: domain-specific backoff (30s → 60s → 120s)
    - **Error handling**:
      - `ClientConnectorError`: log, mark URL as error, don't retry DNS failures
      - `ClientResponseError`: store status code, retry if 5XX
      - `asyncio.TimeoutError`: log, retry
    - **Self-signed cert support**: optional `ssl=False` parameter in connector

  **Must NOT do**:
  - Don't implement circuit breaker pattern
  - Don't implement checkpoint/resume
  - Don't create session-per-request (one session per crawl)
  - Don't implement Playwright/JS rendering

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex async networking with redirect tracking, error handling, concurrency control
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7, T8, T9)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 11, 14 (parser needs fetch results, engine needs fetcher)
  - **Blocked By**: Task 6 (needs config)

  **References**:

  **Pattern References**:
  - `PLAN.md:1711-1751` — Fetcher Pool Design (connector config, timeouts, rate limiter, redirect handling, retry, anti-bot)
  - `PLAN.md:326` — fetcher.py description
  - `PLAN.md:471-479` — Feature 1.5 HTTP Response Handling spec

  **WHY Each Reference Matters**:
  - Fetcher Pool Design has exact aiohttp configuration values — use them
  - Redirect handling spec defines max hops, loop detection algorithm
  - HTTP Response Handling feature defines what status codes to track and how

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Fetcher retrieves page with correct metadata
    Tool: Bash
    Preconditions: Backend running with fetcher module
    Steps:
      1. Fetch https://books.toscrape.com/ via fetcher
      2. Assert status_code == 200
      3. Assert content_type contains "text/html"
      4. Assert body length > 0
      5. Assert response_time_ms > 0
    Expected Result: Successful fetch with all metadata captured
    Failure Indicators: Connection error, missing metadata, empty body
    Evidence: .sisyphus/evidence/s1-task-10-fetch.txt

  Scenario: Redirect chain tracked correctly
    Tool: Bash
    Preconditions: Fetcher available
    Steps:
      1. Fetch a URL that returns 301 redirect (e.g., http://example.com → https://example.com)
      2. Assert redirect_chain contains at least one hop with status 301
      3. Assert final_url != original url
    Expected Result: Redirect chain recorded with each hop's URL and status
    Failure Indicators: Missing redirect chain, infinite loop, wrong status
    Evidence: .sisyphus/evidence/s1-task-10-redirects.txt

  Scenario: Retry on 5XX with backoff
    Tool: Bash
    Preconditions: Mock server or known 5XX URL
    Steps:
      1. Fetch a URL that returns 500
      2. Assert 3 retry attempts were made
      3. Assert exponential backoff timing (1s, 2s, 4s)
    Expected Result: Retries attempted with increasing delay
    Failure Indicators: No retries, wrong delay, crash on error
    Evidence: .sisyphus/evidence/s1-task-10-retry.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 11. Parser Pool (selectolax Extraction Pipeline)

  **What to do**:
  - Create `backend/app/crawler/parser.py`:
    - Class `ParserPool` for HTML extraction
    - **Primary parser**: selectolax `HTMLParser`
    - `parse(html_content, base_url)` → returns `PageData` dataclass
    - **PageData** dataclass (raw fields only — NO Issue generation):
      ```python
      @dataclass
      class PageData:
          title: str | None
          title_length: int | None
          meta_description: str | None
          meta_desc_length: int | None
          h1: list[str]
          h2: list[str]
          canonical_url: str | None
          robots_meta: list[str]   # noindex, nofollow, etc.
          is_indexable: bool
          indexability_reason: str | None
          word_count: int
          content_hash: bytes     # MD5 of normalized content
          links: list[LinkData]
          images: list[ImageData]
          hreflang_tags: list[HreflangData]
          structured_data_blocks: list[dict]  # raw JSON-LD
          og_tags: dict
      ```
    - **Extraction order** (from PLAN.md Section 5c):
      1. `<title>` — page title
      2. `<meta name="description">` — meta description
      3. `<meta name="robots">` — robots directives
      4. `<link rel="canonical">` — canonical URL
      5. `<h1>`, `<h2>` — headings
      6. `<a href>` — all links (internal + external), resolve relative URLs
      7. `<img src>`, `<img srcset>` — images with alt text
      8. `<link rel="alternate" hreflang>` — hreflang
      9. `<script type="application/ld+json">` — structured data
      10. `<meta property="og:*">` — Open Graph
    - **LinkData** dataclass: `url`, `anchor_text`, `rel_attrs` (nofollow, etc.), `link_type` (internal/external/resource), `is_same_domain(base_domain)` helper
    - **Content cleanup** before word count: decompose script, style, noscript, template tags → strip HTML → normalize whitespace → count words
    - **Content hashing**: MD5 of normalized HTML for exact-duplicate detection
    - **Charset detection**: read Content-Type header charset, fall back to `<meta charset>`, then chardet library

  **Must NOT do**:
  - Don't generate Issue records (missing_title, title_too_long, etc.) — that's Sprint 2
  - Don't implement lxml XPath extraction (Sprint 4 Custom Extraction)
  - Don't implement SimHash near-duplicate (Sprint 2 post-crawl analysis)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex HTML parsing with many extraction targets, charset handling, content normalization
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T12, T13)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 14 (CrawlEngine)
  - **Blocked By**: Tasks 7 (needs data models), T10 (parser processes fetch results)

  **References**:

  **Pattern References**:
  - `PLAN.md:1755-1784` — Parser Pipeline (dual-parser architecture, extraction order, content cleanup, hashing)
  - `PLAN.md:327` — parser.py description
  - `PLAN.md:434-446` — Feature 1.3 URL Discovery spec (all link types to extract)
  - `PLAN.md:401` — Data fields to extract per page

  **WHY Each Reference Matters**:
  - Extraction order from PLAN.md must be followed to ensure consistent data extraction
  - Feature 1.3 defines ALL link types to extract (a, img, link, script, iframe, meta refresh, etc.)
  - Content cleanup algorithm determines accurate word count

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Parser extracts all fields from real HTML
    Tool: Bash
    Preconditions: Parser module available
    Steps:
      1. Fetch https://books.toscrape.com/ HTML
      2. Parse with ParserPool
      3. Assert title is not None and contains "Books to Scrape"
      4. Assert h1 list is not empty
      5. Assert links list has > 10 internal links
      6. Assert word_count > 0
    Expected Result: All PageData fields populated from real HTML
    Failure Indicators: None title, empty links, zero word_count
    Evidence: .sisyphus/evidence/s1-task-11-parse.txt

  Scenario: Link extraction classifies internal vs external correctly
    Tool: Bash
    Preconditions: Parser with HTML containing both link types
    Steps:
      1. Parse HTML with links to same domain and external domains
      2. Assert internal links have link_type='internal'
      3. Assert external links have link_type='external'
      4. Assert resource links (CSS, JS) have link_type='resource'
    Expected Result: Correct classification of all link types
    Failure Indicators: Wrong classification, missing links
    Evidence: .sisyphus/evidence/s1-task-11-links.txt

  Scenario: Content cleanup removes scripts and styles
    Tool: Bash
    Preconditions: Parser available
    Steps:
      1. Parse HTML with <script>, <style>, <noscript> containing text
      2. Assert word_count does NOT include words from script/style tags
      3. Assert only visible content is counted
    Expected Result: Script/style content excluded from word count
    Failure Indicators: Inflated word count, script text in content
    Evidence: .sisyphus/evidence/s1-task-11-cleanup.txt
  ```

  **Commit**: NO (no git repo)

- [ ] 12. Batch Inserter (asyncpg COPY with Error Isolation)

  **What to do**:
  - Create `backend/app/crawler/inserter.py`:
    - Class `BatchInserter` managing bulk DB writes
    - **Buffer strategy**: accumulate rows in memory, flush when 500 rows OR 2 seconds elapsed
    - **Flush on**: crawl pause, stop, complete, or buffer full
    - **asyncpg COPY** via `connection.copy_records_to_table()`:
      - Write to parent table name (PostgreSQL routes to correct partition)
      - Pre-generate UUIDs in Python for all `id` fields (COPY has no RETURNING)
    - **Error isolation strategy** (from Metis consultation):
      - Try COPY first (fast path: ~50k rows/sec)
      - On failure: fall back to individual INSERTs to isolate bad rows
      - Bad rows logged with error details for debugging
    - **Tables written per flush**:
      - `crawled_urls` — one row per crawled URL
      - `page_links` — one row per discovered link
      - `redirects` — one row per redirect hop
    - Methods:
      - `add_url(crawl_id, url_data: PageData, fetch_result: FetchResult)` → buffer
      - `add_links(crawl_id, source_url_id, links: list[LinkData])` → buffer
      - `add_redirects(crawl_id, chain: list[RedirectHop])` → buffer
      - `flush()` → COPY all buffers to DB
      - `close()` → final flush + cleanup

  **Must NOT do**:
  - Don't use staging/temp table pattern (overkill for Sprint 1 — try/except is simpler)
  - Don't write to url_issues table (empty until Sprint 2)
  - Don't implement partial RETURNING workarounds

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Low-level asyncpg COPY protocol, buffer management, error isolation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T11, T13)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 14 (CrawlEngine)
  - **Blocked By**: Tasks 7 (models), T6 (asyncpg pool)

  **References**:

  **Pattern References**:
  - `PLAN.md:1815-1836` — Batch Inserter specification (COPY protocol, buffer strategy, error handling, tables written)
  - Metis consultation — asyncpg COPY error handling: try/except fallback to individual INSERTs

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Batch insert writes correct data to partitioned table
    Tool: Bash
    Preconditions: DB migrated, asyncpg pool available
    Steps:
      1. Create a test crawl record
      2. Buffer 10 URL records via add_url()
      3. Call flush()
      4. Query crawled_urls: SELECT COUNT(*) WHERE crawl_id=test_id
      5. Assert count == 10
    Expected Result: All 10 records written to correct partition
    Failure Indicators: Missing records, partition routing error, UUID error
    Evidence: .sisyphus/evidence/s1-task-12-batch.txt

  Scenario: Error isolation handles one bad row gracefully
    Tool: Bash
    Preconditions: BatchInserter available
    Steps:
      1. Buffer 9 valid URL records + 1 record with invalid data (e.g., NULL for NOT NULL field)
      2. Call flush()
      3. Assert 9 records written successfully
      4. Assert error logged for the bad row
    Expected Result: Good rows saved, bad row isolated and logged
    Failure Indicators: All 10 lost, no error logging, crash
    Evidence: .sisyphus/evidence/s1-task-12-error.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 13. Robots.txt Parser + Per-Domain Cache

  **What to do**:
  - Create `backend/app/crawler/robots.py`:
    - Class `RobotsChecker` managing robots.txt compliance
    - **Fetch and parse** robots.txt for each domain encountered:
      - Fetch `{scheme}://{domain}/robots.txt`
      - Parse using Python `urllib.robotparser.RobotFileParser`
      - Cache parsed result in Redis: `crawl:{crawl_id}:robots:{domain}` with TTL 3600s
    - `can_fetch(url, user_agent)` → check if URL is allowed by robots.txt
    - `get_crawl_delay(domain, user_agent)` → extract Crawl-delay directive
    - **Modes** (from crawl config):
      - `respect`: obey robots.txt (default)
      - `ignore`: skip robots.txt entirely
    - **Error handling**:
      - robots.txt returns 404/5XX → treat as "allow all"
      - robots.txt fetch timeout → treat as "allow all"
      - robots.txt too large (>500KB) → ignore, treat as "allow all"
    - Cache invalidation: one fetch per domain per crawl session

  **Must NOT do**:
  - Don't implement "Ignore but Report" mode (Sprint 2+)
  - Don't implement custom robots.txt editor
  - Don't implement per-subdomain robots.txt (one per domain)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Standard parsing with caching, well-defined spec
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T11, T12)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 14 (CrawlEngine)
  - **Blocked By**: Task 6 (Redis client)

  **References**:

  **Pattern References**:
  - `PLAN.md:483-495` — Feature 1.6 Robots.txt spec (3 modes, block reporting, custom editor)
  - `PLAN.md:330` — robots.py description
  - `PLAN.md:1729-1731` — Crawl-delay respect in Fetcher Pool

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Robots.txt blocks disallowed URLs
    Tool: Bash
    Preconditions: RobotsChecker available, Redis running
    Steps:
      1. Fetch robots.txt for books.toscrape.com
      2. Test can_fetch() for an allowed URL → True
      3. Test can_fetch() for a typical disallowed path → matches robots.txt
    Expected Result: Allowed URLs return True, disallowed return False
    Failure Indicators: Wrong allow/disallow, cache miss, parse error
    Evidence: .sisyphus/evidence/s1-task-13-robots.txt

  Scenario: Missing robots.txt treated as allow-all
    Tool: Bash
    Preconditions: RobotsChecker available
    Steps:
      1. Check a domain that returns 404 for /robots.txt
      2. Assert can_fetch() returns True for any path
    Expected Result: Missing robots.txt = all URLs allowed
    Failure Indicators: False negative, exception on 404
    Evidence: .sisyphus/evidence/s1-task-13-missing.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 14. Crawl Engine Coordinator

  **What to do**:
  - Create `backend/app/crawler/engine.py`:
    - Class `CrawlEngine` — the main orchestrator that ties frontier → fetcher → parser → inserter
    - **Initialization**: receives crawl_id, config, Redis, asyncpg pool
    - **Main crawl loop** (async):
      ```python
      async def run(self):
          self.frontier.add(self.start_url, depth=0)
          while not self.frontier.is_empty() and not self.stopped:
              if self.paused:
                  await asyncio.sleep(0.5)
                  continue
              # Check limits
              if self.crawled_count >= self.config.max_urls:
                  break
              # Get next URL from frontier
              url, depth = await self.frontier.pop()
              if depth > self.config.max_depth:
                  continue
              # Check robots.txt
              if not await self.robots.can_fetch(url, self.config.user_agent):
                  continue
              # Rate limit check
              domain = extract_domain(url)
              await self.rate_limiter.wait(domain)
              # Fetch
              result = await self.fetcher.fetch(url)
              # Parse (if HTML)
              page_data = None
              if result.is_html:
                  page_data = self.parser.parse(result.body, result.final_url)
                  # Add discovered links to frontier (internal only, within scope)
                  for link in page_data.links:
                      if link.is_internal and link.url not in self.frontier:
                          self.frontier.add(link.url, depth + 1)
              # Insert results
              url_id = uuid4()
              self.inserter.add_url(self.crawl_id, url_id, result, page_data, depth)
              if page_data:
                  self.inserter.add_links(self.crawl_id, url_id, page_data.links)
              if result.redirect_chain:
                  self.inserter.add_redirects(self.crawl_id, result.redirect_chain)
              # Update stats
              self.crawled_count += 1
              # Publish progress event to Redis pub/sub
              await self.publish_progress()
          # Drain: flush inserter, update crawl status
          await self.inserter.flush()
          await self.complete()
      ```
    - **State management**: `paused`, `stopped` flags (set by external control via Redis or direct call)
    - **Scope checking**: only follow links within the start URL's effective domain (after initial redirects)
    - **Progress publishing**: `PUBLISH crawl:{crawl_id}:events {json_payload}` every 500ms or every 10 URLs
    - **Graceful shutdown**: on stop → set stopped flag, drain in-flight, flush inserter, update crawl status to `completed`/`cancelled`
    - **Error boundary**: wrap main loop in try/except, on unrecoverable error → set crawl status to `failed` with error message
    - **Edge cases from Metis**:
      - Start URL unreachable → set crawl FAILED immediately
      - Start URL returns non-HTML → store URL, don't extract links, complete with 1 URL
      - 10 consecutive domain failures → set crawl FAILED
      - Response body > 10MB → skip parsing, store URL with error

  **Must NOT do**:
  - Don't implement post-crawl analysis (PageRank, MinHash)
  - Don't implement checkpoint/resume
  - Don't implement multi-worker coordination
  - Don't implement circuit breaker

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core system coordinator, complex async control flow, state management, error handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential — depends on T9, T10, T11, T12, T13)
  - **Parallel Group**: Wave 4
  - **Blocks**: Tasks 15, 19 (ARQ worker, crawl control)
  - **Blocked By**: Tasks 9, 10, 11, 12, 13 (all crawler components)

  **References**:

  **Pattern References**:
  - `PLAN.md:324` — engine.py description: "CrawlEngine (async coordinator)"
  - `PLAN.md:60-143` — State machine diagram (idle→configuring→queued→crawling→paused→completing→completed/failed/cancelled)
  - `PLAN.md:394-412` — Feature 1.1 Spider Mode full spec
  - `PLAN.md:1675-1707` — URL Frontier interaction pattern
  - Metis consultation — Edge cases section (11 edge cases documented)

  **WHY Each Reference Matters**:
  - State machine defines ALL valid state transitions — engine must enforce them
  - Spider Mode spec defines BFS behavior, subdomain scope, data fields extracted
  - Edge cases from Metis prevent crashes on common real-world scenarios

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Engine crawls a small site end-to-end
    Tool: Bash
    Preconditions: All crawler components available, DB migrated
    Steps:
      1. Create project + crawl record in DB
      2. Instantiate CrawlEngine with start_url=https://books.toscrape.com, max_urls=20, max_depth=1
      3. Run engine
      4. Assert crawled_count > 0 and <= 20
      5. Assert crawl status = completed
      6. Query DB: SELECT COUNT(*) FROM crawled_urls WHERE crawl_id=...
      7. Assert DB count matches crawled_count
    Expected Result: Crawl completes with correct number of URLs stored in DB
    Failure Indicators: Hang, crash, wrong count, status not completed
    Evidence: .sisyphus/evidence/s1-task-14-crawl.txt

  Scenario: Engine respects max_urls limit
    Tool: Bash
    Preconditions: Engine available
    Steps:
      1. Set max_urls=5 for a site with many pages
      2. Run engine
      3. Assert crawled_count <= 5
    Expected Result: Crawl stops at limit
    Failure Indicators: More than 5 URLs crawled
    Evidence: .sisyphus/evidence/s1-task-14-limit.txt

  Scenario: Engine handles unreachable start URL
    Tool: Bash
    Preconditions: Engine available
    Steps:
      1. Set start_url to a non-existent domain
      2. Run engine
      3. Assert crawl status = failed
      4. Assert error message includes connection error info
    Expected Result: Crawl fails gracefully with informative error
    Failure Indicators: Hang, crash, no error message
    Evidence: .sisyphus/evidence/s1-task-14-unreachable.txt
  ```

  **Commit**: NO (no git repo)

- [ ] 15. ARQ Worker Setup + Crawl Task

  **What to do**:
  - Create `backend/app/worker/settings.py`:
    - ARQ `WorkerSettings` class with CRITICAL configuration (from Metis research):
      ```python
      class WorkerSettings:
          redis_settings = RedisSettings.from_dsn(REDIS_URL)
          functions = [start_crawl_job]
          job_timeout = 7200      # 2 hours max per crawl
          max_tries = 1           # Crawls are NOT idempotent — don't retry
          health_check_interval = 30  # Detect dead workers in <1 minute
          max_jobs = 1            # One crawl at a time per worker
      ```
  - Create `backend/app/worker/tasks/crawl_tasks.py`:
    - `async def start_crawl_job(ctx, crawl_id: str)`:
      - Load crawl config from DB
      - Create CrawlEngine instance with all components (frontier, fetcher, parser, inserter, robots)
      - Run engine
      - Handle exceptions → update crawl status to FAILED
      - Clean up resources (close aiohttp session, flush inserter)
  - Update docker-compose.yml worker command: `python -m arq app.worker.settings.WorkerSettings`

  **Must NOT do**:
  - Don't set max_tries > 1 (crawls are not idempotent)
  - Don't set job_timeout < 7200 (long crawls will be killed)
  - Don't enable retry_jobs

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: ARQ configuration is critical — wrong defaults cause silent failures
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T16)
  - **Parallel Group**: Wave 4
  - **Blocks**: Tasks 17, 18
  - **Blocked By**: Task 14 (needs CrawlEngine)

  **References**:

  **Pattern References**:
  - `PLAN.md:368-371` — worker/ directory structure
  - `PLAN.md:411` — "Task queue ด้วย ARQ (async-native, ใช้ Redis ที่มีอยู่แล้ว)"
  - Metis consultation — ARQ critical configuration values

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: ARQ worker starts and accepts jobs
    Tool: Bash
    Preconditions: Docker Compose running
    Steps:
      1. Run: docker compose logs worker | tail -10
      2. Assert log contains "Starting worker" or ARQ startup message
      3. Assert no ERROR in logs
    Expected Result: Worker running, ready to accept crawl jobs
    Failure Indicators: Startup error, Redis connection failure
    Evidence: .sisyphus/evidence/s1-task-15-worker.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 16. Service Layer (CrawlService, ProjectService)

  **What to do**:
  - Create `backend/app/services/crawl_service.py`:
    - `async def start_crawl(project_id, data: CrawlCreate)` → creates crawl record → enqueues ARQ job → returns crawl
    - `async def get_crawl(crawl_id)` → fetches crawl with stats
    - `async def pause_crawl(crawl_id)` → publish pause command to Redis `crawl:{id}:control`
    - `async def resume_crawl(crawl_id)` → publish resume command
    - `async def stop_crawl(crawl_id)` → publish stop command
    - `async def delete_crawl(crawl_id)` → delete crawl + cascade URLs
    - `async def list_crawls(project_id, cursor, limit)` → paginated list
  - Create `backend/app/services/project_service.py`:
    - Thin wrapper around ProjectRepository
    - `create_project`, `get_project`, `list_projects`, `update_project`, `delete_project`
  - Services inject repositories and Redis via constructor/deps
  - Crawl control commands published via Redis pub/sub: `PUBLISH crawl:{id}:control {command}`
  - CrawlEngine subscribes to control channel and reacts

  **Must NOT do**:
  - Don't implement analysis_service (Sprint 2)
  - Don't implement export_service (Sprint 5)
  - Don't implement report_service (Sprint 5)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Business logic orchestration, ARQ integration, Redis pub/sub for control
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T15)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 17 (API routes)
  - **Blocked By**: Tasks 8 (repositories), T14 (CrawlEngine for control flow)

  **References**:

  **Pattern References**:
  - `PLAN.md:358-362` — services/ directory structure
  - `PLAN.md:359` — "crawl_service.py — Orchestrates crawl lifecycle"

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: CrawlService creates crawl and enqueues job
    Tool: Bash
    Preconditions: DB + Redis + ARQ worker running
    Steps:
      1. Call crawl_service.start_crawl() with valid config
      2. Assert crawl record created in DB with status='queued'
      3. Assert ARQ job enqueued (check Redis for pending job)
    Expected Result: Crawl created and job queued
    Failure Indicators: DB error, job not enqueued, wrong status
    Evidence: .sisyphus/evidence/s1-task-16-service.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 17. API Routes — Projects + Crawls + URLs + Health (16 endpoints)

  **What to do**:
  - Create `backend/app/api/v1/projects.py`:
    - `POST /api/v1/projects` — create project
    - `GET /api/v1/projects` — list projects (cursor paginated)
    - `GET /api/v1/projects/{id}` — get project
    - `PUT /api/v1/projects/{id}` — update project
    - `DELETE /api/v1/projects/{id}` — delete project
  - Create `backend/app/api/v1/crawls.py`:
    - `POST /api/v1/projects/{id}/crawls` — start crawl (creates + enqueues)
    - `GET /api/v1/projects/{id}/crawls` — list crawls for project
    - `GET /api/v1/crawls/{id}` — get crawl detail (status, stats, config)
    - `POST /api/v1/crawls/{id}/pause` — pause crawl
    - `POST /api/v1/crawls/{id}/resume` — resume crawl
    - `POST /api/v1/crawls/{id}/stop` — stop crawl
    - `DELETE /api/v1/crawls/{id}` — delete crawl + data
    - `WS /api/v1/crawls/{id}/ws` — WebSocket (Task 18)
  - Create `backend/app/api/v1/urls.py`:
    - `GET /api/v1/crawls/{id}/urls` — list crawled URLs (cursor paginated, basic filters: status_code, content_type)
    - `GET /api/v1/crawls/{id}/urls/{urlId}` — get URL detail
  - Wire health endpoint: `GET /api/v1/health` (already in Task 6, just confirm wiring)
  - Update `app/api/v1/router.py` to include all routers
  - All endpoints return JSON with proper error responses (404, 422, 500)
  - All list endpoints use cursor/keyset pagination from CursorPage[T]

  **Must NOT do**:
  - Don't implement more than 16 endpoints
  - Don't implement reports, export, issues, extractors, integrations endpoints
  - Don't implement complex filtering (Sprint 2)
  - Don't implement the WebSocket endpoint here (Task 18)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple endpoint files with consistent patterns, request/response validation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs T8 repos + T15 worker + T16 services)
  - **Parallel Group**: Wave 4 (after T8, T15, T16)
  - **Blocks**: Tasks 21-24 (frontend), T26 (List Mode), T27 (smoke test)
  - **Blocked By**: Tasks 8, 15, 16

  **References**:

  **Pattern References**:
  - `PLAN.md:309-318` — API router file descriptions
  - `PLAN.md:1982-2133` — Full API Specification (all 50+ endpoints — only implement Sprint 1 set)
  - Metis consultation — Sprint 1 API Endpoints list (16 exact endpoints)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Project CRUD via API
    Tool: Bash (curl)
    Preconditions: Backend running
    Steps:
      1. POST /api/v1/projects with {"name":"Test","domain":"https://example.com"}
      2. Assert 201 status, response has id field
      3. GET /api/v1/projects/{id}
      4. Assert 200, name == "Test"
      5. PUT /api/v1/projects/{id} with {"name":"Updated"}
      6. Assert 200, name == "Updated"
      7. DELETE /api/v1/projects/{id}
      8. Assert 200 or 204
      9. GET /api/v1/projects/{id}
      10. Assert 404
    Expected Result: Full CRUD lifecycle works via API
    Failure Indicators: Wrong status codes, validation errors, cascade failure
    Evidence: .sisyphus/evidence/s1-task-17-crud.txt

  Scenario: Crawl lifecycle via API
    Tool: Bash (curl)
    Preconditions: Project exists, worker running
    Steps:
      1. POST /api/v1/projects/{id}/crawls with start_url + config
      2. Assert 201, crawl has status "queued"
      3. Wait 5s, GET /api/v1/crawls/{crawl_id}
      4. Assert status changed to "crawling"
      5. POST /api/v1/crawls/{crawl_id}/pause
      6. Assert 200
      7. POST /api/v1/crawls/{crawl_id}/resume
      8. Assert 200
      9. Wait for completion
    Expected Result: Crawl progresses through lifecycle states
    Failure Indicators: Wrong status transitions, timeout, 500 error
    Evidence: .sisyphus/evidence/s1-task-17-lifecycle.txt

  Scenario: URLs endpoint returns paginated results
    Tool: Bash (curl)
    Preconditions: Completed crawl with data
    Steps:
      1. GET /api/v1/crawls/{id}/urls?limit=5
      2. Assert 200, items array has <= 5 entries
      3. Assert response has has_more and next_cursor fields
      4. GET /api/v1/crawls/{id}/urls?cursor={next_cursor}&limit=5
      5. Assert different URLs returned
    Expected Result: Cursor pagination works correctly
    Failure Indicators: Missing fields, duplicate results, wrong limit
    Evidence: .sisyphus/evidence/s1-task-17-pagination.txt
  ```

  **Commit**: NO (no git repo)

- [ ] 18. WebSocket Manager (Redis Pub/Sub → Client Fan-Out)

  **What to do**:
  - Create `backend/app/websocket/manager.py`:
    - Class `CrawlBroadcaster`:
      - ONE Redis subscription per `crawl_id` (not per WebSocket client)
      - Fan-out to N local `asyncio.Queue(maxsize=100)` — one per connected client
      - `subscribe(crawl_id, queue)` — register client queue
      - `unsubscribe(crawl_id, queue)` — remove client queue
      - **Backpressure**: `queue.put_nowait()` with `QueueFull` catch → drop oldest message
    - Redis listener task per crawl_id:
      - `SUBSCRIBE crawl:{crawl_id}:events`
      - Forward messages to all registered queues
      - Cancel listener when no clients remain
  - Add WebSocket endpoint to `backend/app/api/v1/crawls.py`:
    - `WS /api/v1/crawls/{id}/ws`:
      - Accept connection
      - Create queue, subscribe to broadcaster
      - Loop: dequeue message → send to client as JSON
      - On disconnect: unsubscribe, clean up
      - Heartbeat: send ping every 30s
  - **Message types** (minimum 3 for Sprint 1):
    - `progress`: `{"type":"progress","crawl_id":"...","crawled":N,"total":N,"urls_per_sec":F,"elapsed_sec":N}`
    - `state_change`: `{"type":"state_change","crawl_id":"...","old_state":"...","new_state":"..."}`
    - `crawl_complete`: `{"type":"crawl_complete","crawl_id":"...","total_urls":N,"duration_sec":N}`
  - CrawlEngine publishes to `crawl:{crawl_id}:events` channel (integrate with Task 14)

  **Must NOT do**:
  - Don't create Redis subscription per WebSocket client
  - Don't implement `page_crawled` or `issue_found` message types (Sprint 2)
  - Don't implement authentication on WebSocket

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex async patterns — Redis pub/sub, fan-out queues, connection lifecycle, backpressure
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T19, T20)
  - **Parallel Group**: Wave 5
  - **Blocks**: Tasks 25 (frontend WebSocket hook)
  - **Blocked By**: Tasks 15, 6

  **References**:

  **Pattern References**:
  - `PLAN.md:1870-1978` — WebSocket Protocol spec (architecture, message types, heartbeat, backpressure, reconnection)
  - `PLAN.md:372-373` — websocket/manager.py description
  - Metis consultation — CrawlBroadcaster fan-out pattern, cancel listener on disconnect

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: WebSocket receives progress messages during crawl
    Tool: Bash
    Preconditions: Backend + worker running, crawl started
    Steps:
      1. Start a crawl via API
      2. Connect WebSocket: python -c "import asyncio, websockets; ..."
      3. Receive at least 3 messages
      4. Assert each message has "type" field
      5. Assert at least one "progress" type message
    Expected Result: Client receives real-time progress events
    Failure Indicators: No messages, connection refused, invalid JSON
    Evidence: .sisyphus/evidence/s1-task-18-ws.txt

  Scenario: WebSocket disconnection cleans up resources
    Tool: Bash
    Preconditions: WebSocket connected
    Steps:
      1. Connect WebSocket client
      2. Disconnect abruptly
      3. Check broadcaster: assert client queue removed
      4. If no clients remain: assert Redis listener cancelled
    Expected Result: Clean resource cleanup on disconnect
    Failure Indicators: Memory leak, dangling listeners, error logs
    Evidence: .sisyphus/evidence/s1-task-18-cleanup.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 19. Crawl Control (Pause/Resume/Stop State Machine)

  **What to do**:
  - Integrate CrawlEngine state machine with external control commands:
    - CrawlEngine subscribes to Redis channel `crawl:{crawl_id}:control`
    - On `pause` command → set `self.paused = True`, update DB status to `paused`, publish `state_change` event
    - On `resume` command → set `self.paused = False`, update DB status to `crawling`, publish `state_change` event
    - On `stop` command → set `self.stopped = True`, drain in-flight requests, flush inserter, update DB status to `cancelled`, publish `state_change` + `crawl_complete` events
  - **Valid state transitions** (from PLAN.md state machine):
    - `crawling` → `paused` (pause)
    - `paused` → `crawling` (resume)
    - `crawling` → `cancelled` (stop)
    - `paused` → `cancelled` (stop while paused)
    - `crawling` → `completing` → `completed` (natural finish)
    - Any → `failed` (unrecoverable error)
  - **Invalid transitions**: reject with appropriate error (e.g., can't pause a completed crawl)
  - Update CrawlService pause/resume/stop methods to validate state before publishing command

  **Must NOT do**:
  - Don't implement checkpoint/resume (crash recovery)
  - Don't implement concurrent crawl management

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: State machine correctness is critical, async control with Redis pub/sub
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T18, T20)
  - **Parallel Group**: Wave 5
  - **Blocks**: Tasks 25, 27 (WebSocket + smoke test)
  - **Blocked By**: Tasks 14, 18

  **References**:

  **Pattern References**:
  - `PLAN.md:60-143` — State machine diagram (stateDiagram-v2) with all valid transitions
  - `PLAN.md:398-399` — "Pause / Resume / Stop controls"
  - `PLAN.md:1280` — CrawlStatus enum and CHECK constraint

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Pause and resume a running crawl
    Tool: Bash (curl)
    Preconditions: Crawl running against books.toscrape.com (max_urls=100)
    Steps:
      1. Start crawl, wait 5s (should be crawling)
      2. POST /api/v1/crawls/{id}/pause
      3. Assert 200
      4. GET /api/v1/crawls/{id} — assert status == "paused"
      5. Wait 5s — verify crawled_urls count doesn't increase
      6. POST /api/v1/crawls/{id}/resume
      7. Assert 200
      8. GET /api/v1/crawls/{id} — assert status == "crawling"
      9. Wait for completion
    Expected Result: Crawl pauses (no new URLs), resumes, completes
    Failure Indicators: Status doesn't change, URLs still being crawled while paused
    Evidence: .sisyphus/evidence/s1-task-19-pause-resume.txt

  Scenario: Stop cancels crawl gracefully
    Tool: Bash (curl)
    Preconditions: Crawl running
    Steps:
      1. Start crawl with max_urls=500
      2. Wait 5s
      3. POST /api/v1/crawls/{id}/stop
      4. Assert 200
      5. GET /api/v1/crawls/{id} — assert status == "cancelled"
      6. Verify crawled_urls in DB < 500
    Expected Result: Crawl stops mid-progress, data preserved
    Failure Indicators: Crash, data loss, status not cancelled
    Evidence: .sisyphus/evidence/s1-task-19-stop.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 20. Crawl Limits + User Agent Configuration

  **What to do**:
  - Integrate crawl limits into CrawlEngine:
    - `max_urls`: stop when crawled count reaches limit (already in Task 14, verify/refine)
    - `max_depth`: skip URLs deeper than limit (already in Task 14, verify/refine)
    - `max_threads`: set asyncio.Semaphore value (already in fetcher, verify configurable)
    - `rate_limit_rps`: convert to per-domain delay = 1/rps seconds, integrate with frontier rate limiter
  - Integrate User Agent configuration:
    - Preset UAs in crawl config schema:
      - `Googlebot Desktop`: `Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)`
      - `Googlebot Mobile`: `Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)`
      - `Bingbot`: `Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)`
      - `Chrome Desktop`: standard Chrome UA string
      - `SEO Spider`: `SEO-Spider/1.0 (+https://github.com/user/seo-spider)`
    - UA string passed to Fetcher's request headers
    - UA string used in robots.txt checking

  **Must NOT do**:
  - Don't implement per-URL-path limits (max 500 URLs for /blog/)
  - Don't implement URL length limits, query string limits
  - Don't build a custom UA editor UI

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Configuration wiring, preset data, integration with existing components
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T18, T19)
  - **Parallel Group**: Wave 5
  - **Blocks**: Task 27 (smoke test)
  - **Blocked By**: Task 14 (CrawlEngine)

  **References**:

  **Pattern References**:
  - `PLAN.md:508-521` — Feature 1.8 Crawl Limits spec (all limit types)
  - `PLAN.md:497-505` — Feature 1.7 User Agent spec (preset UAs, custom string)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Rate limiting enforces delay between requests
    Tool: Bash
    Preconditions: Crawl engine available
    Steps:
      1. Start crawl with rate_limit_rps=2 (0.5s between requests)
      2. Monitor request timestamps
      3. Assert minimum 0.5s between requests to same domain
    Expected Result: Rate limit respected
    Failure Indicators: Requests faster than limit, no delay
    Evidence: .sisyphus/evidence/s1-task-20-ratelimit.txt
  ```

  **Commit**: NO (no git repo)

- [ ] 21. Frontend Layout Shell + Routing + API Client

  **What to do**:
  - Implement `frontend/app/layout.tsx`:
    - Root layout with `ThemeProvider` (dark/light mode), `QueryClientProvider`, global fonts (Inter)
    - Toaster component for notifications
  - Implement `frontend/app/(dashboard)/layout.tsx`:
    - Dashboard shell with sidebar navigation + topbar
    - Sidebar links: Dashboard, Crawls, Settings (placeholder)
    - Topbar: app logo/name, breadcrumbs placeholder
    - Main content area with proper responsive layout
  - Implement `frontend/components/layout/Sidebar.tsx`:
    - Navigation links with active state highlighting
    - Collapsible on mobile
    - Icons via lucide-react
  - Implement `frontend/components/layout/Topbar.tsx`:
    - App name, breadcrumb, theme toggle
  - Implement `frontend/lib/api-client.ts`:
    - Typed fetch wrapper for all Sprint 1 API endpoints
    - Base URL from env `NEXT_PUBLIC_API_URL`
    - Methods: `getProjects()`, `createProject()`, `getCrawl()`, `startCrawl()`, `pauseCrawl()`, `resumeCrawl()`, `stopCrawl()`, `getCrawlUrls()`, `getHealth()`
    - Error handling: throw typed errors for 4XX/5XX
  - Implement `frontend/lib/query-client.ts`:
    - TanStack Query default config: `staleTime: 30_000`, `retry: 2`
  - Implement `frontend/stores/crawl-store.ts`:
    - Zustand store for client-side UI state: `activeTab`, `selectedUrl`, basic filter state
  - Implement `frontend/types/index.ts`:
    - TypeScript types matching Pydantic schemas: `Project`, `Crawl`, `CrawlConfig`, `CrawledUrl`, `CrawlStatus`, `PaginatedResponse<T>`

  **Must NOT do**:
  - Don't implement complex state management
  - Don't add D3.js or chart components
  - Don't implement WebSocket hooks yet (Task 25)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI layout, component composition, styling with Tailwind + shadcn
  - **Skills**: [`shadcn-ui`, `next-best-practices`]
    - `shadcn-ui`: Component integration guidance
    - `next-best-practices`: Next.js App Router patterns

  **Parallelization**:
  - **Can Run In Parallel**: NO (must complete before T22-T24)
  - **Parallel Group**: Wave 6
  - **Blocks**: Tasks 22, 23, 24
  - **Blocked By**: Tasks 4 (frontend init), T17 (API exists)

  **References**:

  **Pattern References**:
  - `PLAN.md:249-278` — App route structure
  - `PLAN.md:279-293` — Component/hook/lib/store structure
  - `PLAN.md:2483-2514` — UI Layout ASCII art (top tabs, data grid, bottom panel, right sidebar)
  - `PLAN.md:289-291` — lib/ files (api-client, query-client, utils)
  - `PLAN.md:293` — stores/crawl-store.ts description

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Dashboard layout renders with sidebar and topbar
    Tool: Playwright
    Preconditions: Frontend running on localhost:3000 (via Docker or dev)
    Steps:
      1. Navigate to http://localhost:3000
      2. Assert sidebar is visible with navigation links
      3. Assert topbar is visible with app name
      4. Assert main content area is visible
      5. Screenshot the layout
    Expected Result: Professional layout with sidebar, topbar, content area
    Failure Indicators: Missing components, broken layout, hydration errors
    Evidence: .sisyphus/evidence/s1-task-21-layout.png

  Scenario: API client can reach backend
    Tool: Bash
    Preconditions: Full stack running
    Steps:
      1. From frontend container, test API connectivity
      2. Call getHealth() from api-client
      3. Assert returns healthy status
    Expected Result: Frontend can communicate with backend API
    Failure Indicators: CORS error, network error, type mismatch
    Evidence: .sisyphus/evidence/s1-task-21-api.txt
  ```

  **Commit**: NO (no git repo)

---

- [ ] 22. Dashboard + Crawl List Pages

  **What to do**:
  - Implement `frontend/app/(dashboard)/page.tsx` (Dashboard):
    - Show recent crawls (last 5) with status badges
    - Quick stats: total projects, total crawls, active crawls
    - "New Crawl" button → navigates to /crawls/new
    - Uses TanStack Query hooks for data fetching
  - Implement `frontend/app/(dashboard)/crawls/page.tsx` (Crawl List):
    - Table of all crawls with columns: Project, Start URL, Status, URLs Crawled, Started, Duration
    - Status badges with color coding: green=completed, yellow=crawling, red=failed, gray=idle
    - Click row → navigate to /crawls/[crawlId]
    - "New Crawl" button
    - Server-side pagination via cursor
  - Implement `frontend/components/crawl/StatusBadge.tsx`:
    - Color-coded badge for each CrawlStatus value
    - Uses shadcn Badge component

  **Must NOT do**:
  - Don't implement complex filtering or search
  - Don't implement bulk actions
  - Don't use TanStack Table (use shadcn/ui Table directly)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI pages with data fetching, table rendering, navigation
  - **Skills**: [`shadcn-ui`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T23, T24)
  - **Parallel Group**: Wave 6
  - **Blocks**: Task 25
  - **Blocked By**: Task 21

  **References**:

  **Pattern References**:
  - `PLAN.md:253` — Dashboard page description
  - `PLAN.md:255` — Crawl list page description
  - `PLAN.md:1171-1177` — Feature 6.1 SEO Score Dashboard (simplified for Sprint 1)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Dashboard shows recent crawls
    Tool: Playwright
    Preconditions: At least 1 completed crawl exists
    Steps:
      1. Navigate to http://localhost/
      2. Assert redirected to dashboard
      3. Assert recent crawls section is visible
      4. Assert at least 1 crawl shown with status badge
      5. Screenshot
    Expected Result: Dashboard displays crawl data
    Failure Indicators: Empty page, loading forever, API error
    Evidence: .sisyphus/evidence/s1-task-22-dashboard.png

  Scenario: Crawl list shows all crawls with pagination
    Tool: Playwright
    Preconditions: Multiple crawls exist
    Steps:
      1. Navigate to /crawls
      2. Assert table with crawl data visible
      3. Assert each row has: project name, URL, status, crawled count
      4. Click a row → assert navigated to /crawls/{id}
    Expected Result: Crawl list is browsable and clickable
    Failure Indicators: Empty table, broken navigation
    Evidence: .sisyphus/evidence/s1-task-22-list.png
  ```

  **Commit**: NO (no git repo)

---

- [ ] 23. New Crawl Form (Spider + List Mode)

  **What to do**:
  - Implement `frontend/app/(dashboard)/crawls/new/page.tsx`:
    - **Mode toggle**: Spider Mode ↔ List Mode (using shadcn Tabs or Select)
    - **Spider Mode fields**:
      - URL input (required) with validation (must be valid URL)
      - Project selection (create new or select existing)
      - Configuration panel (collapsible):
        - Max URLs (number input, default 500)
        - Max Depth (number input, default 10)
        - Concurrent Threads (slider 1-20, default 5)
        - Rate Limit (requests/sec, default 5)
        - User Agent (select from presets)
        - Robots.txt mode (Respect / Ignore)
    - **List Mode fields**:
      - Textarea for pasting URLs (one per line)
      - File upload (.txt, .csv) — parse and populate textarea
      - Same configuration panel as Spider Mode
    - **Start Crawl button**: calls API, navigates to crawl detail page on success
    - URL auto-prepend: if user enters `example.com`, prepend `https://`
    - Form validation with error messages
    - Loading state while crawl is being created

  **Must NOT do**:
  - Don't implement sitemap URL download in List Mode
  - Don't implement saved configuration profiles
  - Don't implement custom regex include/exclude patterns UI (Sprint 2)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Form UI with validation, mode toggle, conditional fields
  - **Skills**: [`shadcn-ui`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T22, T24)
  - **Parallel Group**: Wave 6
  - **Blocks**: Tasks 25, 26
  - **Blocked By**: Task 21

  **References**:

  **Pattern References**:
  - `PLAN.md:256` — "New crawl form (URL, mode, config)"
  - `PLAN.md:394-412` — Feature 1.1 Spider Mode spec
  - `PLAN.md:416-427` — Feature 1.2 List Mode spec
  - `PLAN.md:508-521` — Feature 1.8 Crawl Limits spec (UI fields)
  - `PLAN.md:497-505` — Feature 1.7 User Agent presets

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Create spider crawl via form
    Tool: Playwright
    Preconditions: Full stack running
    Steps:
      1. Navigate to /crawls/new
      2. Enter URL: "https://books.toscrape.com"
      3. Set Max URLs: 20
      4. Click "Start Crawl"
      5. Assert navigated to /crawls/{id} (crawl detail page)
      6. Assert crawl status shows "queued" or "crawling"
    Expected Result: Crawl created and user redirected to detail page
    Failure Indicators: Validation error, API error, no redirect
    Evidence: .sisyphus/evidence/s1-task-23-spider-form.png

  Scenario: Create list mode crawl with pasted URLs
    Tool: Playwright
    Preconditions: Full stack running
    Steps:
      1. Navigate to /crawls/new
      2. Switch to List Mode
      3. Paste 3 URLs in textarea
      4. Click "Start Crawl"
      5. Assert crawl created
    Expected Result: List mode crawl starts with pasted URLs
    Failure Indicators: Mode toggle broken, textarea not working
    Evidence: .sisyphus/evidence/s1-task-23-list-form.png
  ```

  **Commit**: NO (no git repo)

---

- [ ] 24. Crawl Detail Page (Progress + Results Table)

  **What to do**:
  - Implement `frontend/app/(dashboard)/crawls/[crawlId]/page.tsx`:
    - **Header section**:
      - Crawl URL + status badge
      - Progress bar (crawled / total URLs)
      - Elapsed time + URLs/sec rate
      - Control buttons: Pause, Resume, Stop (show/hide based on status)
    - **Results table** (basic server-paginated shadcn Table):
      - Columns: URL, Status Code, Title, Meta Description, Response Time, Word Count, Crawl Depth
      - Server-side pagination with "Load More" or Previous/Next buttons
      - Basic column sorting (client-side for current page)
      - Click row → expand to show URL details (inline or bottom panel)
    - **Loading state**: skeleton while data loads
    - **Error state**: error boundary for failed requests
    - **Auto-refresh**: poll crawl status every 2s while status is `crawling` or `paused`
    - Uses TanStack Query with `refetchInterval` for live updates (WebSocket integration in Task 25)

  **Must NOT do**:
  - Don't implement TanStack Table or react-virtual
  - Don't implement tab panels (Internal, External, Titles, etc.) — Sprint 2
  - Don't implement right sidebar (Issues, Site Structure) — Sprint 2
  - Don't implement bottom detail panel (Inlinks, Outlinks) — Sprint 2

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Data-heavy page with progress visualization, table, controls
  - **Skills**: [`shadcn-ui`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T22, T23)
  - **Parallel Group**: Wave 6
  - **Blocks**: Tasks 25, 27
  - **Blocked By**: Task 21

  **References**:

  **Pattern References**:
  - `PLAN.md:258-268` — Crawl detail page + co-located components
  - `PLAN.md:2483-2514` — UI Layout (data grid, progress bar, control buttons)
  - `PLAN.md:262` — CrawlProgress.tsx component
  - `PLAN.md:263` — TabPanel.tsx (defer to Sprint 2)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Crawl detail shows progress and results
    Tool: Playwright
    Preconditions: Completed crawl with data
    Steps:
      1. Navigate to /crawls/{crawlId}
      2. Assert progress bar shows 100% for completed crawl
      3. Assert results table is visible with URLs
      4. Assert each row has: URL, status code, title
      5. Assert pagination controls work
      6. Screenshot
    Expected Result: Crawl results displayed in paginated table
    Failure Indicators: Empty table, no progress bar, broken pagination
    Evidence: .sisyphus/evidence/s1-task-24-detail.png

  Scenario: Control buttons respond to crawl status
    Tool: Playwright
    Preconditions: Crawl in different states
    Steps:
      1. For completed crawl: assert no Pause/Resume/Stop buttons
      2. For crawling crawl: assert Pause and Stop visible
      3. For paused crawl: assert Resume and Stop visible
    Expected Result: Correct buttons shown for each state
    Failure Indicators: Wrong buttons, buttons for invalid transitions
    Evidence: .sisyphus/evidence/s1-task-24-controls.png
  ```

  **Commit**: NO (no git repo)

- [ ] 25. WebSocket Integration in Frontend (Real-Time Progress)

  **What to do**:
  - Create `frontend/hooks/use-crawl-websocket.ts`:
    - Custom hook: `useCrawlWebSocket(crawlId: string)`
    - Connects to `ws://localhost/api/v1/crawls/{crawlId}/ws`
    - Exponential backoff reconnect on disconnect (1s, 2s, 4s, 8s, max 30s)
    - Parses incoming JSON messages
    - Returns: `{ isConnected, lastMessage, progress, status }`
    - On `progress` message: update Zustand store + invalidate TanStack Query cache
    - On `state_change` message: update crawl status in store
    - On `crawl_complete` message: invalidate all crawl queries, show toast notification
    - Cleanup: close WebSocket on component unmount
  - Update `frontend/app/(dashboard)/crawls/[crawlId]/page.tsx`:
    - Replace polling (`refetchInterval`) with WebSocket for real-time progress
    - Progress bar updates live via WebSocket progress messages
    - Status badge updates via WebSocket state_change messages
    - Keep TanStack Query for initial data load + on-demand refetch
  - Update `frontend/app/(dashboard)/crawls/[crawlId]/_components/CrawlProgress.tsx`:
    - Component showing: progress bar, URLs crawled/remaining, URLs/sec, elapsed time
    - Animated progress bar that updates smoothly
    - Status text below progress bar

  **Must NOT do**:
  - Don't implement SSE (Server-Sent Events) as alternative
  - Don't implement complex reconnection state machine

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: WebSocket integration with React hooks, state management, UI updates
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T26)
  - **Parallel Group**: Wave 7
  - **Blocks**: Task 27
  - **Blocked By**: Tasks 18, 22, 24

  **References**:

  **Pattern References**:
  - `PLAN.md:285-286` — use-crawl-websocket.ts hook description
  - `PLAN.md:1870-1978` — WebSocket protocol (message format, reconnection strategy)
  - `PLAN.md:264` — CrawlProgress.tsx component description

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Progress bar updates in real-time during crawl
    Tool: Playwright
    Preconditions: Full stack running
    Steps:
      1. Navigate to /crawls/new
      2. Start a crawl (max_urls=50)
      3. Observe crawl detail page
      4. Assert progress bar increases over 10 seconds
      5. Assert URLs crawled count increases
      6. Assert URLs/sec metric is shown
      7. Wait for completion
      8. Assert progress bar shows 100% and status=completed
      9. Screenshot during crawl + after completion
    Expected Result: Live progress updates without page refresh
    Failure Indicators: Static progress bar, no WebSocket connection, stale data
    Evidence: .sisyphus/evidence/s1-task-25-live-progress.png
  ```

  **Commit**: NO (no git repo)

---

- [ ] 26. List Mode Implementation

  **What to do**:
  - Implement List Mode crawl in backend:
    - When `mode=list` in CrawlCreate:
      - Accept `urls` field (list of strings) instead of `start_url`
      - CrawlEngine adds all URLs to frontier at depth=0
      - Default: `max_depth=0` (don't follow links from listed URLs)
      - Optional: user can set `max_depth > 0` to also crawl outlinks
    - Same crawler pipeline: fetch → parse → insert
    - Same WebSocket progress updates
  - Update CrawlCreate Pydantic schema: `urls: list[str] | None` for list mode
  - Update new crawl API endpoint to handle both modes
  - Frontend already has List Mode form from Task 23 — verify integration works end-to-end
  - **URL parsing from textarea**: split by newline, strip whitespace, filter empty lines, validate URLs, auto-prepend https:// if missing

  **Must NOT do**:
  - Don't implement XML Sitemap URL download
  - Don't implement file upload (beyond basic textarea paste)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Backend logic extension with API integration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T25)
  - **Parallel Group**: Wave 7
  - **Blocks**: Task 27
  - **Blocked By**: Tasks 17, 23

  **References**:

  **Pattern References**:
  - `PLAN.md:416-427` — Feature 1.2 List Mode full spec
  - `PLAN.md:256` — new crawl form page

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: List mode crawls only specified URLs
    Tool: Bash (curl)
    Preconditions: Full stack running
    Steps:
      1. Start crawl with mode=list, urls=["https://books.toscrape.com/", "https://books.toscrape.com/catalogue/page-2.html"]
      2. Wait for completion
      3. Query crawled_urls: SELECT COUNT(*) WHERE crawl_id=...
      4. Assert count == 2 (only the listed URLs)
      5. Assert no additional discovered URLs were crawled
    Expected Result: Only listed URLs crawled at depth 0
    Failure Indicators: More than 2 URLs, link discovery enabled
    Evidence: .sisyphus/evidence/s1-task-26-listmode.txt

  Scenario: List mode via frontend
    Tool: Playwright
    Preconditions: Full stack running
    Steps:
      1. Navigate to /crawls/new, switch to List Mode
      2. Paste 3 URLs in textarea
      3. Click Start Crawl
      4. Wait for completion on detail page
      5. Assert 3 URLs in results table
    Expected Result: End-to-end List Mode works via UI
    Failure Indicators: Form error, wrong URL count
    Evidence: .sisyphus/evidence/s1-task-26-listmode-ui.png
  ```

  **Commit**: NO (no git repo)

---

- [ ] 27. End-to-End Smoke Test (books.toscrape.com)

  **What to do**:
  - **Full integration test** that verifies the entire Sprint 1 stack works together:
  - Start from clean state: `docker compose down -v && docker compose up -d`
  - Wait for all services healthy
  - Execute ALL acceptance criteria from the plan (AC-1 through AC-13):
    1. Docker Compose starts all services → verify `docker compose ps`
    2. Alembic migrations run → verify tables created
    3. Health check passes → `curl /api/v1/health`
    4. Create project → `POST /api/v1/projects`
    5. Start spider crawl → `POST /api/v1/projects/{id}/crawls` with max_urls=50, max_depth=2
    6. Connect WebSocket → verify progress messages received
    7. Wait for completion → poll status until `completed`
    8. Verify crawled_urls count > 0 and ≤ 50
    9. Verify URLs have populated fields (status_code, title, etc.)
    10. Verify robots.txt was respected
    11. Test pause/resume on a separate crawl
    12. Test stop on a separate crawl
    13. Test List Mode with 3 specific URLs
    14. Verify frontend loads and shows results
  - **Capture evidence** for every step
  - **Report**: generate summary file with PASS/FAIL for each check

  **Must NOT do**:
  - Don't test Sprint 2+ features (SEO analysis, issues, etc.)
  - Don't test against external sites other than books.toscrape.com

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex multi-step verification across entire stack, requires patience and thoroughness
  - **Skills**: [`playwright`]
    - `playwright`: For browser-based UI verification

  **Parallelization**:
  - **Can Run In Parallel**: NO (final integration test)
  - **Parallel Group**: Wave 7 (after T25, T26 complete)
  - **Blocks**: Final Verification Wave (F1-F4)
  - **Blocked By**: Tasks 19, 20, 25, 26 (all features must be complete)

  **References**:

  **Pattern References**:
  - All acceptance criteria defined in this plan's "Success Criteria" section
  - Metis consultation AC-1 through AC-13

  **External References**:
  - Test target: `https://books.toscrape.com` — purpose-built scraping sandbox

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Complete end-to-end crawl pipeline
    Tool: Bash + Playwright
    Preconditions: Clean Docker state
    Steps:
      1. docker compose down -v && docker compose up -d
      2. Wait for all services healthy (30s timeout)
      3. Run Alembic migrations
      4. Create project via API
      5. Start spider crawl (books.toscrape.com, max_urls=50, max_depth=2)
      6. Connect WebSocket, capture progress messages
      7. Wait for crawl completion (120s timeout)
      8. Assert crawl status == completed
      9. Assert 10 < crawled_urls count <= 50
      10. Assert URLs have title, status_code, meta_description populated
      11. Open frontend, navigate to crawl detail
      12. Assert results table shows crawled URLs
      13. Screenshot final state
    Expected Result: Full pipeline works from Docker start to UI results
    Failure Indicators: Any step fails
    Evidence: .sisyphus/evidence/s1-task-27-e2e-report.txt + .sisyphus/evidence/s1-task-27-e2e-final.png

  Scenario: List Mode end-to-end
    Tool: Bash
    Preconditions: Stack running from previous scenario
    Steps:
      1. Start list mode crawl with 3 URLs
      2. Wait for completion
      3. Assert exactly 3 URLs crawled
    Expected Result: List mode works end-to-end
    Evidence: .sisyphus/evidence/s1-task-27-listmode-e2e.txt

  Scenario: Pause/Resume/Stop end-to-end
    Tool: Bash
    Preconditions: Stack running
    Steps:
      1. Start crawl with max_urls=200
      2. Wait 5s, POST /pause
      3. Assert status=paused, count frozen
      4. POST /resume
      5. Assert status=crawling, count increasing
      6. POST /stop
      7. Assert status=cancelled
    Expected Result: All control commands work
    Evidence: .sisyphus/evidence/s1-task-27-controls-e2e.txt
  ```

  **Commit**: NO (no git repo)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `deep`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run linter + type checks. Review all changed files for: `as any`/`@ts-ignore` (frontend), bare `except:` (backend), `print()` in prod code, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp). Verify Router→Service→Repository pattern followed in backend.
  Output: `Lint [PASS/FAIL] | Types [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real QA** — `unspecified-high` (+ `playwright` skill for UI)
  Start from clean state (`docker compose down -v && docker compose up -d`). Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration. Test edge cases: empty crawl target, unreachable URL, very large page. Save to `.sisyphus/evidence/s1-final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", compare against actual files created. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT Have" compliance (no SEO analyzers, no TanStack Table, no auth, etc.). Flag unaccounted files.
  Output: `Tasks [N/N compliant] | Creep [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

> No git repo exists in this project. No commit operations.
> Files are tracked by Docker volumes and local filesystem only.

---

## Success Criteria

### Verification Commands
```bash
# Infrastructure
docker compose up -d                          # Expected: all services healthy
docker compose ps                             # Expected: 7 services Up
curl -s http://localhost/api/v1/health         # Expected: {"status":"healthy","services":{"database":"ok","redis":"ok"}}

# Database
docker compose exec db psql -U postgres -d seo_spider -c "\dt" | grep -c "projects\|crawls\|crawled_urls\|page_links\|url_issues\|redirects"
# Expected: 6

# End-to-end crawl
PROJECT_ID=$(curl -s -X POST http://localhost/api/v1/projects -H "Content-Type: application/json" -d '{"name":"Test","domain":"https://books.toscrape.com"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
CRAWL_ID=$(curl -s -X POST "http://localhost/api/v1/projects/${PROJECT_ID}/crawls" -H "Content-Type: application/json" -d '{"start_url":"https://books.toscrape.com","mode":"spider","config":{"max_urls":50,"max_depth":2,"threads":3}}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
# Wait ~60s for crawl to complete
curl -s "http://localhost/api/v1/crawls/${CRAWL_ID}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='completed', f'status={d[\"status\"]}'"
# Expected: status=completed

# Verify data
docker compose exec db psql -U postgres -d seo_spider -c "SELECT COUNT(*) FROM crawled_urls WHERE crawl_id='${CRAWL_ID}'"
# Expected: count > 0 and count <= 50

# Frontend accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Expected: 200
```

### Final Checklist
- [ ] All "Must Have" items present and working
- [ ] All "Must NOT Have" items absent from codebase
- [ ] Docker Compose starts cleanly from scratch
- [ ] End-to-end crawl completes successfully
- [ ] WebSocket delivers real-time progress
- [ ] Frontend shows crawl results
- [ ] Robots.txt respected
- [ ] Crawl limits enforced
- [ ] Pause/Resume/Stop work
- [ ] List Mode works
