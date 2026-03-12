"""PageLink model."""

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PageLink(Base):
    """A link found on a crawled page."""

    __tablename__ = "page_links"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    crawl_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("crawls.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_url_id: Mapped[uuid.UUID] = mapped_column(sa.UUID(), nullable=False)
    target_url: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    target_url_hash: Mapped[bytes] = mapped_column(sa.LargeBinary(), nullable=False)
    anchor_text: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    link_type: Mapped[str] = mapped_column(sa.String(20), server_default="internal", nullable=False)
    rel_attrs: Mapped[Optional[list[str]]] = mapped_column(sa.ARRAY(sa.Text()), nullable=True)
    link_position: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    is_javascript: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.text("false"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PageLink(id={self.id}, type={self.link_type!r}, target={self.target_url!r})>"
