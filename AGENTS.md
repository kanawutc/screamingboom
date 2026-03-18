# AGENTS.md

## Overview

SEO Spider is a self-hosted SEO crawling/analysis tool (Screaming Frog clone). The backend is Python 3.12 (FastAPI + arq worker), backed by PostgreSQL 16 and Redis 7. The frontend is Next.js 16 (React 19, TypeScript, Tailwind 4, shadcn/ui).

**Current status**: Phase 1 (Core Crawl Engine) complete. Phase 2 (SEO Analysis & Audit) in progress. Backend is fully functional with 30+ API endpoints, crawl engine, and 9 SEO analysis rule modules. Frontend is scaffolded with 6 pages, layout, API client, WebSocket hook, and Zustand store.

## Architecture

```
Browser (:80) → Nginx → Next.js 16 (:3000) → FastAPI (:8000) → PostgreSQL 16 + Redis 7
                                                    ↕
                                               arq Worker
```

## Services

| Service | Command | Port |
|---------|---------|------|
| Backend API | `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | 8000 |
| Worker | `cd backend && source .venv/bin/activate && python3 -m arq app.worker.settings.WorkerSettings` | — |
| Frontend | `cd frontend && npm run dev` | 3000 |
| PostgreSQL | Already running (Homebrew service) | 5432 |
| Redis | Already running (Homebrew service) | 6379 |

## Local development setup notes

- **Python venv**: Backend uses `backend/.venv/` (Python 3.12). Always activate before running backend commands: `source backend/.venv/bin/activate`.
- The backend reads `DATABASE_URL` and `REDIS_URL` from `backend/.env` (loaded via pydantic-settings). For local dev, these should point to `localhost` not `db`/`redis` (the Docker service names).
- Alembic reads `DATABASE_URL` from the environment and swaps `+asyncpg` to `+psycopg2` automatically in `env.py`. Run migrations from `backend/`: `DATABASE_URL=postgresql+asyncpg://postgres:changeme@localhost:5432/seo_spider alembic upgrade head`.
- PostgreSQL requires the `uuid-ossp` and `pg_trgm` extensions on the `seo_spider` database.
- Frontend uses Node.js 22 / npm 10. Run `cd frontend && npm install` then `npm run dev`.

## Lint / Test / Build

- **Lint**: `cd backend && source .venv/bin/activate && ruff check .` and `mypy .` (pre-existing errors exist in the repo)
- **Test (pytest)**: `cd backend && source .venv/bin/activate && python3 -m pytest tests/ -v` — only `conftest.py` with fixtures; no test modules yet
- **Integration tests**: Root-level `test_*.py` files (14 files) are standalone scripts that hit the running API at `http://localhost` (port 80 via nginx) — they need the full Docker Compose stack or port adjustments for local dev
- **API docs**: http://localhost:8000/api/docs (Swagger UI)
- **Health check**: `curl http://localhost:8000/api/v1/health`

## Project structure

```
├── backend/                           # Python 3.12, FastAPI
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory + lifespan
│   │   ├── core/                      # Config (pydantic-settings), logging (structlog), exceptions
│   │   ├── api/v1/                    # REST endpoints: projects, crawls, urls, issues, comparison, extraction_rules
│   │   ├── api/deps.py                # Dependency injection (DB session, Redis)
│   │   ├── crawler/                   # BFS crawl pipeline: engine, frontier, fetcher, parser, inserter, robots, utils
│   │   ├── analysis/                  # SEO analysis: analyzer, post_crawl, pixel_width, issue_registry
│   │   ├── analysis/rules/            # 9 rule modules: titles, meta_descriptions, headings, images, canonicals, directives, security, url_quality, pagination
│   │   ├── models/                    # SQLAlchemy ORM: Project, Crawl, CrawledUrl, PageLink, UrlIssue, Redirect, ExtractionRule
│   │   ├── schemas/                   # Pydantic v2 schemas: project, crawl, url, issue, comparison, pagination, extraction_rule
│   │   ├── repositories/             # DB access: base, project, crawl, url, issue repos
│   │   ├── services/                  # Business logic: crawl_service, project_service
│   │   ├── websocket/manager.py       # Redis pub/sub → WebSocket fan-out
│   │   ├── worker/                    # arq worker settings + crawl_tasks
│   │   └── db/                        # Session management + 3 Alembic migrations
│   ├── tests/conftest.py              # pytest fixtures
│   ├── .venv/                         # Python virtual environment
│   ├── pyproject.toml                 # Dependencies + tool config
│   └── Dockerfile
├── frontend/                          # Next.js 16, React 19, TypeScript
│   ├── app/(dashboard)/               # 6 pages: dashboard, crawls list, crawl detail, new crawl, compare, settings
│   ├── components/layout/             # Sidebar, Topbar
│   ├── components/ui/                 # 13 shadcn/ui components
│   ├── components/crawl/              # StatusBadge
│   ├── lib/api-client.ts              # Typed API client for all backend endpoints
│   ├── hooks/use-crawl-websocket.ts   # WebSocket with auto-reconnect + backoff
│   ├── stores/crawl-store.ts          # Zustand store for active crawl state
│   ├── types/index.ts                 # TypeScript type definitions
│   └── Dockerfile
├── nginx/nginx.conf                   # Reverse proxy, WS upgrade, gzip
├── docker-compose.yml                 # Production (7 services)
├── docker-compose.dev.yml             # Dev overrides
├── test_*.py                          # 14 integration/E2E test files
├── PLAN.md                            # Full roadmap (57 features, 6 phases)
└── AGENTS.md                          # This file
```

## Subdirectory AGENTS.md files

Each major directory has its own AGENTS.md with domain-specific guidance:

| File | Focus |
|------|-------|
| `backend/AGENTS.md` | Coding conventions, layer architecture (Router→Service→Repo), testing, common gotchas |
| `backend/app/api/AGENTS.md` | Endpoint patterns, DI, pagination, error handling, WebSocket |
| `backend/app/crawler/AGENTS.md` | Pipeline flow, component classes, Redis keys, error recovery, design decisions |
| `backend/app/analysis/AGENTS.md` | Two-phase analysis, 9 rule modules, issue registry, how to add new rules |
| `frontend/AGENTS.md` | Page implementation status, component inventory, API client usage, what's not built yet |

## Database schema (3 migrations)

| Table | Key Features |
|-------|-------------|
| projects | UUID PK, name, domain, settings (JSONB) |
| crawls | UUID PK, FK→projects, status enum (9 states), mode (spider/list), config (JSONB) |
| crawled_urls | Hash-partitioned ×4, full-text search (tsvector+GIN), trigram index, seo_data (JSONB) |
| page_links | Source→target, link_type, anchor_text |
| url_issues | Hash-partitioned ×4, severity, category, details (JSONB) |
| redirects | Chain tracking with hop_number |
| extraction_rules | Project-scoped CSS/XPath selectors |
