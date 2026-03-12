"""Crawl model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.url import CrawledUrl


class Crawl(UUIDPrimaryKeyMixin, Base):
    """A crawl session belonging to a project."""

    __tablename__ = "crawls"

    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(sa.String(20), server_default="idle", nullable=False)
    mode: Mapped[str] = mapped_column(sa.String(10), server_default="spider", nullable=False)
    config: Mapped[dict] = mapped_column(
        sa.JSON(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    total_urls: Mapped[int] = mapped_column(sa.Integer(), server_default="0", nullable=False)
    crawled_urls_count: Mapped[int] = mapped_column(
        sa.Integer(), server_default="0", nullable=False
    )
    error_count: Mapped[int] = mapped_column(sa.Integer(), server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="crawls")
    urls: Mapped[list["CrawledUrl"]] = relationship(
        "CrawledUrl", back_populates="crawl", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Crawl(id={self.id}, status={self.status!r}, mode={self.mode!r})>"
