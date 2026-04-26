"""Repository for crawl schedules."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import CrawlSchedule


class ScheduleRepository:
    """Data-access layer for crawl_schedules table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        name: str,
        cron_expression: str,
        crawl_config: dict,
        is_active: bool = True,
        next_run_at: datetime | None = None,
    ) -> CrawlSchedule:
        schedule = CrawlSchedule(
            project_id=project_id,
            name=name,
            cron_expression=cron_expression,
            crawl_config=crawl_config,
            is_active=is_active,
            next_run_at=next_run_at,
        )
        self._session.add(schedule)
        await self._session.flush()
        return schedule

    async def get_by_id(self, schedule_id: uuid.UUID) -> CrawlSchedule | None:
        result = await self._session.execute(
            select(CrawlSchedule).where(CrawlSchedule.id == schedule_id)
        )
        return result.scalar_one_or_none()

    async def list_for_project(self, project_id: uuid.UUID) -> list[CrawlSchedule]:
        result = await self._session.execute(
            select(CrawlSchedule)
            .where(CrawlSchedule.project_id == project_id)
            .order_by(CrawlSchedule.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_due_schedules(self, now: datetime) -> list[CrawlSchedule]:
        """Get all active schedules whose next_run_at is <= now."""
        result = await self._session.execute(
            select(CrawlSchedule)
            .where(
                CrawlSchedule.is_active.is_(True),
                CrawlSchedule.next_run_at.isnot(None),
                CrawlSchedule.next_run_at <= now,
            )
            .order_by(CrawlSchedule.next_run_at)
        )
        return list(result.scalars().all())

    async def update_schedule(
        self, schedule_id: uuid.UUID, **kwargs: object
    ) -> CrawlSchedule | None:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self._session.execute(
            update(CrawlSchedule)
            .where(CrawlSchedule.id == schedule_id)
            .values(**kwargs)
        )
        await self._session.flush()
        return await self.get_by_id(schedule_id)

    async def delete_schedule(self, schedule_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(CrawlSchedule).where(CrawlSchedule.id == schedule_id)
        )
        return result.rowcount > 0
