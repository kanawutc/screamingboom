"""Crawl service — orchestrates crawl lifecycle, ARQ enqueue, and Redis control."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from arq import ArqRedis
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.crawl import Crawl
from app.repositories.crawl_repo import CrawlRepository
from app.repositories.url_repo import UrlRepository
from app.schemas.crawl import CrawlCreate

logger = structlog.get_logger(__name__)


class CrawlService:
    """Business logic for crawl lifecycle management.

    Responsibilities:
    - Create crawl record + enqueue ARQ job
    - Pause/resume/stop via Redis pub/sub
    - List/get crawl details
    - Delete crawl + cascade data
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
    ) -> None:
        self._repo = CrawlRepository(session)
        self._url_repo = UrlRepository(session)
        self._session = session
        self._redis = redis

    async def start_crawl(
        self,
        project_id: uuid.UUID,
        data: CrawlCreate,
    ) -> Crawl:
        """Create a crawl record and enqueue the ARQ job."""
        config_dict: dict[str, Any] = {
            "start_url": data.start_url,
            "max_urls": data.config.max_urls,
            "max_depth": data.config.max_depth,
            "max_threads": data.config.max_threads,
            "rate_limit_rps": data.config.rate_limit_rps,
            "user_agent": data.config.user_agent,
            "respect_robots": data.config.respect_robots,
        }

        if data.mode == "list" and data.urls:
            config_dict["urls"] = data.urls
            if not data.start_url and data.urls:
                config_dict["start_url"] = data.urls[0]

        crawl = await self._repo.create_crawl(
            project_id=project_id,
            mode=data.mode.value,
            config=config_dict,
        )
        # Set status to queued
        await self._repo.update_status(crawl.id, "queued")
        await self._session.commit()
        await self._session.refresh(crawl)

        # Enqueue ARQ job
        try:
            arq_redis = ArqRedis(
                pool_or_conn=self._redis.connection_pool,
                default_queue_name="arq:queue",
            )
            await arq_redis.enqueue_job(
                "start_crawl_job",
                str(crawl.id),
            )
            logger.info("crawl_job_enqueued", crawl_id=str(crawl.id))
        except Exception as e:
            logger.error("crawl_enqueue_failed", crawl_id=str(crawl.id), error=str(e))
            # Revert status to failed if enqueue fails
            await self._repo.update_status(crawl.id, "failed")
            await self._session.commit()
            raise

        return crawl

    async def get_crawl(self, crawl_id: uuid.UUID) -> Crawl | None:
        """Get a single crawl with its current stats."""
        return await self._repo.get_by_id(crawl_id)

    async def list_crawls(
        self,
        project_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._repo.list_by_project(
            project_id=project_id,
            cursor=cursor,
            limit=limit,
        )

    async def list_all_crawls(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._repo.list_all(cursor=cursor, limit=limit)

    async def pause_crawl(self, crawl_id: uuid.UUID) -> bool:
        """Send pause command via Redis pub/sub."""
        crawl = await self._repo.get_by_id(crawl_id)
        if crawl is None or crawl.status != "crawling":
            return False
        await self._repo.update_status(crawl_id, "paused")
        await self._session.commit()
        # Publish AFTER commit so DB state is consistent if worker reads immediately
        channel = f"crawl:{crawl_id}:control"
        await self._redis.publish(channel, "pause")
        logger.info("crawl_pause_sent", crawl_id=str(crawl_id))
        return True

    async def resume_crawl(self, crawl_id: uuid.UUID) -> bool:
        """Send resume command via Redis pub/sub."""
        crawl = await self._repo.get_by_id(crawl_id)
        if crawl is None or crawl.status != "paused":
            return False
        await self._repo.update_status(crawl_id, "crawling")
        await self._session.commit()
        # Publish AFTER commit so DB state is consistent if worker reads immediately
        channel = f"crawl:{crawl_id}:control"
        await self._redis.publish(channel, "resume")
        logger.info("crawl_resume_sent", crawl_id=str(crawl_id))
        return True

    async def stop_crawl(self, crawl_id: uuid.UUID) -> bool:
        """Send stop command via Redis pub/sub."""
        crawl = await self._repo.get_by_id(crawl_id)
        if crawl is None or crawl.status not in ("crawling", "paused", "queued"):
            return False
        # Engine will set final status, but update to cancelled for immediate feedback
        await self._repo.update_status(crawl_id, "cancelled")
        await self._session.commit()
        # Publish AFTER commit so DB state is consistent if worker reads immediately
        channel = f"crawl:{crawl_id}:control"
        await self._redis.publish(channel, "stop")
        logger.info("crawl_stop_sent", crawl_id=str(crawl_id))
        return True

    async def delete_crawl(self, crawl_id: uuid.UUID) -> bool:
        """Delete a crawl and all associated data (cascade)."""
        crawl = await self._repo.get_by_id(crawl_id)
        if crawl is None:
            return False
        # If crawl is running, stop it first
        if crawl.status in ("crawling", "paused"):
            channel = f"crawl:{crawl_id}:control"
            await self._redis.publish(channel, "stop")
        await self._repo.delete_crawl(crawl)
        await self._session.commit()
        logger.info("crawl_deleted", crawl_id=str(crawl_id))
        return True
