# AGENTS.md

## Cursor Cloud specific instructions

### Overview

SEO Spider is a self-hosted SEO crawling/analysis tool. The backend is Python 3.12 (FastAPI + arq worker), backed by PostgreSQL 16 and Redis 7. The `frontend/` directory is currently empty (not yet scaffolded).

### Services

| Service | Command | Port |
|---------|---------|------|
| Backend API | `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | 8000 |
| Worker | `cd backend && python3 -m arq app.worker.settings.WorkerSettings` | — |
| PostgreSQL | `sudo pg_ctlcluster 16 main start` | 5432 |
| Redis | `sudo redis-server --daemonize yes` | 6379 |

### Local development setup notes

- The backend reads `DATABASE_URL` and `REDIS_URL` from `backend/.env` (loaded via pydantic-settings). For local dev, these should point to `localhost` not `db`/`redis` (the Docker service names).
- Alembic reads `DATABASE_URL` from the environment and swaps `+asyncpg` to `+psycopg2` automatically in `env.py`. Run migrations from `backend/`: `DATABASE_URL=postgresql+asyncpg://postgres:changeme@localhost:5432/seo_spider alembic upgrade head`.
- PostgreSQL requires the `uuid-ossp` and `pg_trgm` extensions on the `seo_spider` database.
- The `~/.local/bin` directory must be on `PATH` for pip-installed CLI tools (`uvicorn`, `ruff`, `mypy`, `pytest`, `alembic`, `arq`).

### Lint / Test / Build

- **Lint**: `cd backend && ruff check .` and `cd backend && mypy .` (pre-existing errors exist in the repo)
- **Test (pytest)**: `cd backend && python3 -m pytest tests/ -v` — only `conftest.py` with fixtures; no test modules yet
- **Integration tests**: Root-level `test_*.py` files are standalone scripts that hit the running API at `http://localhost` (port 80 via nginx) — they need the full Docker Compose stack or port adjustments for local dev
- **API docs**: http://localhost:8000/api/docs (Swagger UI)
- **Health check**: `curl http://localhost:8000/api/v1/health`
