"""CrawledUrl model for the crawled_urls partitioned table."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.crawl import Crawl


class CrawledUrl(Base):
    """A URL discovered and crawled during a crawl session.

    The underlying table is HASH-partitioned by crawl_id.
    Composite primary key: (id, crawl_id).
    """

    __tablename__ = "crawled_urls"
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
    url: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    url_hash: Mapped[bytes] = mapped_column(sa.LargeBinary(), nullable=False)
    status_code: Mapped[Optional[int]] = mapped_column(sa.SmallInteger(), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    redirect_url: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    redirect_chain: Mapped[Optional[list]] = mapped_column(
        sa.JSON(), server_default=sa.text("'[]'::jsonb"), nullable=True
    )
    response_time_ms: Mapped[Optional[int]] = mapped_column(sa.Integer(), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    title_length: Mapped[Optional[int]] = mapped_column(sa.Integer(), nullable=True)
    title_pixel_width: Mapped[Optional[int]] = mapped_column(sa.Integer(), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    meta_desc_length: Mapped[Optional[int]] = mapped_column(sa.SmallInteger(), nullable=True)
    h1: Mapped[Optional[list[str]]] = mapped_column(sa.ARRAY(sa.Text()), nullable=True)
    h2: Mapped[Optional[list[str]]] = mapped_column(sa.ARRAY(sa.Text()), nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    robots_meta: Mapped[Optional[list[str]]] = mapped_column(sa.ARRAY(sa.Text()), nullable=True)
    is_indexable: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.text("true"), nullable=False
    )
    indexability_reason: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(sa.Integer(), nullable=True)
    content_hash: Mapped[Optional[bytes]] = mapped_column(sa.LargeBinary(), nullable=True)
    crawl_depth: Mapped[int] = mapped_column(sa.SmallInteger(), server_default="0", nullable=False)
    seo_data: Mapped[dict] = mapped_column(
        sa.JSON(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR(), nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

    # Relationships
    crawl: Mapped["Crawl"] = relationship("Crawl", back_populates="urls")

    @property
    def link_score(self) -> int | None:
        """Link Score from seo_data JSONB."""
        if self.seo_data and isinstance(self.seo_data, dict):
            return self.seo_data.get("link_score")
        return None

    def __repr__(self) -> str:
        return f"<CrawledUrl(id={self.id}, url={self.url!r}, status={self.status_code})>"
