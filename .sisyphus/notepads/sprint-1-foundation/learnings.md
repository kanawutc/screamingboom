# Sprint 1 Foundation — Learnings

## [2026-03-11T11:27:19Z] Session: ses_323f72f60ffe3BrBLGS3ovV1XZ
### Plan initialized. No code written yet. Starting from scratch.
## [2026-03-11] T1: Library Compatibility Verification — COMPLETE

### Bloom Filter Result
- **PYBLOOM OK**: pybloom-live 3.0.0+ works perfectly on Python 3.12
- No C extension issues despite 2021 last release
- ScalableBloomFilter instantiation and add/membership tests pass

### Core Dependencies Status
- **selectolax**: OK (requires libxml2-dev, libxslt1-dev on slim image)
- **lxml**: OK (requires libxml2-dev, libxslt1-dev on slim image)
- **aiohttp**: OK
- **asyncpg**: OK
- **arq**: OK
- **pydantic[email]**: OK
- **pydantic-settings**: OK
- **fastapi**: OK
- **uvicorn[standard]**: OK
- **gunicorn**: OK
- **alembic**: OK
- **sqlalchemy[asyncio]**: OK
- **psycopg2-binary**: OK
- **structlog**: OK
- **httptools**: OK
- **uvloop**: OK

### uv Status
- **uv 0.10.9**: Installed and working on Python 3.12

### Key Learnings
1. python:3.12-slim requires build tools (gcc, libxml2-dev, libxslt1-dev) for lxml/selectolax
2. pybloom-live is safe to use despite age — no compatibility issues with Python 3.12
3. All 18 core dependencies verified in single Docker run
4. No fallback to set() needed — pybloom-live is production-ready

### Evidence Files
- `s1-task-1-deps-verify.txt`: Full install + import test output
- `s1-task-1-bloom-verify.txt`: pybloom-live test result (PYBLOOM OK)
- `s1-task-1-uv-verify.txt`: uv version output (0.10.9)

## [2026-03-11] T2: Docker Compose + Nginx + Environment Configuration — COMPLETE

### 7 Services Architecture
- **frontend**: Next.js 3000 (depends_on backend healthy)
- **backend**: FastAPI 8000 (depends_on migrate completed + redis healthy)
- **worker**: ARQ background jobs (depends_on migrate completed + redis healthy)
- **migrate**: Alembic migrations (depends_on db healthy, exits with success)
- **db**: PostgreSQL 16-alpine (healthcheck pg_isready)
- **redis**: Redis 7-alpine (healthcheck redis-cli ping)
- **nginx**: Nginx alpine reverse proxy (port 80)

### Critical Configuration Details
1. **migrate service**: NEW addition not in PLAN.md
   - Runs `alembic upgrade head` and exits
   - backend/worker use `service_completed_successfully` condition
   - Ensures migrations run before app startup
   
2. **Worker replicas**: MUST be 1 (Sprint 1 guardrail)
   - PLAN.md had 2, but task spec overrides to 1
   - deploy.replicas: 1 in docker-compose.yml

3. **ARQ worker command**: `python -m arq app.worker.settings.WorkerSettings`
   - NOT `workers/main.py` (incorrect path in PLAN.md)
   - Actual module path: `app/worker/settings.py`

4. **Nginx WebSocket support**:
   - `proxy_read_timeout 3600s` (CRITICAL for crawl progress streams)
   - Default 60s kills long-running WebSocket connections
   - `map $http_upgrade $connection_upgrade` for upgrade header
   - Location: `~ ^/api/v1/crawls/[^/]+/ws$`

5. **macOS Docker hot reload**:
   - Frontend: `WATCHPACK_POLLING=true` (Next.js file watcher)
   - Backend: `WATCHFILES_FORCE_POLLING=true` (uvicorn reload)
   - Worker: `WATCHFILES_FORCE_POLLING=true` (arq watch)
   - Fixes VirtioFS polling issues on Docker Desktop

6. **Database initialization**:
   - init.sql mounted to `/docker-entrypoint-initdb.d/init.sql`
   - Runs only on fresh DB init (not on restart)
   - Will be created in Task 5

7. **Frontend Dockerfile**:
   - Multi-stage: deps → builder → runner
   - Runner stage uses `output: 'standalone'` (configured in Task 4)
   - Copies `.next/standalone` and `.next/static`

8. **Backend Dockerfile**:
   - Python 3.12-slim base
   - System deps: gcc, libxml2-dev, libxslt1-dev, curl
   - uv for fast dependency installation
   - Non-root user: appuser
   - Production: gunicorn + uvicorn workers (4 workers)

### Environment Variables
- DATABASE_URL: `postgresql+asyncpg://postgres:changeme@db:5432/seo_spider`
- REDIS_URL: `redis://redis:6379`
- NEXT_PUBLIC_API_URL: `http://localhost/api` (browser)
- API_URL: `http://backend:8000` (server-side)
- OPENAI_API_KEY: Optional (Sprint 4+)

### Nginx Routing
- `/api/v1/crawls/[id]/ws` → backend (3600s timeout, WebSocket upgrade)
- `/api/` → backend (60s timeout, standard proxy)
- `/` → frontend (catch-all, Next.js)

### QA Results
✅ docker compose config --quiet: PASS (version attribute warning is expected)
✅ docker compose -f docker-compose.yml -f docker-compose.dev.yml config: PASS
✅ All 6 files exist: docker-compose.yml, docker-compose.dev.yml, nginx.conf, .env.example, backend/Dockerfile, frontend/Dockerfile
✅ 7 services in docker-compose.yml (10 grep matches = 7 services + 3 other matches)
✅ WebSocket timeout 3600s present
✅ WebSocket upgrade map present
✅ WATCHPACK_POLLING in dev override
✅ WATCHFILES_FORCE_POLLING in dev override (2 occurrences)
✅ Worker replicas: 1
✅ migrate service found (3 grep matches)

### Evidence Files
- `s1-task-2-compose-valid.txt`: docker compose config validation
- `s1-task-2-files-check.txt`: file existence + critical directives
- `s1-task-2-nginx-routes.txt`: nginx routing rules verification

## [2026-03-11] T5: PostgreSQL Schema + Alembic — COMPLETE
- 6 tables: projects, crawls, crawled_urls (4 partitions), page_links, url_issues (4 partitions), redirects
- crawled_urls and url_issues use UUID gen_random_uuid() (NOT BIGSERIAL — avoids sequence contention)
- 4 HASH partitions each (Sprint 1 simplicity)
- Alembic uses psycopg2 sync driver (DATABASE_URL asyncpg→psycopg2 swap in env.py)
- TSVECTOR trigger on crawled_urls for full-text search
- Partitioned table DDL must use op.execute() — Alembic autogenerate doesn't work with partitions

## [2026-03-11] T6: Backend Config, DB Session, Redis Client, Health Endpoint — COMPLETE

### Architecture Decisions
- **asyncpg raw pool**: Added alongside SQLAlchemy engine for future COPY/bulk operations (min_size=5, max_size=20)
- **Shared Redis client**: Module-level singleton in deps.py, initialized during lifespan startup, shared across all requests
- **Health endpoint**: `/api/v1/health` checks DB (SELECT 1) + Redis (PING), returns status/version/services

### Key Changes
- `session.py`: Added `create_db_engine()` that creates both SQLAlchemy engine AND raw asyncpg pool
- `deps.py`: Added `init_redis()`/`close_redis()` lifecycle, type aliases `DbSession`, `RedisClient`, `AsyncpgPool`
- `main.py`: Lifespan now initializes DB engine + Redis, shuts down both
- `router.py`: Health endpoint with proper error handling per service

### Port Mapping Note
- Backend port 8000 is NOT exposed to host — only via nginx or Docker networking
- Test with: `docker compose exec backend curl -s http://localhost:8000/api/v1/health`

### Evidence
- `s1-task-6-health.txt`: Health endpoint returns `{"status":"healthy","version":"0.1.0","services":{"database":"ok","redis":"ok"}}`
