"""Crawl API routes — lifecycle management for crawls."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.api.deps import DbSession, RedisClient
from app.schemas.crawl import CrawlCreate, CrawlResponse, CrawlSummary
from app.schemas.pagination import CursorPage
from app.services.crawl_service import CrawlService
from app.websocket.manager import get_broadcaster

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["crawls"])


# ------------------------------------------------------------------
# Crawl creation (nested under projects)
# ------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/crawls",
    response_model=CrawlResponse,
    status_code=201,
)
async def start_crawl(
    project_id: uuid.UUID,
    data: CrawlCreate,
    db: DbSession,
    redis: RedisClient,
) -> CrawlResponse:
    """Start a new crawl for a project. Creates the record and enqueues the ARQ job."""
    # Verify project exists
    from app.services.project_service import ProjectService

    project_svc = ProjectService(db)
    project = await project_svc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    svc = CrawlService(db, redis)
    crawl = await svc.start_crawl(project_id, data)
    return CrawlResponse.model_validate(crawl)


@router.get(
    "/projects/{project_id}/crawls",
    response_model=CursorPage[CrawlSummary],
)
async def list_crawls_for_project(
    project_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> CursorPage[CrawlSummary]:
    """List crawls for a project with cursor pagination."""
    from app.services.project_service import ProjectService

    project_svc = ProjectService(db)
    project = await project_svc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    svc = CrawlService(db, redis)
    result = await svc.list_crawls(project_id, cursor=cursor, limit=limit)
    return CursorPage(
        items=[CrawlSummary.model_validate(c) for c in result["items"]],
        next_cursor=result["next_cursor"],
    )


@router.get("/crawls", response_model=CursorPage[CrawlSummary])
async def list_all_crawls(
    db: DbSession,
    redis: RedisClient,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> CursorPage[CrawlSummary]:
    svc = CrawlService(db, redis)
    result = await svc.list_all_crawls(cursor=cursor, limit=limit)
    return CursorPage(
        items=[CrawlSummary.model_validate(c) for c in result["items"]],
        next_cursor=result["next_cursor"],
    )


@router.get("/crawls/{crawl_id}", response_model=CrawlResponse)
async def get_crawl(
    crawl_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> CrawlResponse:
    """Get crawl detail: status, stats, config."""
    svc = CrawlService(db, redis)
    crawl = await svc.get_crawl(crawl_id)
    if crawl is None:
        raise HTTPException(status_code=404, detail="Crawl not found")
    return CrawlResponse.model_validate(crawl)


@router.post("/crawls/{crawl_id}/pause", status_code=200)
async def pause_crawl(
    crawl_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> dict:
    """Pause a running crawl."""
    svc = CrawlService(db, redis)
    ok = await svc.pause_crawl(crawl_id)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Crawl cannot be paused (not in 'crawling' state)",
        )
    return {"status": "paused", "crawl_id": str(crawl_id)}


@router.post("/crawls/{crawl_id}/resume", status_code=200)
async def resume_crawl(
    crawl_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> dict:
    """Resume a paused crawl."""
    svc = CrawlService(db, redis)
    ok = await svc.resume_crawl(crawl_id)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Crawl cannot be resumed (not in 'paused' state)",
        )
    return {"status": "crawling", "crawl_id": str(crawl_id)}


@router.post("/crawls/{crawl_id}/stop", status_code=200)
async def stop_crawl(
    crawl_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> dict:
    """Stop (cancel) a running or paused crawl."""
    svc = CrawlService(db, redis)
    ok = await svc.stop_crawl(crawl_id)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Crawl cannot be stopped (not in active state)",
        )
    return {"status": "cancelled", "crawl_id": str(crawl_id)}


@router.delete("/crawls/{crawl_id}", status_code=204)
async def delete_crawl(
    crawl_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> None:
    """Delete a crawl and all associated URL/link data."""
    svc = CrawlService(db, redis)
    deleted = await svc.delete_crawl(crawl_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Crawl not found")


# ------------------------------------------------------------------
# WebSocket endpoint (T18)
# ------------------------------------------------------------------


@router.websocket("/crawls/{crawl_id}/ws")
async def crawl_websocket(websocket: WebSocket, crawl_id: uuid.UUID) -> None:
    """WebSocket endpoint for real-time crawl progress.

    Subscribes to CrawlBroadcaster for the given crawl_id and forwards
    all events to the connected client. Sends ping every 30s.
    """
    await websocket.accept()

    broadcaster = get_broadcaster()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    crawl_id_str = str(crawl_id)

    await broadcaster.subscribe(crawl_id_str, queue)
    logger.info("ws_client_connected", crawl_id=crawl_id_str)

    try:
        while True:
            try:
                # Wait for message with timeout (30s heartbeat)
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(message)
            except asyncio.TimeoutError:
                # Send heartbeat ping
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", crawl_id=crawl_id_str)
    except Exception as e:
        logger.warning("ws_client_error", crawl_id=crawl_id_str, error=str(e))
    finally:
        await broadcaster.unsubscribe(crawl_id_str, queue)
