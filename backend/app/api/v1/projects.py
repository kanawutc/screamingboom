"""Project API routes — CRUD for projects."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

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


@router.get("/{project_id}/stats")
async def get_project_stats(project_id: uuid.UUID, db: DbSession) -> dict:
    """Get project crawl history with summary stats."""
    sql = text("""
        SELECT
            c.id AS crawl_id,
            c.status,
            c.started_at,
            c.completed_at,
            c.crawled_urls_count,
            c.error_count,
            c.total_urls,
            EXTRACT(EPOCH FROM (c.completed_at - c.started_at))::int AS duration_secs
        FROM crawls c
        WHERE c.project_id = :project_id
        ORDER BY c.created_at DESC
        LIMIT 20
    """)
    result = await db.execute(sql, {"project_id": str(project_id)})
    crawls = [
        {
            "crawl_id": str(r.crawl_id),
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "urls_crawled": r.crawled_urls_count,
            "errors": r.error_count,
            "total_urls": r.total_urls,
            "duration_secs": r.duration_secs,
        }
        for r in result.all()
    ]

    total_crawls = len(crawls)
    completed = [c for c in crawls if c["status"] == "completed"]

    return {
        "total_crawls": total_crawls,
        "completed_crawls": len(completed),
        "latest_crawl": crawls[0] if crawls else None,
        "crawl_history": crawls,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db: DbSession) -> None:
    """Delete a project and all its crawl data."""
    svc = ProjectService(db)
    deleted = await svc.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
