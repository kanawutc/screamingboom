"""UrlIssue model for the url_issues partitioned table."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UrlIssue(Base):
    """An SEO issue detected on a crawled URL.

    The underlying table is HASH-partitioned by crawl_id.
    Composite primary key: (id, crawl_id).
    """

    __tablename__ = "url_issues"
    __table_args__ = {"implicit_returning": False}

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )
    crawl_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("crawls.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    url_id: Mapped[uuid.UUID] = mapped_column(sa.UUID(), nullable=False)
    issue_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(20), server_default="warning", nullable=False)
    category: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    details: Mapped[dict] = mapped_column(
        sa.JSON(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UrlIssue(id={self.id}, type={self.issue_type!r}, severity={self.severity!r})>"
