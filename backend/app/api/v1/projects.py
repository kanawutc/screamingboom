"""Project API routes — CRUD for projects."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession
from app.schemas.pagination import CursorPage
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: DbSession) -> ProjectResponse:
    """Create a new project."""
    svc = ProjectService(db)
    project = await svc.create_project(data)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=CursorPage[ProjectResponse])
async def list_projects(
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> CursorPage[ProjectResponse]:
    """List all projects with cursor pagination."""
    svc = ProjectService(db)
    result = await svc.list_projects(cursor=cursor, limit=limit)
    return CursorPage(
        items=[ProjectResponse.model_validate(p) for p in result["items"]],
        next_cursor=result["next_cursor"],
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db: DbSession) -> ProjectResponse:
    """Get a project by ID."""
    svc = ProjectService(db)
    project = await svc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: DbSession,
) -> ProjectResponse:
    """Update a project."""
    svc = ProjectService(db)
    project = await svc.update_project(project_id, data)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db: DbSession) -> None:
    """Delete a project and all its crawl data."""
    svc = ProjectService(db)
    deleted = await svc.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
