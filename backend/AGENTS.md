# Backend — AGENTS.md

## Stack
Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, arq (Redis worker), asyncpg, aiohttp, selectolax, structlog.

## Architecture (Router → Service → Repository)
- **Routers** (`api/v1/`): Async handlers with `Annotated` DI, explicit status codes, response_model on decorator. Create service instance in handler: `svc = ProjectService(db)`.
- **Services** (`services/`): Business logic orchestrators. Take `AsyncSession` + `Redis` in constructor. Store deps as `self._repo`, `self._session`, `self._redis`. Return `bool` for success/failure, raise `ValueError` for invalid state. Always `await self._session.commit()` then `await self._session.refresh()` after mutations.
- **Repositories** (`repositories/`): Extend `BaseRepository[T]`. Wrap base methods with domain names. All methods `async def` with full return types.
- **Models** (`models/`): SQLAlchemy 2.0 with `Mapped[Type]` + `mapped_column()`. Use `UUIDPrimaryKeyMixin`. Relationships via `back_populates`. JSONB for flexible data.
- **Schemas** (`schemas/`): Pydantic v2. `ConfigDict(from_attributes=True)`. `StrEnum` for enums. `@model_validator(mode="after")` for cross-field validation. `Field(default_factory=list)` for mutable defaults.

## Coding Conventions
- **Type hints**: Always. Use `str | None` not `Optional[str]`. Full return types on all functions.
- **Async**: All I/O is async. No blocking calls ever.
- **Naming**: snake_case functions/vars, PascalCase classes, `_private` prefix for internals.
- **Logging**: `structlog.get_logger(__name__)` at module level. Structured fields: `logger.info("message", crawl_id=str(id))`.
- **Error handling**: `HTTPException` in routers, `ValueError` in services, `RuntimeError` for init failures.
- **DI pattern**: `Annotated[AsyncSession, Depends(get_db)]` aliased as `DbSession` in deps.py.
- **Line length**: 100 chars (ruff).
- **Imports**: ruff sorts them (isort rules).

## Database
- PostgreSQL 16 with extensions: `uuid-ossp`, `pg_trgm`.
- Hash-partitioned tables: `crawled_urls` (×4), `url_issues` (×4).
- Alembic migrations in `app/db/migrations/versions/`. Run from backend/: `alembic upgrade head`.
- Connection: `DATABASE_URL` from `.env` (pydantic-settings). Async via `asyncpg`.

## Testing
- **Unit tests**: `tests/` with pytest-asyncio (`asyncio_mode = "auto"`).
- **Fixtures**: `conftest.py` has async DB session and Redis client fixtures.
- **Integration tests**: Root-level `test_*.py` files hit live API (need running services).
- **Lint**: `ruff check .` (rules: E, F, I, N, W, UP). `mypy .` (strict mode, Python 3.12).

## Key Files
| File | Purpose |
|------|---------|
| `app/main.py` | App factory + lifespan (startup/shutdown) |
| `app/core/config.py` | `Settings(BaseSettings)` singleton |
| `app/core/exceptions.py` | Exception handlers → JSONResponse |
| `app/api/deps.py` | DI: `get_db`, `get_redis`, type aliases |
| `app/api/v1/router.py` | Aggregates all v1 routers |

## Common Gotchas
- Always activate venv: `source .venv/bin/activate` before any command.
- `.env` uses `localhost` not Docker service names (`db`/`redis`) for local dev.
- Pre-existing mypy/type errors exist — don't fix unless asked.
- `crawled_urls` and `url_issues` are hash-partitioned — queries must include `crawl_id`.
