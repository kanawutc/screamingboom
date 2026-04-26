"""Crawl Schedule API routes — CRUD for recurring crawl schedules."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/projects/{project_id}/schedules", tags=["schedules"])


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    project_id: uuid.UUID,
    data: ScheduleCreate,
    db: DbSession,
) -> ScheduleResponse:
    """Create a new crawl schedule for a project."""
    svc = ScheduleService(db)
    try:
        schedule = await svc.create_schedule(project_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScheduleResponse.model_validate(schedule)


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    project_id: uuid.UUID,
    db: DbSession,
) -> list[ScheduleResponse]:
    """List all schedules for a project."""
    svc = ScheduleService(db)
    schedules = await svc.list_schedules(project_id)
    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db: DbSession,
) -> ScheduleResponse:
    """Get a schedule by ID."""
    svc = ScheduleService(db)
    schedule = await svc.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.model_validate(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    data: ScheduleUpdate,
    db: DbSession,
) -> ScheduleResponse:
    """Update a crawl schedule."""
    svc = ScheduleService(db)
    try:
        schedule = await svc.update_schedule(schedule_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db: DbSession,
) -> None:
    """Delete a crawl schedule."""
    svc = ScheduleService(db)
    deleted = await svc.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
