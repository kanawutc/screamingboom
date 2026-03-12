"""Shared FastAPI dependencies."""

from typing import Annotated, AsyncIterator

import asyncpg
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db, get_asyncpg_pool as _get_asyncpg_pool

# Module-level Redis client — created once in lifespan, reused across requests
_redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize and return the Redis client. Called during lifespan startup."""
    global _redis_client
    _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis client. Called during lifespan shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def get_redis() -> AsyncIterator[Redis]:
    """FastAPI dependency: yield the shared Redis client."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    yield _redis_client


async def get_asyncpg_pool_dep() -> asyncpg.Pool:
    """FastAPI dependency: return the raw asyncpg pool."""
    return _get_asyncpg_pool()


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
AsyncpgPool = Annotated[asyncpg.Pool, Depends(get_asyncpg_pool_dep)]
