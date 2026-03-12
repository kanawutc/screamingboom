"""Issues API routes — SEO issue queries."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.repositories.issue_repo import IssueRepository
from app.schemas.issue import IssueResponse, IssueSummary
from app.schemas.pagination import CursorPage

router = APIRouter(tags=["issues"])


@router.get(
    "/crawls/{crawl_id}/issues",
    response_model=CursorPage[IssueResponse],
)
async def list_issues(
    crawl_id: uuid.UUID,
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    severity: str | None = Query(
        None, description="Filter by severity (critical/warning/info/opportunity)"
    ),
    category: str | None = Query(None, description="Filter by category (titles/security/etc.)"),
    issue_type: str | None = Query(None, description="Filter by specific issue type"),
) -> CursorPage[IssueResponse]:
    """List SEO issues for a crawl with cursor pagination and optional filters."""
    repo = IssueRepository(db)
    result = await repo.list_issues(
        crawl_id=crawl_id,
        cursor=cursor,
        limit=limit,
        severity=severity,
        category=category,
        issue_type=issue_type,
    )
    return CursorPage(
        items=result["items"],
        next_cursor=result["next_cursor"],
    )


@router.get(
    "/crawls/{crawl_id}/issues/summary",
    response_model=IssueSummary,
)
async def get_issues_summary(
    crawl_id: uuid.UUID,
    db: DbSession,
) -> IssueSummary:
    """Get aggregated issue counts by severity and category for a crawl."""
    repo = IssueRepository(db)
    return await repo.get_summary(crawl_id)
