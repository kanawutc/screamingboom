"""ARQ worker settings.

CRITICAL CONFIGURATION (from Metis research):
- job_timeout=None: No timeout — crawls run indefinitely (24/7 operation).
- max_tries=1: Crawls are NOT idempotent — retrying corrupts data.
- health_check_interval=30: Detect dead workers within ~1 minute.
- max_jobs=1: One crawl at a time per worker process.
"""

from __future__ import annotations

import asyncpg
import structlog
from arq import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.core.config import settings
from app.worker.tasks.crawl_tasks import start_crawl_job
from app.worker.tasks.schedule_tasks import check_schedules_job

logger = structlog.get_logger(__name__)


def _parse_redis_settings() -> RedisSettings:
    """Parse REDIS_URL into ARQ RedisSettings."""
    url = settings.redis_url  # e.g. redis://redis:6379
    # Strip scheme
    stripped = url.replace("redis://", "")
    host_port = stripped.split("/")[0]
    parts = host_port.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 6379
    # Database number
    db = 0
    if "/" in stripped:
        db_str = stripped.split("/")[1]
        if db_str:
            db = int(db_str)
    return RedisSettings(host=host, port=port, database=db)


async def startup(ctx: dict) -> None:
    """ARQ worker startup: initialize DB pool and Redis client."""
    logger.info("arq_worker_starting")

    # Create asyncpg pool for direct DB access in crawl jobs
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    ctx["asyncpg_pool"] = await asyncpg.create_pool(dsn, min_size=5, max_size=20)

    # Create Redis client for pub/sub and frontier operations
    # Note: ARQ provides ctx["redis"] but it's used internally by ARQ.
    # We create our own for crawl operations to avoid conflicts.
    ctx["redis_client"] = Redis.from_url(settings.redis_url, decode_responses=False)

    logger.info("arq_worker_ready")


async def shutdown(ctx: dict) -> None:
    """ARQ worker shutdown: clean up connections."""
    logger.info("arq_worker_shutting_down")

    pool = ctx.get("asyncpg_pool")
    if pool:
        await pool.close()

    redis_client = ctx.get("redis_client")
    if redis_client:
        await redis_client.aclose()

    logger.info("arq_worker_stopped")


class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = _parse_redis_settings()
    functions = [start_crawl_job, check_schedules_job]
    cron_jobs = [
        cron(check_schedules_job, second={0}, unique=True),  # Every minute
    ]

    # CRITICAL: these values are non-negotiable (see module docstring)
    job_timeout = None  # None = no timeout (24/7 crawling)
    max_tries = 1  # Crawls are NOT idempotent
    health_check_interval = 30  # Detect dead workers in <1 minute
    max_jobs = 1  # One crawl at a time per worker

    on_startup = startup
    on_shutdown = shutdown
