"""Project repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Project)

    async def create_project(
        self,
        name: str,
        domain: str,
        settings: dict | None = None,
    ) -> Project:
        return await self.create(Project(name=name, domain=domain, settings=settings or {}))

    async def get_by_id(self, entity_id: uuid.UUID) -> Project | None:
        return await super().get_by_id(entity_id)

    async def list_all(self, cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
        return await self.list_paginated(cursor=cursor, limit=limit)

    async def update_project(self, project: Project, data: dict) -> Project:
        return await self.update(project, data)

    async def delete_project(self, project: Project) -> None:
        await self.delete(project)
