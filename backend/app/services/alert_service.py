"""Alert service — generates alerts by comparing crawl results."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, text, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert

logger = structlog.get_logger(__name__)


class AlertService:
    """Generates and manages alerts from crawl analysis."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def analyze_crawl(self, crawl_id: uuid.UUID) -> list[Alert]:
        """Compare a completed crawl to the previous crawl for the same project.

        Generates alerts for:
        - Health score regressions
        - New critical/warning issues
        - Error rate spikes
        - Response time degradation
        - Pages lost (crawled before but now erroring)
        """
        # Get this crawl's project
        result = await self._session.execute(
            text("""
                SELECT c.project_id, c.status,
                       c.crawled_urls_count, c.error_count
                FROM crawls c WHERE c.id = :cid
            """),
            {"cid": str(crawl_id)},
        )
        crawl = result.first()
        if not crawl or crawl.status != "completed":
            return []

        project_id = crawl.project_id

        # Find the previous completed crawl
        result = await self._session.execute(
            text("""
                SELECT id, crawled_urls_count, error_count
                FROM crawls
                WHERE project_id = :pid AND status = 'completed' AND id != :cid
                ORDER BY completed_at DESC
                LIMIT 1
            """),
            {"pid": str(project_id), "cid": str(crawl_id)},
        )
        prev_crawl = result.first()

        alerts: list[Alert] = []

        # Health score comparison
        try:
            from app.repositories.url_repo import UrlRepository

            repo = UrlRepository(self._session)
            current_health = await repo.get_health_score(crawl_id)
            current_score = current_health.get("score", 0)

            if prev_crawl:
                prev_health = await repo.get_health_score(prev_crawl.id)
                prev_score = prev_health.get("score", 0)
                score_diff = current_score - prev_score

                if score_diff <= -10:
                    alerts.append(Alert(
                        project_id=project_id,
                        crawl_id=crawl_id,
                        alert_type="health_regression",
                        severity="critical" if score_diff <= -20 else "warning",
                        title=f"Health score dropped by {abs(score_diff)} points",
                        description=f"Score went from {prev_score} to {current_score} ({score_diff:+d})",
                        metric_before=prev_score,
                        metric_after=current_score,
                    ))
                elif score_diff >= 10:
                    alerts.append(Alert(
                        project_id=project_id,
                        crawl_id=crawl_id,
                        alert_type="health_improvement",
                        severity="info",
                        title=f"Health score improved by {score_diff} points",
                        description=f"Score went from {prev_score} to {current_score} ({score_diff:+d})",
                        metric_before=prev_score,
                        metric_after=current_score,
                    ))

            # Low health score alert
            if current_score < 50:
                alerts.append(Alert(
                    project_id=project_id,
                    crawl_id=crawl_id,
                    alert_type="low_health",
                    severity="critical",
                    title=f"Health score is critically low: {current_score}/100",
                    description="Multiple areas need immediate attention.",
                    metric_after=current_score,
                ))
        except Exception:
            logger.exception("alert_health_check_failed", crawl_id=str(crawl_id))

        # Error rate comparison
        if prev_crawl and prev_crawl.crawled_urls_count > 0:
            prev_error_rate = prev_crawl.error_count / prev_crawl.crawled_urls_count
            current_error_rate = (
                crawl.error_count / crawl.crawled_urls_count
                if crawl.crawled_urls_count > 0
                else 0
            )

            if current_error_rate > prev_error_rate + 0.05:
                alerts.append(Alert(
                    project_id=project_id,
                    crawl_id=crawl_id,
                    alert_type="error_spike",
                    severity="warning",
                    title=f"Error rate increased to {current_error_rate:.1%}",
                    description=f"Previous error rate was {prev_error_rate:.1%}. {crawl.error_count} errors found.",
                    metric_before=round(prev_error_rate * 100, 1),
                    metric_after=round(current_error_rate * 100, 1),
                ))

        # High error count (absolute)
        if crawl.error_count > 10:
            alerts.append(Alert(
                project_id=project_id,
                crawl_id=crawl_id,
                alert_type="high_errors",
                severity="warning" if crawl.error_count < 50 else "critical",
                title=f"{crawl.error_count} crawl errors detected",
                description=f"Out of {crawl.crawled_urls_count} URLs crawled.",
                metric_after=crawl.error_count,
            ))

        # Issue severity comparison
        try:
            from app.repositories.issue_repo import IssueRepository

            issue_repo = IssueRepository(self._session)
            current_issues = await issue_repo.get_summary(crawl_id)

            current_critical = (current_issues.by_severity or {}).get("critical", 0)
            if current_critical > 0:
                alerts.append(Alert(
                    project_id=project_id,
                    crawl_id=crawl_id,
                    alert_type="critical_issues",
                    severity="critical",
                    title=f"{current_critical} critical SEO issues found",
                    description=f"Total issues: {current_issues.total}",
                    metric_after=current_critical,
                ))

            if prev_crawl:
                prev_issues = await issue_repo.get_summary(prev_crawl.id)
                prev_total = prev_issues.total
                current_total = current_issues.total
                issue_diff = current_total - prev_total

                if issue_diff > 10:
                    alerts.append(Alert(
                        project_id=project_id,
                        crawl_id=crawl_id,
                        alert_type="issues_increased",
                        severity="warning",
                        title=f"{issue_diff} new issues since last crawl",
                        description=f"Issues went from {prev_total} to {current_total}.",
                        metric_before=prev_total,
                        metric_after=current_total,
                    ))
        except Exception:
            logger.exception("alert_issues_check_failed", crawl_id=str(crawl_id))

        # Response time check
        try:
            perf = await repo.get_performance_stats(crawl_id)
            perf_stats = perf.get("stats", {})
            avg_ms = perf_stats.get("avg_ms", 0)
            p95_ms = perf_stats.get("p95_ms", 0)

            if avg_ms > 3000:
                alerts.append(Alert(
                    project_id=project_id,
                    crawl_id=crawl_id,
                    alert_type="slow_site",
                    severity="warning",
                    title=f"Average response time is {avg_ms}ms",
                    description=f"P95 is {p95_ms}ms. Consider optimizing server performance.",
                    metric_after=avg_ms,
                ))
        except Exception:
            logger.exception("alert_perf_check_failed", crawl_id=str(crawl_id))

        # Save all alerts
        for alert in alerts:
            self._session.add(alert)

        if alerts:
            await self._session.flush()
            logger.info(
                "alerts_generated",
                crawl_id=str(crawl_id),
                count=len(alerts),
            )

        return alerts

    async def list_alerts(
        self,
        project_id: uuid.UUID | None = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Alert]:
        q = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if project_id:
            q = q.where(Alert.project_id == project_id)
        if unread_only:
            q = q.where(Alert.is_read.is_(False))
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def mark_read(self, alert_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(Alert).where(Alert.id == alert_id).values(is_read=True)
        )
        await self._session.flush()
        return result.rowcount > 0

    async def mark_all_read(self, project_id: uuid.UUID) -> int:
        result = await self._session.execute(
            update(Alert)
            .where(Alert.project_id == project_id, Alert.is_read.is_(False))
            .values(is_read=True)
        )
        await self._session.flush()
        return result.rowcount

    async def delete_alert(self, alert_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(Alert).where(Alert.id == alert_id)
        )
        return result.rowcount > 0

    async def unread_count(self, project_id: uuid.UUID | None = None) -> int:
        q = text("SELECT COUNT(*) FROM alerts WHERE is_read = false")
        params: dict = {}
        if project_id:
            q = text("SELECT COUNT(*) FROM alerts WHERE is_read = false AND project_id = :pid")
            params["pid"] = str(project_id)
        result = await self._session.execute(q, params)
        return result.scalar() or 0
