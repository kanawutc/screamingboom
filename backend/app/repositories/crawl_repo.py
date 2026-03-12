"""Crawl repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl import Crawl
from app.repositories.base import BaseRepository


class CrawlRepository(BaseRepository[Crawl]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Crawl)

    async def create_crawl(
        self,
        project_id: uuid.UUID,
        mode: str = "spider",
        config: dict | None = None,
    ) -> Crawl:
        return await self.create(Crawl(project_id=project_id, mode=mode, config=config or {}))

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        base_query = select(Crawl).where(Crawl.project_id == project_id)
        return await self.list_paginated(cursor=cursor, limit=limit, base_query=base_query)

    async def list_all(self, cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
        return await self.list_paginated(cursor=cursor, limit=limit)

    async def update_status(self, crawl_id: uuid.UUID, status: str) -> None:
        stmt = sa_update(Crawl).where(Crawl.id == crawl_id).values(status=status)
        await self._session.execute(stmt)
        await self._session.flush()

    async def increment_crawled_count(self, crawl_id: uuid.UUID, increment: int = 1) -> None:
        stmt = (
            sa_update(Crawl)
            .where(Crawl.id == crawl_id)
            .values(crawled_urls_count=Crawl.crawled_urls_count + increment)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def set_error_count(self, crawl_id: uuid.UUID, count: int) -> None:
        stmt = sa_update(Crawl).where(Crawl.id == crawl_id).values(error_count=count)
        await self._session.execute(stmt)
        await self._session.flush()

    async def set_total_urls(self, crawl_id: uuid.UUID, total: int) -> None:
        stmt = sa_update(Crawl).where(Crawl.id == crawl_id).values(total_urls=total)
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_crawl(self, crawl: Crawl) -> None:
        await self.delete(crawl)
