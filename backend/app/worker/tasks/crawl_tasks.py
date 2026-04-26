"""ARQ task definitions for crawl jobs."""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import structlog
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.crawler.engine import CrawlConfig, CrawlEngine

logger = structlog.get_logger(__name__)

# Preset user agent strings
_USER_AGENT_PRESETS: dict[str, str] = {
    "googlebot_desktop": (
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    ),
    "googlebot_mobile": (
        "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 "
        "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    ),
    "bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "chrome_desktop": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "seo_spider": "SEOSpider/1.0 (+https://github.com/user/seo-spider)",
}


def _resolve_user_agent(ua_input: str) -> str:
    """Resolve user agent: check presets first, then use as-is."""
    # Check if it's a preset key (case-insensitive, underscores/spaces)
    key = ua_input.lower().replace(" ", "_").replace("-", "_")
    return _USER_AGENT_PRESETS.get(key, ua_input)


async def start_crawl_job(ctx: dict, crawl_id: str) -> dict:
    """Execute a crawl job.

    Called by ARQ worker. Loads crawl config from DB, creates CrawlEngine,
    runs the full BFS crawl, and updates final status.

    Args:
        ctx: ARQ context dict (contains redis, asyncpg_pool).
        crawl_id: UUID string of the crawl record.

    Returns:
        Dict with crawl stats summary.
    """
    crawl_uuid = uuid.UUID(crawl_id)
    redis: Redis = ctx["redis_client"]
    pool: asyncpg.Pool = ctx["asyncpg_pool"]

    logger.info("crawl_job_starting", crawl_id=crawl_id)

    # Load crawl record from DB
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT c.id, c.project_id, c.config, c.mode, c.status,
                   p.domain
            FROM crawls c
            JOIN projects p ON p.id = c.project_id
            WHERE c.id = $1
            """,
            crawl_uuid,
        )

    if row is None:
        logger.error("crawl_not_found", crawl_id=crawl_id)
        return {"error": "crawl_not_found"}

    if row["status"] not in ("queued", "idle"):
        logger.warning(
            "crawl_invalid_status",
            crawl_id=crawl_id,
            status=row["status"],
        )
        return {"error": "invalid_status", "status": row["status"]}

    # Update status to crawling + set started_at
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE crawls SET status = 'crawling', started_at = NOW() WHERE id = $1",
            crawl_uuid,
        )

    # Build CrawlConfig from DB record
    # asyncpg may return JSON as str or dict depending on codec registration
    raw_config = row["config"]
    if isinstance(raw_config, str):
        import json as _json

        db_config: dict = _json.loads(raw_config) if raw_config else {}
    else:
        db_config = raw_config or {}
    # Convert rate_limit_rps to crawl_delay
    rate_limit_rps = db_config.get("rate_limit_rps", 2.0)
    crawl_delay = db_config.get("crawl_delay", 0.0)
    if rate_limit_rps and rate_limit_rps > 0 and crawl_delay == 0.0:
        crawl_delay = 1.0 / rate_limit_rps

    # Resolve user agent (support presets)
    ua = _resolve_user_agent(db_config.get("user_agent", "SEOSpider/1.0"))

    crawl_mode = row["mode"] or "spider"

    # Phase 3E: Load custom extraction rules for this project
    extraction_rules: list[dict] = []
    async with pool.acquire() as conn:
        rule_rows = await conn.fetch(
            "SELECT name, selector, selector_type, extract_type, attribute_name "
            "FROM extraction_rules WHERE project_id = $1",
            row["project_id"],
        )
        extraction_rules = [dict(r) for r in rule_rows]

    config = CrawlConfig(
        start_url=db_config.get("start_url", f"https://{row['domain']}"),
        max_urls=db_config.get("max_urls", settings.max_crawl_urls),
        max_depth=db_config.get("max_depth", settings.max_crawl_depth),
        user_agent=ua,
        respect_robots=db_config.get("respect_robots", True),
        follow_subdomains=db_config.get("follow_subdomains", False),
        request_timeout=db_config.get("request_timeout", 30),
        crawl_delay=crawl_delay,
        max_per_host=db_config.get("max_per_host", 2),
        mode=crawl_mode,
        urls=db_config.get("urls", []),
        extraction_rules=extraction_rules,
    )

    # Listen for control commands (pause/resume/stop) via Redis pub/sub
    engine = CrawlEngine(
        crawl_id=crawl_uuid,
        config=config,
        redis=redis,
        asyncpg_pool=pool,
    )

    # Start control listener in background
    control_task = asyncio.create_task(_listen_for_control(redis, crawl_id, engine))

    try:
        stats = await engine.run()
        logger.info(
            "crawl_job_completed",
            crawl_id=crawl_id,
            crawled=stats.crawled_count,
            errors=stats.error_count,
        )

        # Run alert analysis after crawl completes
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
            from app.core.config import settings as app_settings
            from app.services.alert_service import AlertService

            alert_engine = create_async_engine(app_settings.database_url, pool_pre_ping=True)
            alert_session_maker = async_sessionmaker(alert_engine, class_=AsyncSession, expire_on_commit=False)
            async with alert_session_maker() as alert_session:
                alert_svc = AlertService(alert_session)
                alerts = await alert_svc.analyze_crawl(crawl_uuid)
                await alert_session.commit()
                if alerts:
                    logger.info("alerts_generated_post_crawl", crawl_id=crawl_id, count=len(alerts))
            await alert_engine.dispose()
        except Exception:
            logger.exception("alert_analysis_failed", crawl_id=crawl_id)

        return {
            "crawl_id": crawl_id,
            "crawled_count": stats.crawled_count,
            "error_count": stats.error_count,
            "links_discovered": stats.links_discovered,
        }
    except Exception as e:
        logger.exception("crawl_job_failed", crawl_id=crawl_id, error=str(e))
        # Engine already handles marking failed in most cases,
        # but ensure it's set if an unexpected error escaped
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE crawls
                    SET status = 'failed', completed_at = NOW()
                    WHERE id = $1 AND status != 'failed'
                    """,
                    crawl_uuid,
                )
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        control_task.cancel()
        try:
            await control_task
        except asyncio.CancelledError:
            pass


async def _listen_for_control(
    redis: Redis,
    crawl_id: str,
    engine: CrawlEngine,
) -> None:
    """Subscribe to crawl control channel and relay commands to the engine.

    Commands: pause, resume, stop.
    """
    channel = f"crawl:{crawl_id}:control"
    # Use a separate Redis connection for pub/sub (blocking subscriber)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            command = message["data"]
            if isinstance(command, bytes):
                command = command.decode("utf-8")

            logger.info("crawl_control_received", crawl_id=crawl_id, command=command)

            if command == "pause":
                engine.pause()
            elif command == "resume":
                engine.resume()
            elif command == "stop":
                engine.stop()
                break
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
