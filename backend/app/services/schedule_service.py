"""Schedule service — manages crawl schedules and triggers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

logger = structlog.get_logger(__name__)


def compute_next_run(cron_expression: str, after: datetime | None = None) -> datetime:
    """Compute the next run time from a cron expression."""
    base = after or datetime.now(timezone.utc)
    cron = croniter(cron_expression, base)
    return cron.get_next(datetime).replace(tzinfo=timezone.utc)


def validate_cron(cron_expression: str) -> bool:
    """Check if a cron expression is valid."""
    return croniter.is_valid(cron_expression)


class ScheduleService:
    """Business logic for crawl schedule management."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ScheduleRepository(session)
        self._session = session

    async def create_schedule(
        self, project_id: uuid.UUID, data: ScheduleCreate
    ) -> object:
        if not validate_cron(data.cron_expression):
            raise ValueError(f"Invalid cron expression: {data.cron_expression}")

        next_run = compute_next_run(data.cron_expression) if data.is_active else None

        schedule = await self._repo.create(
            project_id=project_id,
            name=data.name,
            cron_expression=data.cron_expression,
            crawl_config=data.crawl_config.model_dump(),
            is_active=data.is_active,
            next_run_at=next_run,
        )
        await self._session.commit()
        await self._session.refresh(schedule)
        logger.info(
            "schedule_created",
            schedule_id=str(schedule.id),
            project_id=str(project_id),
            next_run=str(next_run),
        )
        return schedule

    async def update_schedule(
        self, schedule_id: uuid.UUID, data: ScheduleUpdate
    ) -> object | None:
        existing = await self._repo.get_by_id(schedule_id)
        if existing is None:
            return None

        update_data: dict = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.cron_expression is not None:
            if not validate_cron(data.cron_expression):
                raise ValueError(f"Invalid cron expression: {data.cron_expression}")
            update_data["cron_expression"] = data.cron_expression
        if data.crawl_config is not None:
            update_data["crawl_config"] = data.crawl_config.model_dump()
        if data.is_active is not None:
            update_data["is_active"] = data.is_active

        # Recompute next_run if cron or active status changed
        new_cron = update_data.get("cron_expression", existing.cron_expression)
        new_active = update_data.get("is_active", existing.is_active)
        if new_active:
            update_data["next_run_at"] = compute_next_run(new_cron)
        else:
            update_data["next_run_at"] = None

        schedule = await self._repo.update_schedule(schedule_id, **update_data)
        await self._session.commit()
        if schedule:
            await self._session.refresh(schedule)
        return schedule

    async def delete_schedule(self, schedule_id: uuid.UUID) -> bool:
        deleted = await self._repo.delete_schedule(schedule_id)
        await self._session.commit()
        return deleted

    async def get_schedule(self, schedule_id: uuid.UUID) -> object | None:
        return await self._repo.get_by_id(schedule_id)

    async def list_schedules(self, project_id: uuid.UUID) -> list:
        return await self._repo.list_for_project(project_id)

    async def get_due_schedules(self) -> list:
        """Get all active schedules that are due to run."""
        now = datetime.now(timezone.utc)
        return await self._repo.get_due_schedules(now)

    async def mark_schedule_run(
        self, schedule_id: uuid.UUID, crawl_id: uuid.UUID
    ) -> None:
        """Mark a schedule as having run and compute next run time."""
        schedule = await self._repo.get_by_id(schedule_id)
        if schedule is None:
            return
        now = datetime.now(timezone.utc)
        next_run = compute_next_run(schedule.cron_expression, after=now)
        await self._repo.update_schedule(
            schedule_id,
            last_run_at=now,
            last_crawl_id=crawl_id,
            next_run_at=next_run,
        )
        await self._session.commit()
