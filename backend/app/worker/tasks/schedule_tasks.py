"""Schedule checker task — runs periodically to trigger due crawl schedules."""

from __future__ import annotations

import uuid

import structlog
from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.repositories.schedule_repo import ScheduleRepository
from app.services.schedule_service import ScheduleService

logger = structlog.get_logger(__name__)


async def check_schedules_job(ctx: dict) -> dict:
    """Check for due schedules and enqueue crawl jobs for each.

    Runs every 60 seconds via ARQ cron. For each due schedule:
    1. Creates a new crawl record via the crawl service
    2. Enqueues the crawl job
    3. Updates the schedule with last_run_at and next_run_at
    """
    from datetime import datetime, timezone

    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    triggered = 0

    async with async_session() as session:
        repo = ScheduleRepository(session)
        svc = ScheduleService(session)

        now = datetime.now(timezone.utc)
        due_schedules = await repo.get_due_schedules(now)

        if not due_schedules:
            await engine.dispose()
            return {"triggered": 0}

        logger.info("schedules_due", count=len(due_schedules))

        for schedule in due_schedules:
            try:
                config = schedule.crawl_config or {}
                start_url = config.get("start_url")

                if not start_url:
                    # Try to get start_url from project domain
                    from sqlalchemy import text

                    result = await session.execute(
                        text("SELECT domain FROM projects WHERE id = :pid"),
                        {"pid": str(schedule.project_id)},
                    )
                    row = result.first()
                    if row:
                        domain = row.domain
                        if not domain.startswith("http"):
                            domain = f"https://{domain}"
                        start_url = domain

                if not start_url:
                    logger.warning(
                        "schedule_skip_no_url",
                        schedule_id=str(schedule.id),
                    )
                    continue

                # Create crawl record
                from app.models.crawl import Crawl

                crawl = Crawl(
                    project_id=schedule.project_id,
                    mode="spider",
                    config={
                        "start_url": start_url,
                        "max_urls": config.get("max_urls", 10000),
                        "max_depth": config.get("max_depth", 10),
                        "max_threads": config.get("max_threads", 5),
                        "rate_limit_rps": config.get("rate_limit_rps", 2.0),
                        "user_agent": config.get("user_agent", "SEOSpider/1.0"),
                        "respect_robots": config.get("respect_robots", True),
                        "include_patterns": config.get("include_patterns", []),
                        "exclude_patterns": config.get("exclude_patterns", []),
                        "scheduled": True,
                        "schedule_id": str(schedule.id),
                    },
                    status="queued",
                )
                session.add(crawl)
                await session.flush()

                # Enqueue the ARQ job
                redis_client = ctx.get("redis_client") or ctx.get("redis")
                arq_redis = ArqRedis(
                    pool_or_conn=redis_client.connection_pool,
                    default_queue_name="arq:queue",
                )
                await arq_redis.enqueue_job("start_crawl_job", str(crawl.id))

                # Mark schedule as run
                await svc.mark_schedule_run(schedule.id, crawl.id)

                triggered += 1
                logger.info(
                    "schedule_triggered",
                    schedule_id=str(schedule.id),
                    crawl_id=str(crawl.id),
                    schedule_name=schedule.name,
                )

            except Exception:
                logger.exception(
                    "schedule_trigger_failed",
                    schedule_id=str(schedule.id),
                )

        await session.commit()

    await engine.dispose()
    return {"triggered": triggered}
