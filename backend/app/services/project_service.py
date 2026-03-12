"""Project service — thin orchestration over ProjectRepository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.project_repo import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    """Business logic for project management."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProjectRepository(session)
        self._session = session

    async def create_project(self, data: ProjectCreate) -> Project:
        project = await self._repo.create_project(
            name=data.name,
            domain=data.domain,
            settings=data.settings,
        )
        await self._session.commit()
        return project

    async def get_project(self, project_id: uuid.UUID) -> Project | None:
        return await self._repo.get_by_id(project_id)

    async def list_projects(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._repo.list_all(cursor=cursor, limit=limit)

    async def update_project(
        self,
        project_id: uuid.UUID,
        data: ProjectUpdate,
    ) -> Project | None:
        project = await self._repo.get_by_id(project_id)
        if project is None:
            return None
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return project
        project = await self._repo.update_project(project, update_data)
        await self._session.commit()
        return project

    async def delete_project(self, project_id: uuid.UUID) -> bool:
        project = await self._repo.get_by_id(project_id)
        if project is None:
            return False
        await self._repo.delete_project(project)
        await self._session.commit()
        return True
