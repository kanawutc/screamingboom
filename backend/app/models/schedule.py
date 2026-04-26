"""Crawl Schedule model — recurring crawl configuration."""

import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CrawlSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A recurring crawl schedule attached to a project."""

    __tablename__ = "crawl_schedules"

    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    cron_expression: Mapped[str] = mapped_column(
        sa.String(100), nullable=False
    )
    crawl_config: Mapped[dict] = mapped_column(
        sa.JSON(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.text("true"), nullable=False
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_crawl_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.UUID(), nullable=True
    )

    # Relationship
    project: Mapped["Project"] = relationship("Project")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<CrawlSchedule(id={self.id}, name={self.name!r}, cron={self.cron_expression!r})>"
