"""Database session management with asyncpg and SQLAlchemy."""

from typing import AsyncIterator
from urllib.parse import urlparse

import asyncpg
import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_asyncpg_pool: asyncpg.Pool | None = None


def _get_dsn() -> str:
    """Convert SQLAlchemy URL to plain DSN for asyncpg."""
    url = settings.database_url
    # Strip the +asyncpg driver suffix for raw asyncpg
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def create_db_engine() -> None:
    """Initialize the database engine, session factory, and raw asyncpg pool."""
    global _engine, _session_factory, _asyncpg_pool

    _engine = create_async_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        echo=False,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("Database engine created", url=settings.database_url.split("@")[-1])

    # Raw asyncpg pool for COPY / bulk operations
    _asyncpg_pool = await asyncpg.create_pool(
        _get_dsn(),
        min_size=5,
        max_size=20,
    )
    logger.info("asyncpg connection pool created")


async def dispose_db_engine() -> None:
    """Dispose the database engine and close all connections."""
    global _engine, _asyncpg_pool
    if _asyncpg_pool is not None:
        await _asyncpg_pool.close()
        _asyncpg_pool = None
        logger.info("asyncpg pool closed")
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")


def get_engine() -> AsyncEngine:
    """Return the SQLAlchemy async engine."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized.")
    return _session_factory


def get_asyncpg_pool() -> asyncpg.Pool:
    """Return the raw asyncpg connection pool for bulk operations."""
    if _asyncpg_pool is None:
        raise RuntimeError("asyncpg pool not initialized.")
    return _asyncpg_pool


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
