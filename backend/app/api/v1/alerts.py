"""Alert API routes — view, manage, and dismiss alerts."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import DbSession
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    crawl_id: uuid.UUID
    alert_type: str
    severity: str
    title: str
    description: str
    metric_before: float | None
    metric_after: float | None
    is_read: bool
    created_at: str


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    db: DbSession,
    project_id: uuid.UUID | None = Query(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
) -> list[AlertResponse]:
    """List alerts, optionally filtered by project and read status."""
    svc = AlertService(db)
    alerts = await svc.list_alerts(project_id=project_id, unread_only=unread_only, limit=limit)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/unread-count")
async def unread_count(
    db: DbSession,
    project_id: uuid.UUID | None = Query(None),
) -> dict:
    """Get the count of unread alerts."""
    svc = AlertService(db)
    count = await svc.unread_count(project_id=project_id)
    return {"unread_count": count}


@router.post("/{alert_id}/read", status_code=204)
async def mark_alert_read(alert_id: uuid.UUID, db: DbSession) -> None:
    """Mark an alert as read."""
    svc = AlertService(db)
    if not await svc.mark_read(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()


@router.post("/mark-all-read", status_code=204)
async def mark_all_read(
    db: DbSession,
    project_id: uuid.UUID = Query(...),
) -> None:
    """Mark all alerts for a project as read."""
    svc = AlertService(db)
    await svc.mark_all_read(project_id)
    await db.commit()


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: uuid.UUID, db: DbSession) -> None:
    """Delete an alert."""
    svc = AlertService(db)
    if not await svc.delete_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()


@router.post("/analyze/{crawl_id}")
async def trigger_analysis(crawl_id: uuid.UUID, db: DbSession) -> dict:
    """Manually trigger alert analysis for a crawl."""
    svc = AlertService(db)
    alerts = await svc.analyze_crawl(crawl_id)
    await db.commit()
    return {
        "crawl_id": str(crawl_id),
        "alerts_generated": len(alerts),
        "alerts": [AlertResponse.model_validate(a) for a in alerts],
    }
