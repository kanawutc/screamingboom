"""Issue repository — queries for url_issues partitioned table.

Uses raw asyncpg queries via session connection for best performance
with partitioned tables (same pattern as url_repo).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.issue_registry import ISSUE_REGISTRY
from app.schemas.issue import IssueResponse, IssueSummary


class IssueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_issues(
        self,
        crawl_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
        severity: str | None = None,
        category: str | None = None,
        issue_type: str | None = None,
    ) -> dict[str, Any]:
        """List issues for a crawl with cursor pagination and filters.

        Returns dict with 'items' (list of IssueResponse) and 'next_cursor'.
        """
        # Build query with filters
        conditions = ["ui.crawl_id = :crawl_id"]
        params: dict[str, Any] = {"crawl_id": crawl_id, "limit": limit + 1}

        if severity:
            conditions.append("ui.severity = :severity")
            params["severity"] = severity
        if category:
            conditions.append("ui.category = :category")
            params["category"] = category
        if issue_type:
            conditions.append("ui.issue_type = :issue_type")
            params["issue_type"] = issue_type
        if cursor:
            try:
                params["cursor"] = uuid.UUID(cursor)
            except (ValueError, AttributeError):
                return {"items": [], "next_cursor": None}
            conditions.append("ui.id > :cursor")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                ui.id,
                ui.crawl_id,
                ui.url_id,
                cu.url,
                ui.issue_type,
                ui.severity,
                ui.category,
                ui.details
            FROM url_issues ui
            JOIN crawled_urls cu ON cu.id = ui.url_id AND cu.crawl_id = ui.crawl_id
            WHERE {where_clause}
            ORDER BY ui.id
            LIMIT :limit
        """

        # Execute via raw connection to handle partitioned tables
        from sqlalchemy import text

        result = await self._session.execute(text(query), params)
        rows = result.fetchall()

        has_more = len(rows) > limit
        page_rows = rows[:limit]

        items = []
        for row in page_rows:
            defn = ISSUE_REGISTRY.get(row.issue_type)
            description = defn.description if defn else row.issue_type

            details = row.details
            if details is None:
                details = {}
            elif isinstance(details, str):
                try:
                    details = json.loads(details)
                except (json.JSONDecodeError, TypeError):
                    details = {}

            items.append(
                IssueResponse(
                    id=str(row.id),
                    crawl_id=str(row.crawl_id),
                    url_id=str(row.url_id),
                    url=row.url,
                    issue_type=row.issue_type,
                    severity=row.severity,
                    category=row.category,
                    description=description,
                    details=details if isinstance(details, dict) else {},
                )
            )

        next_cursor = str(page_rows[-1].id) if has_more and page_rows else None

        return {"items": items, "next_cursor": next_cursor}

    async def get_summary(self, crawl_id: uuid.UUID) -> IssueSummary:
        """Get aggregated issue counts by severity and category."""
        from sqlalchemy import text

        # Total count
        total_result = await self._session.execute(
            text("SELECT COUNT(*) FROM url_issues WHERE crawl_id = :crawl_id"),
            {"crawl_id": crawl_id},
        )
        total = total_result.scalar() or 0

        # By severity
        sev_result = await self._session.execute(
            text("""
                SELECT severity, COUNT(*) as cnt
                FROM url_issues
                WHERE crawl_id = :crawl_id
                GROUP BY severity
            """),
            {"crawl_id": crawl_id},
        )
        by_severity = {row.severity: row.cnt for row in sev_result.fetchall()}

        # By category
        cat_result = await self._session.execute(
            text("""
                SELECT category, COUNT(*) as cnt
                FROM url_issues
                WHERE crawl_id = :crawl_id
                GROUP BY category
            """),
            {"crawl_id": crawl_id},
        )
        by_category = {row.category: row.cnt for row in cat_result.fetchall()}

        return IssueSummary(
            total=total,
            by_severity=by_severity,
            by_category=by_category,
        )
